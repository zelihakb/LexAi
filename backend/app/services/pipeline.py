from collections import OrderedDict
import re

from app.core.config import MIN_FINAL_SCORE, MIN_TOP_GAP
from app.services.helpers import (
    compact_text,
    normalize_relation_label,
    normalize_text,
    safe_float,
    safe_int,
)
from app.services.retrieval import (
    build_raw_evidence,
    cross_encoder_rerank,
    format_raw_evidence,
    hybrid_candidate_scoring,
    retrieve_candidates_with_rrf,
    scroll_candidates,
)
from app.services.llm_service import interpret_with_llm


# =========================
# SON YÖNÜ KOD BELİRLESİN
# =========================
def decide_final_direction(parsed: dict):
    if not parsed or "decisions" not in parsed:
        return "unclear"

    rank_weights = {
        1: 1.35,
        2: 0.95,
        3: 0.70,
        4: 0.45,
        5: 0.30,
    }

    yes_score = 0.0
    no_score = 0.0
    neutral_score = 0.0

    rank1 = None
    rank2 = None

    for d in parsed["decisions"]:
        rank = safe_int(d.get("rank", 0), 0)
        relation = normalize_relation_label(d.get("relation", "unclear"))
        w = rank_weights.get(rank, 0.25)

        if rank == 1:
            rank1 = relation
        elif rank == 2:
            rank2 = relation

        if relation == "supports_yes":
            yes_score += w
        elif relation == "supports_no":
            no_score += w
        else:
            neutral_score += w

    if rank1 == "supports_yes" and yes_score >= no_score * 0.95:
        return "yes"
    if rank1 == "supports_no" and no_score >= yes_score * 0.95:
        return "no"

    if rank1 in {"unclear", "procedural"} and rank2 == "supports_yes" and yes_score > no_score * 1.05:
        return "yes"
    if rank1 in {"unclear", "procedural"} and rank2 == "supports_no" and no_score > yes_score * 1.05:
        return "no"

    if yes_score >= no_score * 1.15 and yes_score > neutral_score:
        return "yes"
    if no_score >= yes_score * 1.15 and no_score > neutral_score:
        return "no"

    return "unclear"


# =========================
# CONFIDENCE
# =========================
def assess_confidence(final_items: list, parsed=None):
    if not final_items:
        return {"status": "weak", "reason": "hiç aday yok"}

    top1 = safe_float(final_items[0].get("final_score", 0.0))
    top2 = safe_float(final_items[1].get("final_score", 0.0)) if len(final_items) > 1 else 0.0
    gap = top1 - top2

    if top1 < MIN_FINAL_SCORE:
        return {"status": "weak", "reason": f"üst skor düşük ({top1:.3f})"}

    if gap < MIN_TOP_GAP:
        return {"status": "uncertain", "reason": f"ilk iki aday çok yakın (gap={gap:.3f})"}

    top_folders = [
        str(item.get("payload", {}).get("folder", "")).strip()
        for item in final_items[:3]
        if item.get("payload")
    ]
    unique_top_folders = {f for f in top_folders if f}

    if len(unique_top_folders) >= 3:
        return {"status": "uncertain", "reason": "üst kararlar farklı alanlara dağılıyor"}

    if len(unique_top_folders) == 2 and len(top_folders) >= 2:
        if top_folders[0] != top_folders[1]:
            return {"status": "uncertain", "reason": "ilk iki karar farklı alanlardan geliyor"}

    if parsed and "decisions" in parsed:
        labels = [normalize_relation_label(d.get("relation", "unclear")) for d in parsed["decisions"][:3]]
        decisive_count = labels.count("supports_yes") + labels.count("supports_no")

        if labels.count("irrelevant") >= 2:
            return {"status": "weak", "reason": "üst kararların çoğu alakasız"}

        if decisive_count == 0 and labels.count("unclear") >= 2:
            return {"status": "uncertain", "reason": "üst kararların çoğu net yön vermiyor"}

        if decisive_count == 1 and labels.count("unclear") >= 2:
            return {"status": "uncertain", "reason": "üst kararlarda tek güçlü yön var"}

    return {"status": "ok", "reason": f"üst skor yeterli ({top1:.3f})"}


# =========================
# DETERMINISTIC YORUM
# =========================
def build_relation_text(relation: str):
    relation = normalize_relation_label(relation)

    if relation == "supports_yes":
        return "kullanıcının sorusuna evet cevabını destekliyor"
    if relation == "supports_no":
        return "kullanıcının sorusuna hayır cevabını destekliyor"
    if relation == "procedural":
        return "daha çok usuli değerlendirme içeriyor"
    if relation == "irrelevant":
        return "soruyla bağlantısı zayıf"
    return "soruyla bağlantılı olmakla birlikte net evet/hayır yönü vermiyor"


def build_card_relevance_text(relation: str):
    relation = normalize_relation_label(relation)

    if relation == "supports_yes":
        return "Bu karar, soruya evet yönünde cevap veren emsaller arasında görülmüştür."
    if relation == "supports_no":
        return "Bu karar, soruya hayır yönünde cevap veren emsaller arasında görülmüştür."
    if relation == "procedural":
        return "Bu karar daha çok usul, görev, süre veya inceleme şartlarıyla ilgilidir."
    if relation == "irrelevant":
        return "Bu kararın soruyla bağlantısı zayıf görülmüştür."

    return "Bu karar soruyla bağlantılı görünse de net bir sonuç yönü vermemektedir."
def build_source_label(item: dict):
    payload = item.get("payload", {}) if item else {}

    court = str(payload.get("court", "")).strip()
    case_no = str(payload.get("case_no", "")).strip()
    decision_no = str(payload.get("decision_no", "")).strip()

    parts = []

    if court:
        parts.append(court)
    if case_no:
        parts.append(f"E. {case_no}")
    if decision_no:
        parts.append(f"K. {decision_no}")

    return " | ".join(parts) if parts else "Karar"


def is_bad_summary(summary: str) -> bool:
    summary = compact_text(summary)
    summary_norm = summary.lower().strip(" .,:;!-")

    bad_summaries = {
        "tek cümleli net karar özeti",
        "tek cümlelik net karar özeti",
        "tek cümlelik, sade, net karar özeti",
        "kararın somut kısa içeriği",
        "kısa karar özeti",
        "somut kısa özet",
        "karardan net kısa özet üretilemedi.",
    }

    if not summary:
        return True

    if summary_norm in bad_summaries:
        return True

    if "tek cümle" in summary_norm and "özet" in summary_norm:
        return True

    if "kısa" in summary_norm and "özet" in summary_norm and len(summary_norm) < 45:
        return True

    generic_bad_patterns = [
        "kararı soruya hayır yönünde yakın görünüyor",
        "kararı soruya evet yönünde yakın görünüyor",
        "kararı daha çok usuli değerlendirme içeriyor",
        "kararından net yön çıkarılamadı",
        "sorudaki talep veya savunma",
        "sorudaki talep veya hukuki sonuç",
        "talep veya savunma bakımından",
        "otomatik metin eşleşmesine dayandığı",
        "otomatik eşleşmeye dayandığı",
        "somut olay bakımından ayrıca kontrol edilmelidir",
        "emsaller arasında değerlendirilmiştir",
        "mahkeme, davacının taleb",
        "davanın kabul",
        "davanın redd",
        "talebinin yasal dayanağı",
        "kabul edilmesi gerektiğini belirtti",
        "soruya hayır yönünde cevap verebilecek",
        "soruya evet yönünde cevap verebilecek",
    ]

    if any(pattern in summary_norm for pattern in generic_bad_patterns):
        return True

    return False
def build_contextual_summary_from_payload(payload: dict, relation: str):
    raw_text = str(payload.get("text", "") or "")
    text = normalize_text(raw_text[:8000])
    relation = normalize_relation_label(relation)

    if not text:
        if relation == "supports_yes":
            return "Bu karar, sorudaki hukuki sonuca olumlu yaklaşan emsaller arasında değerlendirilmiştir."
        if relation == "supports_no":
            return "Bu karar, sorudaki hukuki sonuca olumsuz yaklaşan emsaller arasında değerlendirilmiştir."
        if relation == "procedural":
            return "Bu karar daha çok usul, görev, süre veya inceleme şartları bakımından önem taşımaktadır."
        if relation == "irrelevant":
            return "Bu kararın soruyla doğrudan bağlantısı zayıf görülmüştür."
        return "Bu karar soruyla bağlantılı görünse de net bir sonuç yönü vermemektedir."

    # Kira / temerrüt / tahliye / 30 gün
    if (
        ("temerrut" in text or "temerrüt" in raw_text.lower())
        and "tahliye" in text
        and (
            "otuz gun" in text
            or "otuz günlük" in raw_text.lower()
            or "30 gun" in text
            or "30 günlük" in raw_text.lower()
        )
    ):
        return (
            "Karar, temerrüt nedeniyle tahliye için kiracıya kanuni ödeme süresinin tanınması gerektiğini vurgulamaktadır. "
            "Bu süre beklenmeden tahliye istenirse temerrüt koşullarının oluşmadığı değerlendirilebilir."
        )

    # Ödeme emri sonrası yapılan ödemeler
    if (
        "odeme emri" in text
        and "odeme" in text
        and ("bilirkişi" in raw_text.lower() or "ek rapor" in text or "hesap" in text)
    ):
        return (
            "Karar, ödeme emrinin tebliğinden sonra yapılan ödemelerin kira alacağı hesabında dikkate alınması gerektiğini belirtmektedir. "
            "Bu ödemeler incelenmeden verilen karar eksik değerlendirme sayılabilir."
        )

    # İtirazın kaldırılması / kira alacağı
    if (
        "itirazin kaldirilmasi" in text
        or "itirazın kaldırılması" in raw_text.lower()
    ) and ("kira" in text or "kiraci" in text or "kiracı" in raw_text.lower()):
        return (
            "Karar, kira alacağına dayalı icra takibinde borca itirazın kaldırılması talebinin ödeme kayıtlarıyla birlikte değerlendirilmesi gerektiğini göstermektedir."
        )

    # Kefil sorumluluğu
    if "kefil" in text and ("sorumluluk" in text or "sorumlulug" in text):
        return (
            "Karar, kira sözleşmesinde kefilin sorumluluğunun hangi dönemle sınırlı olduğunun ayrıca incelenmesi gerektiğini göstermektedir."
        )

    # Genel kira/tahliye
    if "kira" in text and "tahliye" in text:
        if relation == "supports_yes":
            return (
                "Karar, kira ilişkisi ve tahliye şartları bakımından kiraya veren lehine sonuç doğurabilecek bir değerlendirme içermektedir."
            )
        if relation == "supports_no":
            return (
                "Karar, kira ilişkisi ve tahliye şartları bakımından tahliye talebinin her durumda kabul edilmeyeceğini göstermektedir."
            )

    # Genel icra
    if "icra" in text or "takip" in text or "ödeme emri" in raw_text.lower():
        if relation == "supports_yes":
            return (
                "Karar, icra takibi bakımından talebin kabul edilebileceği durumlara işaret eden emsaller arasında değerlendirilmiştir."
            )
        if relation == "supports_no":
            return (
                "Karar, icra takibi bakımından talebin eksik inceleme veya şartların oluşmaması nedeniyle kabul edilmeyebileceğini göstermektedir."
            )

    # Genel fallback
    if relation == "supports_yes":
        return "Bu karar, sorudaki hukuki sonuca olumlu yaklaşan emsaller arasında değerlendirilmiştir."
    if relation == "supports_no":
        return "Bu karar, sorudaki hukuki sonuca olumsuz yaklaşan emsaller arasında değerlendirilmiştir."
    if relation == "procedural":
        return "Bu karar daha çok usul, görev, süre veya inceleme şartları bakımından önem taşımaktadır."
    if relation == "irrelevant":
        return "Bu kararın soruyla doğrudan bağlantısı zayıf görülmüştür."

    return "Bu karar soruyla bağlantılı görünse de net bir sonuç yönü vermemektedir."
def build_safe_decision_summary(parsed_decision: dict, relation: str, payload: dict | None = None):
    summary = compact_text(parsed_decision.get("holding", ""))

    if not is_bad_summary(summary):
        return summary

    return build_contextual_summary_from_payload(payload or {}, relation)

def build_deterministic_commentary(
    question: str,
    parsed: dict,
    final_direction: str,
    confidence: dict,
    final_items: list | None = None,
):
    decisions = parsed.get("decisions", []) if parsed else []
    final_items = final_items or []

    if not decisions:
        return (
            "Bu soru için yeterli emsal karar bulunamadı. "
            "Daha net sonuç alabilmek için soruyu biraz daha somutlaştırarak yeniden arayabilirsin. "
            "Bu değerlendirme otomatik oluşturulmuş bir taslaktır ve hukuki danışmanlık yerine geçmez."
        )

    decisive = []

    for d in decisions:
        rel = normalize_relation_label(d.get("relation", "unclear"))

        if final_direction == "yes" and rel == "supports_yes":
            decisive.append(d)
        elif final_direction == "no" and rel == "supports_no":
            decisive.append(d)
        elif final_direction == "unclear" and rel in {"unclear", "procedural"}:
            decisive.append(d)

    if not decisive:
        decisive = decisions[:2]

    source_labels = []
    reason_snippets = []

    for d in decisive[:2]:
        rank = safe_int(d.get("rank", 0), 0)
        item = final_items[rank - 1] if rank > 0 and rank <= len(final_items) else {}
        payload = item.get("payload", {}) if item else {}
        source = build_source_label(item)

        if source and source != "Karar":
            source_labels.append(source)

        rel = normalize_relation_label(d.get("relation", "unclear"))

        try:
            summary = build_safe_decision_summary(d, rel, payload)
        except TypeError:
            summary = build_safe_decision_summary(d, rel)

        summary = compact_text(summary)

        too_generic = any(
            phrase in summary.lower()
            for phrase in [
                "soruya hayır yönünde cevap verebilecek",
                "soruya evet yönünde cevap verebilecek",
                "emsal olarak değerlendirilmiştir",
                "emsaller arasında değerlendirilmiştir",
                "sorudaki hukuki sonuca olumlu",
                "sorudaki hukuki sonuca olumsuz",
            ]
        )

        if summary and not too_generic and summary not in reason_snippets:
            reason_snippets.append(summary)

    if final_direction == "yes":
        main_sentence = (
            "Bulunan emsal kararlar, bu soruya genel olarak “evet” cevabının verilebileceğini gösteriyor."
        )
    elif final_direction == "no":
        main_sentence = (
            "Bulunan emsal kararlar, bu soruya genel olarak “hayır” cevabının verilebileceğini gösteriyor."
        )
    else:
        main_sentence = (
            "Bulunan kararlar soruyla bağlantılı görünse de tek başına net bir evet/hayır sonucu vermiyor."
        )

    if reason_snippets:
        reason_sentence = "Öne çıkan gerekçe şu şekilde özetlenebilir: " + " ".join(reason_snippets[:2])
    else:
        reason_sentence = ""

    if confidence.get("status") == "weak":
        confidence_sentence = (
            "Eşleşme gücü zayıf olduğu için bu sonuç dikkatli değerlendirilmelidir."
        )
    elif confidence.get("status") == "uncertain":
        confidence_sentence = (
            "Kararlar arasında tam birlik olmadığı için sonuç ihtiyatlı yorumlanmalıdır."
        )
    else:
        confidence_sentence = (
            "Eşleşen kararlar genel olarak aynı yönde görünüyor."
        )

    if source_labels:
        sources_sentence = (
            "Bu değerlendirme özellikle "
            + " ve ".join(source_labels[:2])
            + " kararları dikkate alınarak oluşturuldu."
        )
    else:
        sources_sentence = (
            "Bu değerlendirme, listelenen kararların otomatik analiziyle oluşturuldu."
        )

    disclaimer_sentence = (
        "Bu metin bilgilendirme amaçlı otomatik bir taslaktır; kesin hukuki görüş yerine geçmez."
    )

    parts = [
        main_sentence,
        reason_sentence,
        confidence_sentence,
        sources_sentence,
        disclaimer_sentence,
    ]

    return " ".join(part for part in parts if part)

def build_final_answer(
    question: str,
    parsed: dict,
    final_direction: str,
    confidence: dict,
    final_items: list | None = None,
):
    return build_deterministic_commentary(
        question=question,
        parsed=parsed,
        final_direction=final_direction,
        confidence=confidence,
        final_items=final_items,
    )


# =========================
# ASK/FIND SERIALIZER
# =========================
def serialize_ask_items_with_summaries(final_items: list, parsed: dict):
    parsed_by_rank = {}

    if parsed and isinstance(parsed.get("decisions"), list):
        for d in parsed["decisions"]:
            rank = safe_int(d.get("rank", 0), 0)
            if rank > 0:
                parsed_by_rank[rank] = d

    response_items = []

    for rank, item in enumerate(final_items, start=1):
        payload = item.get("payload", {})
        parsed_decision = parsed_by_rank.get(rank, {})

        relation = normalize_relation_label(parsed_decision.get("relation", "unclear"))
        summary = build_safe_decision_summary(parsed_decision, relation,payload)
        relevance = build_card_relevance_text(relation)

        response_items.append(
            {
                "final_score": float(item.get("final_score", 0.0)),
                "relation": relation,
                "summary": summary,
                "relevance": relevance,
                "payload": {
                    "court": str(payload.get("court", "")),
                    "case_no": str(payload.get("case_no", "")),
                    "decision_no": str(payload.get("decision_no", "")),
                    "decision_date": str(payload.get("decision_date", "")),
                    "folder": str(payload.get("folder", "")),
                    "summary": summary,
                    "relevance": relevance,
                    "relation": relation,
                    "text": "",
                },
            }
        )

    return response_items
def sort_items_by_final_direction(response_items: list, final_direction: str):
    if final_direction == "yes":
        target = "supports_yes"
        opposite = "supports_no"
    elif final_direction == "no":
        target = "supports_no"
        opposite = "supports_yes"
    else:
        target = None
        opposite = None

    def sort_key(item):
        relation = normalize_relation_label(item.get("relation", "unclear"))
        score = safe_float(item.get("final_score", 0.0))

        if target and relation == target:
            group = 0
        elif relation in {"unclear", "procedural"}:
            group = 1
        elif relation == "irrelevant":
            group = 2
        elif opposite and relation == opposite:
            group = 3
        else:
            group = 4

        return (group, -score)

    return sorted(response_items, key=sort_key)
def clean_decision_text_for_summary(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" .", ".").replace(" :", ":")
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = clean_decision_text_for_summary(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def find_sentence_containing(sentences: list[str], keywords: list[str]) -> str:
    lowered_keywords = [k.lower() for k in keywords]

    for sentence in sentences:
        s = sentence.lower()
        if any(k in s for k in lowered_keywords):
            return sentence.strip()

    return ""


def shorten_text(text: str, max_len: int = 360) -> str:
    text = clean_decision_text_for_summary(text)

    if len(text) <= max_len:
        return text

    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut.strip() + "..."


def extract_case_subject_from_text(text: str) -> str:
    text = clean_decision_text_for_summary(text)
    sentences = split_sentences(text)

    # En güvenli yer genelde "Dava, ... ilişkindir." cümlesi.
    subject_sentence = find_sentence_containing(
        sentences,
        [
            "dava,",
            "istemine ilişkindir",
            "talebine ilişkindir",
            "uyuşmazlık",
            "itirazın kaldırılması",
            "tahliye",
            "ödeme emri",
            "kira alacağı",
            "tazminat",
            "işçilik alacağı",
            "kamulaştırma",
            "idari para cezası",
        ],
    )

    if subject_sentence:
        return shorten_text(subject_sentence, 300)

    # "DAVA :" ile "KARAR :" arası bazen konu bilgisini taşır.
    match = re.search(
        r"DAVA\s*:\s*(.*?)(KARAR\s*:|GEREĞİ DÜŞÜNÜLDÜ|Dosya incelendi)",
        text,
        flags=re.IGNORECASE,
    )

    if match:
        return shorten_text(match.group(1), 300)

    return ""


def extract_decision_result_from_text(text: str) -> str:
    text = clean_decision_text_for_summary(text)
    sentences = split_sentences(text)

    result_keywords = [
        "bozulmasına",
        "onanmasına",
        "reddine",
        "kabulüne",
        "karar verilmiştir",
        "karar verilmesine",
        "eksik inceleme",
        "yeniden değerlendirilmesi",
        "bilirkişiden ek rapor",
        "sonucuna göre karar verilmesi",
    ]

    # Önce SONUÇ kısmından yakalamaya çalış.
    sonuc_match = re.search(r"SONUÇ\s*:\s*(.*)$", text, flags=re.IGNORECASE)

    if sonuc_match:
        sonuc_text = sonuc_match.group(1)
        sonuc_sentences = split_sentences(sonuc_text)

        sentence = find_sentence_containing(sonuc_sentences, result_keywords)
        if sentence:
            return shorten_text(sentence, 320)

        if sonuc_sentences:
            return shorten_text(sonuc_sentences[0], 320)

    # SONUÇ yoksa genel metinde sonuç cümlesi ara.
    sentence = find_sentence_containing(sentences, result_keywords)
    if sentence:
        return shorten_text(sentence, 320)

    return ""


def build_find_summary_from_payload(payload: dict):
    raw_text = str(
        payload.get("text", "")
        or payload.get("full_text", "")
        or ""
    )

    court = str(payload.get("court", "")).strip()
    case_no = str(payload.get("case_no", "")).strip()
    decision_no = str(payload.get("decision_no", "")).strip()
    decision_date = str(payload.get("decision_date", "")).strip()

    label_parts = []
    if court:
        label_parts.append(court)
    if case_no:
        label_parts.append(f"E. {case_no}")
    if decision_no:
        label_parts.append(f"K. {decision_no}")
    if decision_date:
        label_parts.append(f"T. {decision_date}")

    label = " | ".join(label_parts)

    subject = extract_case_subject_from_text(raw_text)
    result = extract_decision_result_from_text(raw_text)

    if subject and result:
        return f"{subject} Kararda öne çıkan sonuç: {result}"

    if subject:
        return subject

    if result:
        return f"Kararda öne çıkan sonuç: {result}"

    if label:
        return f"Bu karar {label} bilgileriyle eşleşmiştir. Kararın ayrıntılı konusu için karar metni incelenmelidir."

    return "Bu karar arama bilgileriyle eşleşmiştir. Kararın ayrıntılı konusu için karar metni incelenmelidir."

def serialize_find_items(items: list, top_k: int = 10):
    response_items = []

    for item in items[:top_k]:
        payload = item.get("payload", {})

        summary = build_find_summary_from_payload(payload)
        relevance = "Bu karar, aradığın esas/karar numarası veya filtre bilgileriyle eşleşti."

        response_items.append(
            {
                "final_score": float(item.get("find_score", item.get("final_score", 0.0))),
                "relation": "metadata_match",
                "summary": summary,
                "relevance": relevance,
                "payload": {
                    "court": str(payload.get("court", "")),
                    "case_no": str(payload.get("case_no", "")),
                    "decision_no": str(payload.get("decision_no", "")),
                    "decision_date": str(payload.get("decision_date", "")),
                    "folder": str(payload.get("folder", "")),
                    "summary": summary,
                    "relevance": relevance,
                    "relation": "metadata_match",
                    "text": "",
                },
            }
        )

    return response_items

# =========================
# FIND YARDIMCILARI
# =========================
def extract_year_from_payload(payload: dict) -> str:
    year = str(payload.get("year", "")).strip()
    if year:
        return year

    decision_date = str(payload.get("decision_date", "")).strip()
    match = re.search(r"(19|20)\d{2}", decision_date)
    return match.group(0) if match else ""


def build_find_haystack(payload: dict) -> str:
    return normalize_text(
        " ".join(
            [
                str(payload.get("court", "")),
                str(payload.get("case_no", "")),
                str(payload.get("decision_no", "")),
                str(payload.get("decision_date", "")),
                str(payload.get("folder", "")),
                str(payload.get("title", "")),
                str(payload.get("text", ""))[:1500],
            ]
        )
    )


def extract_legal_numbers(text: str) -> list[str]:
    normalized = normalize_text(text)
    return re.findall(r"\b\d{4}/\d+\b", normalized)


def metadata_match_score(payload: dict, query: str, filters: dict) -> float:
    score = 0.0

    case_no = normalize_text(str(payload.get("case_no", "")))
    decision_no = normalize_text(str(payload.get("decision_no", "")))
    court = normalize_text(str(payload.get("court", "")))
    year = extract_year_from_payload(payload)

    query_norm = normalize_text(query)
    query_numbers = extract_legal_numbers(query_norm)

    filter_number = normalize_text(str(filters.get("number", "")).strip())
    filter_court = normalize_text(str(filters.get("court", "")).strip())
    filter_year = str(filters.get("year", "")).strip()

    if filter_number:
        if filter_number == case_no:
            score += 10.0
        elif filter_number == decision_no:
            score += 9.0
        elif filter_number in f"{case_no} {decision_no}".strip():
            score += 6.0

    if filter_court:
        if filter_court == court:
            score += 4.0
        elif filter_court in court:
            score += 2.5

    if filter_year:
        if filter_year == year:
            score += 2.0

    for qn in query_numbers:
        if qn == case_no:
            score += 6.0
        elif qn == decision_no:
            score += 5.0
        elif qn in f"{case_no} {decision_no}".strip():
            score += 3.0

    return score


def matches_find_filters(payload: dict, query: str, filters: dict) -> bool:
    clean_query = normalize_text(query)
    query_tokens = [t for t in clean_query.split() if len(t) > 2]

    year_filter = str(filters.get("year", "")).strip()
    court_filter = normalize_text(str(filters.get("court", "")).strip())
    number_filter = normalize_text(str(filters.get("number", "")).strip())

    haystack = build_find_haystack(payload)
    year_text = extract_year_from_payload(payload)
    case_no = normalize_text(str(payload.get("case_no", "")))
    decision_no = normalize_text(str(payload.get("decision_no", "")))
    number_text = f"{case_no} {decision_no}".strip()
    court_text = normalize_text(str(payload.get("court", "")))

    match_query = True
    if clean_query:
        if clean_query in haystack or clean_query == case_no or clean_query == decision_no:
            match_query = True
        else:
            matched = sum(1 for token in query_tokens if token in haystack)
            match_query = matched >= max(1, min(2, len(query_tokens)))

    match_year = not year_filter or year_filter == year_text
    match_court = not court_filter or court_filter in court_text

    match_number = True
    if number_filter:
        match_number = (
            number_filter == case_no
            or number_filter == decision_no
            or number_filter in number_text
        )

    return match_query and match_year and match_court and match_number


def score_find_item(item: dict, query: str, filters: dict) -> float:
    payload = item.get("payload", {})
    haystack = build_find_haystack(payload)
    clean_query = normalize_text(query)
    query_tokens = [t for t in clean_query.split() if len(t) > 2]

    base_score = float(item.get("final_score", item.get("hybrid_score", 0.0)))
    meta_score = metadata_match_score(payload, query, filters)
    score = base_score + meta_score

    case_no = normalize_text(str(payload.get("case_no", "")))
    decision_no = normalize_text(str(payload.get("decision_no", "")))
    number_text = f"{case_no} {decision_no}".strip()

    if clean_query:
        if clean_query == case_no or clean_query == decision_no:
            score += 1.2
        elif clean_query in haystack:
            score += 0.35

    if query_tokens:
        matched = sum(1 for token in query_tokens if token in haystack)
        score += matched * 0.03

    year_filter = str(filters.get("year", "")).strip()
    court_filter = normalize_text(str(filters.get("court", "")).strip())
    number_filter = normalize_text(str(filters.get("number", "")).strip())

    year_text = extract_year_from_payload(payload)
    court_text = normalize_text(str(payload.get("court", "")))

    if year_filter and year_filter == year_text:
        score += 0.25

    if court_filter and court_filter in court_text:
        score += 0.25

    if number_filter:
        if number_filter == case_no or number_filter == decision_no:
            score += 1.5
        elif number_filter in number_text:
            score += 0.40

    return score


# =========================
# ANA ASK AKIŞI
# =========================
def run_ask_pipeline(question: str) -> dict:
    print("\n" + "=" * 100)
    print("ASK PIPELINE BAŞLADI")
    print("SORU:", question)

    candidates, search_queries = retrieve_candidates_with_rrf(question)
    print("-" * 100)
    print("SEARCH QUERIES:")
    for i, q in enumerate(search_queries, start=1):
        print(f"[{i}] {q}")
    print("TOPLAM ADAY:", len(candidates))

    candidate_pool, query_terms, query_phrases = hybrid_candidate_scoring(
        user_question=question,
        search_queries=search_queries,
        candidates=candidates,
    )

    print("-" * 100)
    print("RERANK HAVUZU:", len(candidate_pool))
    print("QUERY TERMS:", query_terms[:10])
    print("QUERY PHRASES:", query_phrases[:6])

    final_items = cross_encoder_rerank(question, candidate_pool)
    confidence = assess_confidence(final_items)

    print("-" * 100)
    print("FINAL ITEMS (ilk 5):")
    if not final_items:
        print("Hiç sonuç yok.")
    else:
        for i, item in enumerate(final_items, start=1):
            payload = item.get("payload", {})
            print(
                f"[{i}] skor={item.get('final_score', 0.0):.3f} | "
                f"{payload.get('court', '')} | "
                f"E. {payload.get('case_no', '')} | "
                f"K. {payload.get('decision_no', '')} | "
                f"alan={payload.get('folder', '')}"
            )
            print("metin:", str(payload.get("text", ""))[:250])
            print("-" * 60)

    evidence = build_raw_evidence(final_items)
    raw_evidence_text = format_raw_evidence(evidence)

    parsed, raw_llm_output = interpret_with_llm(
        question=question,
        raw_evidence_text=raw_evidence_text,
        evidence=evidence,
        confidence_reason=confidence["reason"],
    )

    print("-" * 100)
    print("LLM PARSED DECISIONS:")
    for d in parsed.get("decisions", []):
        print(
            f"rank={d.get('rank')} | relation={d.get('relation')} | "
            f"holding={d.get('holding')}"
        )

    confidence = assess_confidence(final_items, parsed)
    final_direction = decide_final_direction(parsed)
    final_answer = build_final_answer(
        question=question,
        parsed=parsed,
        final_direction=final_direction,
        confidence=confidence,
        final_items=final_items,
    )

    print("-" * 100)
    print("CONFIDENCE:", confidence)
    print("FINAL DIRECTION:", final_direction)
    print("FINAL ANSWER:", final_answer)
    print("=" * 100 + "\n")

    response_items = serialize_ask_items_with_summaries(final_items, parsed)
    response_items = sort_items_by_final_direction(response_items, final_direction)

    return {
    "mode": "ask",
    "final_answer": final_answer,
    "confidence": confidence,
    "final_direction": final_direction,
    "final_items": response_items,
}


# =========================
# ANA FIND AKIŞI
# =========================
def run_find_pipeline(query: str, filters: dict | None = None) -> dict:
    filters = filters or {}
    query = compact_text(query)

    print("\n" + "=" * 100)
    print("FIND PIPELINE BAŞLADI")
    print("QUERY:", query)
    print("FILTERS:", filters)

    all_items = scroll_candidates(limit=50000)

    metadata_ranked = []
    for item in all_items:
        payload = item.get("payload", {})
        score = metadata_match_score(payload, query, filters)

        if score > 0:
            clone = {
                "final_score": item.get("final_score", 0.0),
                "payload": payload,
                "find_score": score,
            }
            metadata_ranked.append(clone)

    metadata_ranked.sort(key=lambda x: x.get("find_score", 0.0), reverse=True)

    exact_items = [
        item for item in metadata_ranked
        if matches_find_filters(item.get("payload", {}), query, filters)
    ]

    semantic_items = []
    if len(exact_items) < 5 and query:
        candidates, search_queries = retrieve_candidates_with_rrf(query)
        candidate_pool, _, _ = hybrid_candidate_scoring(
            user_question=query,
            search_queries=search_queries,
            candidates=candidates,
        )
        semantic_items = cross_encoder_rerank(query, candidate_pool, top_k=25)

    merged = OrderedDict()

    for item in exact_items:
        payload = item.get("payload", {})
        key = (
            str(payload.get("court", "")),
            str(payload.get("case_no", "")),
            str(payload.get("decision_no", "")),
        )
        merged[key] = item

    for item in semantic_items:
        payload = item.get("payload", {})
        key = (
            str(payload.get("court", "")),
            str(payload.get("case_no", "")),
            str(payload.get("decision_no", "")),
        )

        if key in merged:
            continue

        if matches_find_filters(payload, query, filters):
            item["find_score"] = score_find_item(item, query, filters)
            merged[key] = item

    if not merged:
        relaxed = []

        for item in all_items:
            payload = item.get("payload", {})

            if matches_find_filters(payload, "", filters):
                clone = {
                    "final_score": item.get("final_score", 0.0),
                    "payload": payload,
                }
                clone["find_score"] = score_find_item(clone, query, filters)
                relaxed.append(clone)

        relaxed.sort(key=lambda x: x.get("find_score", 0.0), reverse=True)

        for item in relaxed:
            payload = item.get("payload", {})
            key = (
                str(payload.get("court", "")),
                str(payload.get("case_no", "")),
                str(payload.get("decision_no", "")),
            )
            merged[key] = item

    final_items = list(merged.values())
    final_items.sort(key=lambda x: x.get("find_score", 0.0), reverse=True)

    print("FIND RESULT COUNT:", len(final_items))
    for i, item in enumerate(final_items[:10], start=1):
        payload = item.get("payload", {})
        print(
            f"[{i}] skor={item.get('find_score', 0.0):.3f} | "
            f"{payload.get('court', '')} | "
            f"E. {payload.get('case_no', '')} | "
            f"K. {payload.get('decision_no', '')} | "
            f"alan={payload.get('folder', '')}"
        )

    print("=" * 100 + "\n")

    return {
        "mode": "find",
        "query": query,
        "filters": filters,
        "final_items": serialize_find_items(final_items, top_k=10),
    }
import json
import os
import re
import time


from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

from app.core.config import LLM_MAX_RETRIES
from app.services.helpers import (
    compact_text,
    fallback_relation_from_text,
    normalize_relation_label,
    parse_json_block,
    safe_int,
)


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# =========================
# GEMINI CLIENT
# =========================
def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY bulunamadı. backend/.env içine GEMINI_API_KEY ekle."
        )

    return genai.Client(api_key=api_key)


# =========================
# YORUMLAMA PROMPT'U
# =========================
def build_interpretation_prompt(question: str, raw_evidence_text: str, confidence_reason: str):
    return f"""
Sen Türk hukuk kararlarını analiz eden dikkatli ve temkinli bir hukuk asistanısın.

Görev:
Kullanıcı sorusunu merkeze alarak aşağıdaki kararları değerlendir.
Her karar için sadece karar metninde açıkça görülen bilgiye dayan.
Dış bilgi kullanma.
Kanun maddesi uydurma.
Karar metninde görünmeyen somut olay bilgisi ekleme.
JSON dışında hiçbir şey yazma.

EN ÖNEMLİ ANLAM KURALI:
- supports_yes = karar, kullanıcının sorduğu soruya "EVET" cevabını destekliyor.
- supports_no = karar, kullanıcının sorduğu soruya "HAYIR" cevabını destekliyor.
- Bu etiketler davacının kazanması/kaybetmesi anlamına GELMEZ.
- "Dava kabul edildi" otomatik olarak supports_yes değildir.
- "Dava reddedildi" otomatik olarak supports_no değildir.
- Her zaman kullanıcının soru cümlesindeki fiile göre düşün.

Örnek:
Soru: "Bağ-Kur borcu gerekçe gösterilerek SSK aylığı engellenebilir mi?"
- supports_yes = engellenebilir.
- supports_no = engellenemez.

Örnek:
Soru: "Yeni malik ihtar çekmeden tahliye davası açabilir mi?"
- supports_yes = ihtar çekmeden açabilir.
- supports_no = ihtar/bildirim şartı nedeniyle açamaz veya risklidir.

Örnek:
Soru: "İdari para cezası kesinleşmeden ödeme emri düzenlenebilir mi?"
- supports_yes = düzenlenebilir.
- supports_no = kesinleşmeden düzenlenemez.

ÇOK ÖNEMLİ:
- Karar, kullanıcının sorusundaki hukuki konuya doğrudan temas etmiyorsa "irrelevant" seç.
- Aynı hukuk alanından görünse bile sorudaki somut meseleye cevap vermiyorsa "unclear" veya "irrelevant" seç.
- Kullanıcı sorusu SGK/emeklilik/prim/Bağ-Kur ise; tazminat, kira, ihale, işçilik, ceza gibi farklı konulardaki kararları ilgili gibi gösterme.
- Kullanıcı sorusu kira/tahliye ise; SGK, işçilik, ihale, kamulaştırma gibi farklı konuları ilgili gibi gösterme.
- Kullanıcı sorusu icra/ödeme emri ise; konuyla ilgisiz tazminat/kira/işçilik kararlarını destek karar gibi yazma.
- Karar metninden net sonuç çıkmıyorsa "unclear" seç.
- Sadece kararın gerçekten söylediği şeyi özetle.
- Raw metni kopyalama; anlamlandırılmış kısa özet yaz.
- Kişi adı, adres, T.C. kimlik no gibi gereksiz kişisel verileri tekrar etme.

Her karar için relation seçenekleri:
- supports_yes
- supports_no
- procedural
- irrelevant
- unclear

Kısa anlam:
- supports_yes: karar kullanıcının sorusuna evet cevabını destekliyor
- supports_no: karar kullanıcının sorusuna hayır cevabını destekliyor
- procedural: karar daha çok usul, görev, süre, yetki veya inceleme meselesi içeriyor
- irrelevant: karar soru ile zayıf/alakasız
- unclear: ilgili olabilir ama net evet/hayır yönü çıkmıyor

Holding yazım kuralları:
- holding alanı kararın kullanıcı sorusuyla ilişkisini anlatan profesyonel kısa özet olsun.
- En fazla 2 kısa cümle yaz.
- Holding içinde "davacı kazandı", "dava reddedildi" gibi ifadeleri tek başına sonuç gibi kullanma.
- Mutlaka kullanıcının sorusuna göre sonucu ifade et.
- Eğer karar alakasızsa holding alanında bunu açıkça söyle.
- "kararı soruya hayır yönünde yakın görünüyor" gibi kaba şablon yazma.
- "tek cümlelik net karar özeti" gibi ifadeler kullanma.
- "sorudaki talep veya savunma" gibi muğlak ifadeler kullanma.
- Kararda açıkça görülmeyen hukuki sonuç çıkarma.

Çıktı biçimi:
{{
  "decisions": [
    {{
      "rank": 1,
      "relation": "supports_no",
      "holding": "Karar, kullanıcının sorusundaki işlem bakımından yazılı bildirim şartının önemini vurgulamaktadır. Bu nedenle soruya hayır cevabını destekleyen bir emsal olarak değerlendirilmiştir."
    }}
  ]
}}

Kullanıcı sorusu:
{question}

Güven notu:
{confidence_reason}

Kararlar:
{raw_evidence_text}
""".strip()


# =========================
# LLM JSON ONARIM
# =========================
def build_json_repair_prompt(raw_output: str):
    return f"""
Aşağıdaki çıktıyı geçerli JSON'a çevir.
Sadece JSON döndür.
Açıklama yazma.
Markdown kullanma.

Şema:
{{
  "decisions": [
    {{
      "rank": 1,
      "relation": "supports_yes",
      "holding": "kararın kullanıcı sorusuna göre kısa ve somut değerlendirmesi"
    }}
  ]
}}

relation sadece şunlardan biri olabilir:
- supports_yes
- supports_no
- procedural
- irrelevant
- unclear

Anlam kuralı:
- supports_yes = kullanıcının sorduğu soruya EVET cevabını destekler.
- supports_no = kullanıcının sorduğu soruya HAYIR cevabını destekler.
- Davanın kabulü/reddi ile kullanıcının sorusuna evet/hayır cevabını karıştırma.

Şablon ifade kullanma.
"tek cümlelik net karar özeti" benzeri metinleri sil.
"sorudaki talep veya savunma" gibi muğlak ifadeleri kullanma.

Düzeltilmesi gereken çıktı:
{raw_output}
""".strip()


def normalize_one_decision(decision: dict):
    rank = safe_int(decision.get("rank", 0), 0)
    relation = normalize_relation_label(decision.get("relation", "unclear"))
    holding = compact_text(decision.get("holding", ""))

    bad_holdings = {
        "tek cümleli net karar özeti",
        "tek cümlelik net karar özeti",
        "tek cümlelik, sade, net karar özeti",
        "kararın somut kısa içeriği",
        "karardan net kısa özet üretilemedi.",
        "kısa karar özeti",
        "somut kısa özet",
    }

    bad_fragments = [
        "kararı soruya hayır yönünde yakın görünüyor",
        "kararı soruya evet yönünde yakın görünüyor",
        "kararı daha çok usuli değerlendirme içeriyor",
        "kararından net yön çıkarılamadı",
        "sorudaki talep veya savunma",
        "sorudaki talep veya hukuki sonuç",
        "talep veya savunma bakımından",
        "otomatik metin eşleşmesine dayandığı",
    ]

    holding_norm = holding.lower().strip(" .,:;!-")

    if (
        not holding
        or holding_norm in bad_holdings
        or ("tek cümle" in holding_norm and "özet" in holding_norm)
        or ("kısa" in holding_norm and "özet" in holding_norm and len(holding_norm) < 40)
        or ("somut" in holding_norm and "içerik" in holding_norm)
        or any(fragment in holding_norm for fragment in bad_fragments)
    ):
        holding = ""

    return {
        "rank": rank,
        "relation": relation,
        "holding": holding[:420],
    }


def build_fallback_json(question: str, evidence: list):
    decisions = []

    for e in evidence:
        relation = fallback_relation_from_text(question, e["text"])
        court = e.get("court", "")
        case_no = e.get("case_no", "")
        decision_no = e.get("decision_no", "")

        decision_label = compact_text(
            f"{court} E. {case_no} K. {decision_no}"
        )

        if relation == "supports_yes":
            holding = (
                f"{decision_label} kararı, kullanıcının sorduğu soruya evet cevabını destekleyebilecek emsaller arasında değerlendirilmiştir. "
                "Bu sonuç otomatik eşleşmeye dayandığı için somut olay bakımından ayrıca kontrol edilmelidir."
            )
        elif relation == "supports_no":
            holding = (
                f"{decision_label} kararı, kullanıcının sorduğu soruya hayır cevabını destekleyebilecek emsaller arasında değerlendirilmiştir. "
                "Bu sonuç otomatik eşleşmeye dayandığı için somut olay bakımından ayrıca kontrol edilmelidir."
            )
        elif relation == "procedural":
            holding = (
                f"{decision_label} kararı daha çok usul, görev, süre veya inceleme koşulları bakımından önem taşımaktadır. "
                "Bu nedenle kullanıcının sorusuna doğrudan evet/hayır cevabı üretmez."
            )
        elif relation == "irrelevant":
            holding = (
                f"{decision_label} kararının kullanıcı sorusuyla bağlantısı zayıf görülmüştür. "
                "Bu karar yalnızca sınırlı emsal değeriyle listelenmiştir."
            )
        else:
            holding = (
                f"{decision_label} kararı soruyla bağlantılı görünmekle birlikte net bir evet/hayır yönü üretmemektedir. "
                "Daha güçlü emsal kararlarla birlikte değerlendirilmelidir."
            )

        decisions.append(
            {
                "rank": e["rank"],
                "relation": relation,
                "holding": holding,
            }
        )

    return {"decisions": decisions}


def repair_and_complete_parsed(question: str, parsed: dict, evidence: list):
    fallback = build_fallback_json(question, evidence)
    by_rank = {}

    if isinstance(parsed, dict) and isinstance(parsed.get("decisions"), list):
        for d in parsed["decisions"]:
            if not isinstance(d, dict):
                continue

            nd = normalize_one_decision(d)

            if nd["rank"] > 0 and nd["rank"] <= len(evidence):
                by_rank[nd["rank"]] = nd

    for fd in fallback["decisions"]:
        if fd["rank"] not in by_rank:
            by_rank[fd["rank"]] = fd
        else:
            if not by_rank[fd["rank"]].get("holding"):
                by_rank[fd["rank"]]["holding"] = fd["holding"]

    return {"decisions": [by_rank[k] for k in sorted(by_rank.keys())]}


def call_gemini(prompt: str, use_json_format: bool = False, max_output_tokens: int = 700):
    client = get_gemini_client()

    config_kwargs = {
        "temperature": 0.0,
        "max_output_tokens": max_output_tokens,
    }

    if use_json_format:
        config_kwargs["response_mime_type"] = "application/json"

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    )

    return response.text or ""


def interpret_with_llm(
    question: str,
    raw_evidence_text: str,
    evidence: list,
    confidence_reason: str,
):
    prompt = build_interpretation_prompt(question, raw_evidence_text, confidence_reason)
    raw_attempts = []

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        use_json_format = attempt == 1

        try:
            raw = call_gemini(
                prompt,
                use_json_format=use_json_format,
                max_output_tokens=900,
            )
            raw_attempts.append(f"[ATTEMPT {attempt}]\n{raw}")

            parsed = parse_json_block(raw)

            if (
                parsed is not None
                and "decisions" in parsed
                and isinstance(parsed["decisions"], list)
            ):
                parsed = repair_and_complete_parsed(question, parsed, evidence)
                return parsed, raw

            repair_prompt = build_json_repair_prompt(raw)
            repaired_raw = call_gemini(
                repair_prompt,
                use_json_format=True,
                max_output_tokens=700,
            )
            raw_attempts.append(f"[REPAIR {attempt}]\n{repaired_raw}")

            repaired_parsed = parse_json_block(repaired_raw)

            if (
                repaired_parsed is not None
                and "decisions" in repaired_parsed
                and isinstance(repaired_parsed["decisions"], list)
            ):
                repaired_parsed = repair_and_complete_parsed(
                    question,
                    repaired_parsed,
                    evidence,
                )
                return repaired_parsed, repaired_raw

        except Exception as e:
            raw_attempts.append(f"[ATTEMPT {attempt}] Exception: {repr(e)}")

        time.sleep(0.4)

    fallback = build_fallback_json(question, evidence)

    return fallback, "\n\n".join(raw_attempts) if raw_attempts else "Fallback kullanıldı."


# =========================
# DİLEKÇE ÜRETİMİ
# =========================
def build_petition_prompt(
    petition_type: str,
    authority: str,
    applicant: str,
    opponent: str,
    event_summary: str,
    request_summary: str,
    extra_notes: str,
):
    return f"""
Sen Türk hukuk sistemine uygun, düzenli ve sade dilekçe taslakları hazırlayan bir hukuk asistanısın.

Görev:
Kullanıcının verdiği bilgilere göre profesyonel, anlaşılır ve düzenli bir dilekçe TASLAĞI oluştur.

Önemli kurallar:
- Uydurma kanun maddesi yazma.
- Kullanıcının vermediği somut bilgileri icat etme.
- Bilgi eksikse uygun yerlere [ ... ] şeklinde boşluk bırak.
- Dilekçe dili resmi ve sade olsun.
- Gereksiz uzun açıklama yapma.
- Sadece dilekçe metnini döndür.
- Markdown başlığı kullanma.
- "Elbette" gibi sohbet cümlesi yazma.

Dilekçe yapısı:
1. Hitap
2. Taraf bilgileri
3. Konu
4. Açıklamalar
5. Hukuki nedenler
6. Deliller
7. Sonuç ve talep
8. Tarih
9. İmza

Kullanıcı bilgileri:

Dilekçe türü:
{petition_type}

Mahkeme / kurum:
{authority}

Başvuran / davacı / talep eden:
{applicant}

Karşı taraf / davalı / muhatap:
{opponent}

Olay özeti:
{event_summary}

Talep:
{request_summary}

Ek notlar:
{extra_notes}
""".strip()


def clean_petition_text(text: str):
    text = str(text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_petition_with_llm(
    petition_type: str,
    authority: str,
    applicant: str,
    opponent: str,
    event_summary: str,
    request_summary: str,
    extra_notes: str,
):
    prompt = build_petition_prompt(
        petition_type=petition_type,
        authority=authority,
        applicant=applicant,
        opponent=opponent,
        event_summary=event_summary,
        request_summary=request_summary,
        extra_notes=extra_notes,
    )

    raw_text = call_gemini(
        prompt,
        use_json_format=False,
        max_output_tokens=1800,
    )

    petition_text = clean_petition_text(raw_text)

    return {
        "mode": "petition",
        "petition_text": petition_text,
    }
# =========================
# BELGE OKU / GEMINI VISION
# =========================

DOCUMENT_OCR_WARNING = (
    "OCR çıktısı otomatik üretilmiştir. Görsel kalitesi, ışık, açı veya yazı tipi nedeniyle "
    "hatalı ya da eksik olabilir. Lütfen metni kullanmadan önce mutlaka kontrol edin."
)

DOCUMENT_EXPLAIN_WARNING = (
    "Bu açıklama hukuki danışmanlık değildir. Yapay zekâ tarafından sadeleştirilmiş bir ön "
    "değerlendirmedir. Süre, itiraz, dava veya başvuru gibi işlemler için bir avukattan ya da "
    "yetkili kurumdan destek alınmalıdır."
)

DOCUMENT_PRIVACY_NOTE = (
    "Bu belge kişisel veri içerebilir. T.C. kimlik numarası, adres, telefon, dosya numarası "
    "ve özel bilgiler paylaşılırken dikkatli olunmalıdır."
)
class TemporaryLLMServiceError(RuntimeError):
    pass


class LLMFormatError(RuntimeError):
    pass


def is_temporary_llm_error(error: Exception):
    message = repr(error).lower()

    temporary_markers = [
        "503",
        "unavailable",
        "service unavailable",
        "overloaded",
        "temporarily",
        "try again",
        "deadline",
        "timeout",
        "timed out",
        "resource_exhausted",
        "rate limit",
        "429",
    ]

    return any(marker in message for marker in temporary_markers)

def build_document_ocr_prompt(document_type: str):
    return f"""
Sen dikkatli bir Türkçe OCR asistanısın.

Görev:
Kullanıcının yüklediği belge görselindeki metni mümkün olduğunca aynen çıkar.

Belge türü:
{document_type or "Diğer"}

Kurallar:
- Sadece görselde gördüğün metni yaz.
- Özetleme yapma.
- Hukuki yorum yapma.
- Metinde olmayan bilgi ekleme.
- Tahmin ederek kanun maddesi, tarih, isim, numara veya kurum adı uydurma.
- Okuyamadığın yerleri [okunamadı] olarak işaretle.
- Emin olmadığın kısa parçaları [?] ile işaretle.
- Sayfa düzenini mümkün olduğunca koru.
- Başlıkları, numaraları, tarihleri ve imza bölümlerini ayrı satırlarda tut.
- Kişisel verileri değiştirme veya maskeleme; sadece belgede görünen metni çıkar.
- Cevabın başına "OCR sonucu" gibi açıklama ekleme.
- Markdown kod bloğu kullanma.

Çıktı:
Yalnızca çıkarılan belge metni.
""".strip()


def clean_ocr_text(text: str):
    text = str(text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def extract_text_from_image_with_gemini(
    image_bytes: bytes,
    mime_type: str,
    document_type: str = "Diğer",
):
    if not image_bytes:
        raise RuntimeError("Görsel verisi boş.")

    client = get_gemini_client()
    prompt = build_document_ocr_prompt(document_type)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type,
                ),
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=3500,
            ),
        )
    except Exception as e:
        if is_temporary_llm_error(e):
            raise TemporaryLLMServiceError(
                "Gemini OCR servisi şu anda geçici olarak yanıt veremiyor. Lütfen biraz sonra tekrar deneyin."
            ) from e

        raise

    extracted_text = clean_ocr_text(response.text or "")

    if not extracted_text:
        raise RuntimeError("Gemini görselden okunabilir metin çıkaramadı.")

    return extracted_text
def build_document_explain_prompt(text: str, document_type: str):
    return f"""
Sen Türkçe hukuki belgeleri sade dille açıklayan dikkatli bir hukuk asistanısın.

Görev:
Kullanıcının verdiği OCR metnini sade, somut ve anlaşılır dille açıkla.

Belge türü:
{document_type or "Diğer"}

Kurallar:
- Bu bir hukuki danışmanlık değildir.
- Belgedeki somut bilgileri kullan: mahkeme/kurum, belge türü, tarih, konu, talep, ceza, itiraz, duruşma, süre gibi görünen noktaları ayıkla.
- Genel ve boş ifadeler yazma.
- Metinde açıkça yazmayan bilgiyi uydurma.
- Kanun maddesi uydurma.
- Kesin hak kaybı veya kesin süre varmış gibi konuşma; metinde süre varsa kontrol edilmesi gerektiğini belirt.
- Kişisel verileri gereksiz yere tekrar etme.
- OCR hatası olabileceğini dikkate al.
- Kullanıcıya panik yaptırma; temkinli, sade ve yol gösterici anlat.
- Olası adımları kesin emir gibi değil, kontrol edilebilecek seçenekler gibi yaz.
- Sadece geçerli JSON döndür.
- Markdown kullanma.
- JSON dışında hiçbir açıklama yazma.
- Kişinin telefon, adres, T.C. kimlik numarası veya avukat iletişim bilgilerini olası adım olarak yazma.
- Olası adımlar belgeye özel kontrol listesi gibi olsun: tarih, süre, tebliğ, dosya/karar numarası, itiraz edilen işlem, ekler.
- "Doğrulayın" gibi genel ifadeleri azalt; bunun yerine neyin neden kontrol edileceğini söyle.

JSON şeması:
{{
  "plain_explanation": "Belgenin sade dille 4-7 cümlelik açıklaması.",
  "important_points": [
    "Belgeye özel önemli nokta 1",
    "Belgeye özel önemli nokta 2",
    "Belgeye özel önemli nokta 3"
  ],
  "possible_actions": [
    "Kontrol edilebilecek olası adım 1",
    "Kontrol edilebilecek olası adım 2",
    "Kontrol edilebilecek olası adım 3"
  ]
}}

Liste kuralları:
- important_points en az 3, en fazla 7 madde olsun.
- possible_actions en az 3, en fazla 6 madde olsun.
- Her madde belgeye özel olsun.
- Genel OCR uyarılarını madde listelerini doldurmak için kullanma.

OCR metni:
{text}
""".strip()


def build_document_explain_repair_prompt(raw_output: str):
    return f"""
Aşağıdaki çıktıyı geçerli JSON formatına düzelt.

Kurallar:
- Sadece JSON döndür.
- Markdown kullanma.
- JSON dışında açıklama yazma.
- Eğer metin yarım kalmışsa anlamlı şekilde tamamla.
- Listeler belgeye özel, somut ve kullanışlı olsun.
- Genel OCR uyarılarını liste maddesi olarak tekrar etme.

Şema:
{{
  "plain_explanation": "Belgenin sade dille açıklaması",
  "important_points": [
    "Belgeye özel önemli nokta"
  ],
  "possible_actions": [
 "Belgede görünen tarih/süre/tebliğ bilgisinin kontrol edilmesi gibi somut olası adım 1",
  "İtiraz edilen karar, tutanak veya işlem bilgisinin kontrol edilmesi gibi somut olası adım 2",
  "Eksik belge/ek/vekalet veya başvuru bilgisi varsa kontrol edilmesi gibi somut olası adım 3"
  ]
}}

Düzeltilecek çıktı:
{raw_output}
""".strip()


def _safe_text_list(value, max_items: int = 6):
    if not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        text = compact_text(item)

        if text:
            cleaned.append(text[:360])

        if len(cleaned) >= max_items:
            break

    return cleaned


def parse_document_explanation_json(raw_text: str):
    raw_text = str(raw_text or "").strip()

    if not raw_text:
        return None

    parsed = parse_json_block(raw_text)

    if isinstance(parsed, dict):
        return parsed

    cleaned = clean_ocr_text(raw_text)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    first = cleaned.find("{")
    last = cleaned.rfind("}")

    if first != -1 and last != -1 and last > first:
        candidate = cleaned[first : last + 1]

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return None


def normalize_document_explanation(parsed: dict):
    if not isinstance(parsed, dict):
        raise LLMFormatError(
            "Gemini belge açıklamasını beklenen JSON formatında döndürmedi. Lütfen tekrar deneyin."
        )

    plain_explanation = compact_text(parsed.get("plain_explanation", ""))
    important_points = _safe_text_list(parsed.get("important_points"), max_items=7)
    possible_actions = _safe_text_list(parsed.get("possible_actions"), max_items=6)

    if not plain_explanation:
        raise LLMFormatError(
            "Gemini belge açıklamasını eksik döndürdü. Lütfen tekrar deneyin."
        )

    if not important_points:
        important_points = [
            "Gemini önemli noktaları ayrı liste halinde döndürmedi. OCR metnini kontrol edip tekrar deneyebilirsiniz."
        ]

    if not possible_actions:
        possible_actions = [
            "Gemini olası adımları ayrı liste halinde döndürmedi. Belge metnini kontrol edip tekrar deneyebilirsiniz."
        ]

    return {
        "plain_explanation": plain_explanation[:1800],
        "important_points": important_points,
        "possible_actions": possible_actions,
    }


def explain_document_text_with_llm(text: str, document_type: str = "Diğer"):
    clean_text = clean_ocr_text(text)

    if len(clean_text) < 10:
        raise RuntimeError("Açıklama için yeterli metin yok.")

    prompt = build_document_explain_prompt(
        text=clean_text[:7000],
        document_type=document_type,
    )

    last_error = None

    for attempt in range(1, 4):
        try:
            raw = call_gemini(
                prompt,
                use_json_format=True,
                max_output_tokens=1600,
            )

            parsed = parse_document_explanation_json(raw)

            if isinstance(parsed, dict):
                return normalize_document_explanation(parsed)

            repair_prompt = build_document_explain_repair_prompt(raw)

            repaired_raw = call_gemini(
                repair_prompt,
                use_json_format=True,
                max_output_tokens=1200,
            )

            repaired_parsed = parse_document_explanation_json(repaired_raw)

            if isinstance(repaired_parsed, dict):
                return normalize_document_explanation(repaired_parsed)

            last_error = LLMFormatError(
                "Gemini belge açıklamasını beklenen JSON formatında döndürmedi."
            )

        except Exception as e:
            last_error = e

            if not is_temporary_llm_error(e):
                time.sleep(0.4 * attempt)
            else:
                time.sleep(0.9 * attempt)

    if last_error and is_temporary_llm_error(last_error):
        raise TemporaryLLMServiceError(
            "Gemini açıklama servisi şu anda geçici olarak yanıt veremiyor. Lütfen biraz sonra tekrar deneyin."
        ) from last_error

    if isinstance(last_error, LLMFormatError):
        raise last_error

    raise RuntimeError("Belge açıklaması üretilemedi. Lütfen tekrar deneyin.") from last_error
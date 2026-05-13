import json
import math
import re
import unicodedata

MAX_EVIDENCE_TEXT = 3200

STOP_WORDS = {
    "ve", "veya", "ile", "icin", "için", "gibi", "daha", "çok", "az",
    "bir", "bu", "şu", "o", "da", "de", "mi", "mı", "mu", "mü",
    "ben", "bana", "benim", "biz", "siz", "onlar",
    "olarak", "neden", "nasıl", "ne", "hangi", "acaba",
    "sonra", "önce", "göre", "diye", "ki", "ya", "ama",
    "olan", "olur", "oluyor", "olmuş", "mümkün", "var", "yok",
    "ettim", "etti", "edildi", "eder", "edebilir", "istiyorum",
    "istemiştim", "çıktı", "olduğu", "ortaya", "durumda",
    "böyle", "şekilde", "sonradan", "şeyim", "söylendi",
    "hemen", "varsa", "olabilir", "gerekir",
    "karşı", "taraftan", "beni", "benden", "bizim",
}

GENERIC_TITLES = {"yargi", "yargı", "is", "an", "karar", "özet"}


def safe_turkish_lower(text: str) -> str:
    text = str(text)
    tr_map = str.maketrans(
        {
            "I": "ı",
            "İ": "i",
            "Ş": "ş",
            "Ğ": "ğ",
            "Ü": "ü",
            "Ö": "ö",
            "Ç": "ç",
        }
    )
    text = text.translate(tr_map).lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.replace("\u0307", "")
    text = unicodedata.normalize("NFC", text)
    return text


def normalize_text(text: str) -> str:
    text = safe_turkish_lower(text)
    text = text.replace("â", "a").replace("î", "i").replace("û", "u")
    text = re.sub(r"[^\wçğıöşü\s/.-]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def clip_text(text: str, max_chars: int = MAX_EVIDENCE_TEXT) -> str:
    return compact_text(text)[:max_chars]


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def clean_title_for_scoring(title: str) -> str:
    norm = normalize_text(title)
    if norm in GENERIC_TITLES:
        return ""
    return str(title).strip()


def build_metadata_text(payload: dict) -> str:
    parts = [
        str(payload.get("folder", "")),
        str(payload.get("subdomain", "")),
        str(payload.get("court", "")),
        str(clean_title_for_scoring(payload.get("title", ""))),
        str(payload.get("year", "")),
        str(payload.get("case_no", "")),
        str(payload.get("decision_no", "")),
    ]
    return " | ".join([p for p in parts if str(p).strip()]).strip()


def tokenize_for_bm25(text: str):
    t = normalize_text(text)
    words = re.findall(r"\b[\wçğıöşü]+\b", t, flags=re.IGNORECASE)
    return [w for w in words if len(w) >= 2 and w not in STOP_WORDS]


def extract_query_terms(question: str):
    words = tokenize_for_bm25(question)
    seen = set()
    out = []

    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)

    return out[:20]


def extract_query_phrases(question: str):
    words = tokenize_for_bm25(question)
    phrases = []
    seen = set()

    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i + 1]}"
        if phrase not in seen:
            seen.add(phrase)
            phrases.append(phrase)

    return phrases[:12]


def token_match_count(doc_text: str, query_terms: list):
    doc_words = set(tokenize_for_bm25(doc_text))
    return sum(1 for t in query_terms if t in doc_words)


def phrase_match_count(doc_text: str, query_phrases: list):
    doc = normalize_text(doc_text)
    return sum(1 for p in query_phrases if p in doc)


def minmax_normalize(values):
    if not values:
        return []

    vals = [float(v) for v in values]
    mn = min(vals)
    mx = max(vals)

    if math.isclose(mn, mx):
        return [1.0 for _ in vals]

    return [(v - mn) / (mx - mn) for v in vals]


def smart_join_parts(parts):
    parts = [re.sub(r"\s+", " ", str(p)).strip() for p in parts if str(p).strip()]
    if not parts:
        return ""

    out_tokens = []
    seen_parts = set()

    for part in parts:
        norm_part = normalize_text(part)
        if norm_part in seen_parts:
            continue
        seen_parts.add(norm_part)

        tokens = part.split()
        if not tokens:
            continue

        overlap = 0
        max_overlap = min(len(out_tokens), len(tokens), 4)

        for k in range(max_overlap, 0, -1):
            if [normalize_text(x) for x in out_tokens[-k:]] == [
                normalize_text(x) for x in tokens[:k]
            ]:
                overlap = k
                break

        out_tokens.extend(tokens[overlap:])

    return " ".join(out_tokens).strip()


def clean_json_candidate(text: str) -> str:
    text = str(text).strip()
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text.strip()


def parse_json_block(text: str):
    text = clean_json_candidate(text)

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None

    candidate = clean_json_candidate(match.group(0))

    try:
        return json.loads(candidate)
    except Exception:
        return None


def normalize_relation_label(value: str) -> str:
    t = normalize_text(value)

    if t in {"supports_yes", "yes", "evet"}:
        return "supports_yes"
    if t in {"supports_no", "no", "hayir", "hayır"}:
        return "supports_no"
    if t in {"procedural", "usuli"}:
        return "procedural"
    if t in {"irrelevant", "alakasiz", "alakasız"}:
        return "irrelevant"

    return "unclear"


def get_hit_score(item):
    try:
        return float(item["hit"].score)
    except Exception:
        return 0.0


def fallback_relation_from_text(question: str, text: str):
    q = normalize_text(question)
    t = normalize_text(text)

    no_cues_strong = [
        "yasal degildir", "yasal değildir", "hukuka aykiri", "hukuka aykırı",
        "yetkisi bulunmadigi", "yetkisi bulunmadığı",
        "dogrudan gonderilmesi yasal degildir", "doğrudan gönderilmesi yasal değildir",
        "sira cetveli yapilmadan", "sıra cetveli yapılmadan",
        "dogru degildir", "doğru değildir", "isabetsizdir", "reddine", "reddi",
    ]

    yes_cues_strong = [
        "yapilmasi gerekir", "yapılması gerekir", "zorunludur",
        "emredilmesine", "kabulune", "kabulüne", "tespitine",
        "dogru olmamis", "doğru olmamış", "isabetsiz",
    ]

    procedural_cues = [
        "eksik inceleme", "arastirilmasi gerekir", "araştırılması gerekir",
        "bozulmasina", "bozulmasına", "yeniden degerlendirilmesi",
        "yeniden değerlendirilmesi", "yaklasik ispat", "yaklaşık ispat",
    ]

    q_asks_can = any(
        x in q
        for x in [
            "gonderebilir mi", "gönderebilir mi", "dogrudan", "doğrudan",
            "karar verebilir mi", "odeyebilir mi", "ödeyebilir mi", "mahsup edebilir mi",
        ]
    )

    q_asks_required = any(
        x in q
        for x in [
            "gerekir mi", "zorunlu mu", "yapilmasi mi gerekir", "yapılması mı gerekir",
            "once sira cetveli", "önce sıra cetveli", "sira cetveli yapilmasi", "sıra cetveli yapılması",
        ]
    )

    if q_asks_can:
        if any(c in t for c in no_cues_strong):
            return "supports_no"
        if "sira cetveli yapilmasi gerekir" in t or "sıra cetveli yapılması gerekir" in t:
            return "supports_no"

    if q_asks_required:
        if "sira cetveli yapilmasi gerekir" in t or "sıra cetveli yapılması gerekir" in t:
            return "supports_yes"
        if any(c in t for c in yes_cues_strong):
            return "supports_yes"

    pos = sum(1 for c in yes_cues_strong if c in t)
    neg = sum(1 for c in no_cues_strong if c in t)
    pro = sum(1 for c in procedural_cues if c in t)

    if q_asks_can and ("sira cetveli" in q or "sıra cetveli" in q):
        if "sira cetveli yapilmadan" in t or "sıra cetveli yapılmadan" in t:
            return "supports_no"

    if pro >= max(pos, neg) and pro > 0:
        return "procedural"
    if pos > neg and pos > 0:
        return "supports_yes"
    if neg > pos and neg > 0:
        return "supports_no"

    return "unclear"
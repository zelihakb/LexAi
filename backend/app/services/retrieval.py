from types import SimpleNamespace
import httpx
from collections import OrderedDict

from qdrant_client.http import models
from rank_bm25 import BM25Okapi

from app.core.config import (
    QDRANT_URL,
    QDRANT_API_KEY,
    COLLECTION_NAME,
    FINAL_CONTEXT_K,
    BM25_WEIGHT,
    DENSE_WEIGHT,
    LEXICAL_WEIGHT,
    MAX_EVIDENCE_TEXT,
    RERANK_POOL_SIZE,
    RRF_K,
    RRF_WEIGHT,
    SEMANTIC_THRESHOLD,
    TOP_K_PER_QUERY,
)
from app.core.models import client, embedder, reranker
from app.services.helpers import (
    build_metadata_text,
    clean_title_for_scoring,
    clip_text,
    extract_query_phrases,
    extract_query_terms,
    minmax_normalize,
    normalize_text,
    phrase_match_count,
    smart_join_parts,
    token_match_count,
    tokenize_for_bm25,
)


# =========================
# QUERY REWRITE
# =========================
def build_search_queries(user_question: str):
    terms = extract_query_terms(user_question)
    phrases = extract_query_phrases(user_question)

    q1 = " ".join(str(user_question).split()).strip()
    q2 = smart_join_parts(phrases[:4] + terms[:8])
    q3 = smart_join_parts(terms[:10])

    queries = []
    seen = set()

    for q in [q1, q2, q3]:
        q = " ".join(str(q).split()).strip()
        if len(q) < 5:
            continue

        nq = normalize_text(q)
        if nq not in seen:
            seen.add(nq)
            queries.append(q)

    return queries


def infer_expected_folders(question: str):
    q = normalize_text(question)
    folders = []

    if any(
        x in q
        for x in [
            "ssk",
            "sgk",
            "bagkur",
            "bağkur",
            "emeklilik",
            "yaslilik ayligi",
            "yaşlılık aylığı",
            "prim gunu",
            "prim günü",
            "sigortalilik",
            "sigortalılık",
            "sgdp",
            "aylik",
            "aylığı",
            "ayligi",
        ]
    ):
        folders.append("sgk_data")

    if any(
        x in q
        for x in [
            "icra",
            "odeme emri",
            "ödeme emri",
            "haciz",
            "sira cetveli",
            "sıra cetveli",
            "takip",
        ]
    ):
        folders.append("icra_data")

    if any(
        x in q
        for x in [
            "fesih",
            "ise iade",
            "işe iade",
            "kidem",
            "kıdem",
            "ihbar",
            "isci",
            "işçi",
            "isveren",
            "işveren",
        ]
    ):
        folders.append(normalize_text("işçişveren_data"))

    if any(x in q for x in ["kira", "kiraci", "kiracı", "tahliye"]):
        folders.append("kira_data")

    if any(x in q for x in ["idari para cezasi", "idari para cezası"]):
        folders.append("idaripara_data")

    if any(
        x in q
        for x in [
            "orman",
            "kadastro",
            "tapu",
            "tescil",
            "hak düşürücü süre",
            "hak dusurucu sure",
            "parsel",
            "kamulaştırma",
            "kamulastirma",
        ]
    ):
        folders.append("kadastro_tapu_data")
        folders.append("mülkiyet_data")
        folders.append("kamulastirma_data")

    return list(dict.fromkeys(folders))

# =========================
# QDRANT RAW HTTP FALLBACK
# =========================
def use_raw_qdrant_http():
    return bool(QDRANT_API_KEY)


def qdrant_headers():
    if QDRANT_API_KEY:
        return {"api-key": QDRANT_API_KEY}
    return {}


def qdrant_post(path: str, body: dict, timeout: int = 120):
    url = QDRANT_URL.rstrip("/") + path

    response = httpx.post(
        url,
        headers=qdrant_headers(),
        json=body,
        timeout=timeout,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Qdrant HTTP error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    return data.get("result", data)


def make_hit_from_raw_point(point: dict):
    return SimpleNamespace(
        id=point.get("id"),
        score=float(point.get("score", 0.0) or 0.0),
        payload=point.get("payload", {}) or {},
    )
# =========================
# RETRIEVE + RRF
# =========================
def retrieve_for_single_query(search_query: str):
    query_vector = embedder.encode(search_query).tolist()

    if use_raw_qdrant_http():
        result = qdrant_post(
            f"/collections/{COLLECTION_NAME}/points/query",
            {
                "query": query_vector,
                "limit": TOP_K_PER_QUERY,
                "score_threshold": SEMANTIC_THRESHOLD,
                "with_payload": True,
                "with_vector": False,
            },
        )

        raw_points = result.get("points", []) if isinstance(result, dict) else []
        return [make_hit_from_raw_point(p) for p in raw_points]

    hits_response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=TOP_K_PER_QUERY,
        score_threshold=SEMANTIC_THRESHOLD,
        with_payload=True,
    )

    return hits_response.points if hits_response and hits_response.points else []

def retrieve_candidates_with_rrf(user_question: str):
    search_queries = build_search_queries(user_question)
    merged = {}

    for q in search_queries:
        hits = retrieve_for_single_query(q)

        for rank, hit in enumerate(hits, start=1):
            key = str(hit.id)

            if key not in merged:
                merged[key] = {
                    "hit": hit,
                    "rrf_score": 0.0,
                    "best_semantic_score": float(hit.score),
                    "matched_queries": [],
                    "ranks": [],
                }

            merged[key]["rrf_score"] += 1.0 / (RRF_K + rank)
            merged[key]["best_semantic_score"] = max(
                merged[key]["best_semantic_score"],
                float(hit.score),
            )
            merged[key]["matched_queries"].append(q)
            merged[key]["ranks"].append(rank)

    candidates = []
    for _, value in merged.items():
        hit = value["hit"]
        payload = hit.payload or {}
        payload["_matched_queries"] = value["matched_queries"]
        payload["_rrf_score"] = value["rrf_score"]
        payload["_best_semantic_score"] = value["best_semantic_score"]
        payload["_ranks"] = value["ranks"]
        hit.payload = payload
        candidates.append(hit)

    return candidates, search_queries


# =========================
# HYBRID SCORING
# =========================
def hybrid_candidate_scoring(user_question: str, search_queries: list, candidates: list):
    query_terms = extract_query_terms(user_question)
    query_phrases = extract_query_phrases(user_question)
    expected_folders = infer_expected_folders(user_question)

    if not candidates:
        return [], query_terms, query_phrases

    corpus_texts = []
    for hit in candidates:
        payload = hit.payload or {}
        text = payload.get("text", "") or ""
        title = clean_title_for_scoring(payload.get("title", "") or "")
        meta = build_metadata_text(payload)
        corpus_texts.append(f"{title}\n{text}\n{meta}")

    tokenized_corpus = [tokenize_for_bm25(x) for x in corpus_texts]

    if any(len(x) > 0 for x in tokenized_corpus):
        bm25 = BM25Okapi(tokenized_corpus)
        all_bm25 = []

        for sq in search_queries:
            sq_tokens = tokenize_for_bm25(sq)
            scores = bm25.get_scores(sq_tokens).tolist() if sq_tokens else [0.0] * len(candidates)
            all_bm25.append(scores)

        bm25_scores_raw = []
        for i in range(len(candidates)):
            candidate_scores = [score_list[i] for score_list in all_bm25] if all_bm25 else [0.0]
            bm25_scores_raw.append(max(candidate_scores))
    else:
        bm25_scores_raw = [0.0] * len(candidates)

    dense_scores = minmax_normalize(
        [
            float((h.payload or {}).get("_best_semantic_score", float(h.score)))
            for h in candidates
        ]
    )
    bm25_scores = minmax_normalize(bm25_scores_raw)
    rrf_scores = minmax_normalize(
        [
            float((h.payload or {}).get("_rrf_score", 0.0))
            for h in candidates
        ]
    )

    rescored = []
    for idx, hit in enumerate(candidates):
        payload = hit.payload or {}
        text = payload.get("text", "") or ""
        title = clean_title_for_scoring(payload.get("title", "") or "")
        meta = build_metadata_text(payload)
        matched_queries = payload.get("_matched_queries", [])

        folder = normalize_text(str(payload.get("folder", "")).strip())
        folder_bonus = 0.0
        if expected_folders:
            if folder in expected_folders:
                folder_bonus += 0.14
            else:
                folder_bonus -= 0.08

        text_token = token_match_count(text, query_terms)
        text_phrase = phrase_match_count(text, query_phrases)
        meta_token = token_match_count(meta, query_terms)
        meta_phrase = phrase_match_count(meta, query_phrases)
        title_match = token_match_count(title, query_terms) + phrase_match_count(title, query_phrases)
        multi_query_bonus = min(len(set(matched_queries)) * 0.04, 0.12)

        lexical_support = (
            text_token * 0.05
            + text_phrase * 0.08
            + meta_token * 0.04
            + meta_phrase * 0.06
            + title_match * 0.05
            + multi_query_bonus
        )
        lexical_support = max(0.0, min(lexical_support, 1.0))

        hybrid_score = (
            dense_scores[idx] * DENSE_WEIGHT
            + bm25_scores[idx] * BM25_WEIGHT
            + rrf_scores[idx] * RRF_WEIGHT
            + lexical_support * LEXICAL_WEIGHT
            + folder_bonus
        )
        hybrid_score = max(0.0, min(hybrid_score, 1.2))

        rescored.append(
            {
                "hit": hit,
                "payload": payload,
                "dense_norm": dense_scores[idx],
                "bm25_norm": bm25_scores[idx],
                "rrf_norm": rrf_scores[idx],
                "lexical_support": lexical_support,
                "folder_bonus": folder_bonus,
                "hybrid_score": hybrid_score,
                "matched_queries": matched_queries,
            }
        )

    rescored.sort(key=lambda x: x["hybrid_score"], reverse=True)

    best_per_document = OrderedDict()
    for item in rescored:
        doc_id = item["payload"].get("document_id")
        if not doc_id:
            doc_id = f"fallback_{item['hit'].id}"

        if doc_id not in best_per_document:
            best_per_document[doc_id] = item

    rescored_unique = list(best_per_document.values())
    rescored_unique.sort(key=lambda x: x["hybrid_score"], reverse=True)

    return rescored_unique[:RERANK_POOL_SIZE], query_terms, query_phrases


# =========================
# RERANK
# =========================
def should_keep_for_rerank(item: dict):
    if float(item.get("hybrid_score", 0.0)) < 0.15:
        return False
    return True


def cross_encoder_rerank(user_question: str, candidate_pool: list, top_k: int = FINAL_CONTEXT_K):
    if not candidate_pool:
        return []

    filtered_pool = [item for item in candidate_pool if should_keep_for_rerank(item)]
    if not filtered_pool:
        filtered_pool = candidate_pool[: min(len(candidate_pool), 8)]

    pairs = []
    for item in filtered_pool:
        payload = item["payload"]
        title = clean_title_for_scoring(payload.get("title", "") or "")
        text = payload.get("text", "") or ""
        meta = build_metadata_text(payload)

        passage = (
            f"mahkeme: {payload.get('court', '')}\n"
            f"başlık: {title}\n"
            f"metin: {text}\n"
            f"metadata: {meta}"
        )
        pairs.append((user_question, passage[:1800]))

    raw_preds = reranker.predict(pairs)
    ce_scores_raw = []

    for p in raw_preds:
        if hasattr(p, "__len__") and not isinstance(p, (str, bytes)):
            if len(p) == 1:
                ce_scores_raw.append(float(p[0]))
            else:
                ce_scores_raw.append(float(p[-1]))
        else:
            ce_scores_raw.append(float(p))

    ce_scores = minmax_normalize(ce_scores_raw)

    for idx, item in enumerate(filtered_pool):
        item["ce_score_raw"] = ce_scores_raw[idx]
        item["ce_score_norm"] = ce_scores[idx]
        item["final_score"] = (item["hybrid_score"] * 0.60) + (item["ce_score_norm"] * 0.40)

    filtered_pool.sort(key=lambda x: x["final_score"], reverse=True)
    return filtered_pool[:top_k]


def scroll_candidates(limit: int = 5000):
    if use_raw_qdrant_http():
        items = []
        offset = None
        batch_limit = 2048

        while len(items) < limit:
            body = {
                "limit": min(batch_limit, limit - len(items)),
                "with_payload": True,
                "with_vector": False,
            }

            if offset is not None:
                body["offset"] = offset

            result = qdrant_post(
                f"/collections/{COLLECTION_NAME}/points/scroll",
                body,
            )

            points = result.get("points", []) if isinstance(result, dict) else []
            offset = result.get("next_page_offset") if isinstance(result, dict) else None

            for point in points:
                payload = point.get("payload", {}) or {}
                items.append(
                    {
                        "final_score": 0.0,
                        "payload": payload,
                    }
                )

            if not points or offset is None:
                break

        return items

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        with_payload=True,
        with_vectors=False,
        limit=limit,
    )

    items = []
    for p in points:
        payload = p.payload or {}
        items.append(
            {
                "final_score": 0.0,
                "payload": payload,
            }
        )

    return items


# =========================
# KOMŞU CHUNK TOPLAMA
# =========================
def get_document_neighbor_chunks(document_id: str, center_chunk_index: int, window: int = 1):
    if not document_id:
        return []

    if use_raw_qdrant_http():
        result = qdrant_post(
            f"/collections/{COLLECTION_NAME}/points/scroll",
            {
                "limit": 200,
                "with_payload": True,
                "with_vector": False,
                "filter": {
                    "must": [
                        {
                            "key": "document_id",
                            "match": {"value": document_id},
                        }
                    ]
                },
            },
        )

        points = result.get("points", []) if isinstance(result, dict) else []

        rows = []
        for point in points:
            payload = point.get("payload", {}) or {}
            idx = payload.get("chunk_index", -999)
            rows.append((idx, payload))

        rows.sort(key=lambda x: x[0])

        selected = []
        low = center_chunk_index - window
        high = center_chunk_index + window

        for idx, payload in rows:
            if low <= idx <= high:
                selected.append(payload)

        return selected

    flt = models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=document_id),
            )
        ]
    )

    points, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=flt,
        with_payload=True,
        with_vectors=False,
        limit=200,
    )

    rows = []
    for p in points:
        payload = p.payload or {}
        idx = payload.get("chunk_index", -999)
        rows.append((idx, payload))

    rows.sort(key=lambda x: x[0])

    selected = []
    low = center_chunk_index - window
    high = center_chunk_index + window

    for idx, payload in rows:
        if low <= idx <= high:
            selected.append(payload)

    return selected


# =========================
# RAW KARAR KANITI HAZIRLAMA
# =========================
def build_raw_evidence(final_items: list):
    evidence = []

    for rank, item in enumerate(final_items, start=1):
        payload = item["payload"]
        doc_id = payload.get("document_id")
        chunk_index = payload.get("chunk_index", 0)

        if doc_id:
            neighbor_payloads = get_document_neighbor_chunks(doc_id, chunk_index, window=1)
        else:
            neighbor_payloads = [payload]

        merged_text = "\n".join(
            [
                str(np.get("text", ""))
                for np in neighbor_payloads
                if str(np.get("text", "")).strip()
            ]
        )

        evidence.append(
            {
                "rank": rank,
                "score": float(item.get("final_score", 0.0)),
                "folder": str(payload.get("folder", "")),
                "court": str(payload.get("court", "")),
                "case_no": str(payload.get("case_no", "")),
                "decision_no": str(payload.get("decision_no", "")),
                "text": clip_text(merged_text, MAX_EVIDENCE_TEXT),
            }
        )

    return evidence


def format_raw_evidence(evidence: list):
    blocks = []

    for e in evidence:
        blocks.append(
            f"[KARAR {e['rank']}]\n"
            f"Score: {e['score']:.3f}\n"
            f"Folder: {e['folder']}\n"
            f"Court: {e['court']}\n"
            f"Case No: {e['case_no']}\n"
            f"Decision No: {e['decision_no']}\n"
            f"Text:\n{e['text']}"
        )

    return "\n\n---\n\n".join(blocks)
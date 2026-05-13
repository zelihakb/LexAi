import os
from dotenv import load_dotenv

load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "hukuk_kararlari_updated")

AI_MODEL = "qwen2.5:3b"
COLLECTION_NAME = "hukuk_kararlari_updated"

TOP_K_PER_QUERY = 18
RERANK_POOL_SIZE = 10
FINAL_CONTEXT_K = 5
SEMANTIC_THRESHOLD = 0.24
RRF_K = 60

DENSE_WEIGHT = 0.42
BM25_WEIGHT = 0.24
RRF_WEIGHT = 0.18
LEXICAL_WEIGHT = 0.16

MIN_FINAL_SCORE = 0.38
MIN_TOP_GAP = 0.04

EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
RERANK_MODEL_NAME = "amberoad/bert-multilingual-passage-reranking-msmarco"

OLLAMA_TIMEOUT = 180
LLM_MAX_RETRIES = 3
MAX_EVIDENCE_TEXT = 3200
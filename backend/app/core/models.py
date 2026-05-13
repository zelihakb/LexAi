from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient

from app.core.config import (
    EMBED_MODEL_NAME,
    RERANK_MODEL_NAME,
    QDRANT_URL,
)
from sentence_transformers import SentenceTransformer, CrossEncoder
from qdrant_client import QdrantClient

from app.core.config import (
    EMBED_MODEL_NAME,
    RERANK_MODEL_NAME,
    QDRANT_URL,
    QDRANT_API_KEY,
)


print("Embedding modeli yükleniyor...")
embedder = SentenceTransformer(EMBED_MODEL_NAME, device="cpu")

print("Reranker modeli yükleniyor...")
reranker = CrossEncoder(RERANK_MODEL_NAME, device="cpu")

print("Qdrant bağlanıyor...")

client_kwargs = {
    "url": QDRANT_URL,
    "timeout": 120,
    "prefer_grpc": False,
    "check_compatibility": False,
}

if QDRANT_API_KEY:
    client_kwargs["api_key"] = QDRANT_API_KEY

client = QdrantClient(**client_kwargs)

print("Embedding modeli yükleniyor...")
embedder = SentenceTransformer(EMBED_MODEL_NAME, device="cpu")

print("Reranker modeli yükleniyor...")
reranker = CrossEncoder(RERANK_MODEL_NAME, device="cpu")

print("Qdrant bağlanıyor...")
client = QdrantClient(url=QDRANT_URL)
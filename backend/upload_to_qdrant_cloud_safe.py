import os
import json
import re
import hashlib
import warnings
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models

warnings.filterwarnings("ignore")
load_dotenv(Path(__file__).resolve().parent / ".env")

# =========================
# AYARLAR
# =========================

ROOT_DIR = Path(os.getenv("LEXAI_DATA_ROOT", r"C:\anaconda13\Scripts\LexAI"))

QDRANT_CLOUD_URL = os.getenv("QDRANT_CLOUD_URL", "").strip()
QDRANT_CLOUD_API_KEY = os.getenv("QDRANT_CLOUD_API_KEY", "").strip()

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "hukuk_kararlari_updated")

CHUNK_SIZE = 220
OVERLAP = 0.20
BATCH_SIZE = 64

MODEL_NAME = os.getenv(
    "EMBED_MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
)

VECTOR_SIZE = 768


# =========================
# GÜVENLİK KONTROLÜ
# =========================

def safety_check():
    if not QDRANT_CLOUD_URL:
        raise RuntimeError(
            "QDRANT_CLOUD_URL boş. backend/.env içine Cloud URL eklenmeli."
        )

    if not QDRANT_CLOUD_API_KEY:
        raise RuntimeError(
            "QDRANT_CLOUD_API_KEY boş. backend/.env içine Cloud API key eklenmeli."
        )

    lowered_url = QDRANT_CLOUD_URL.lower()

    if "localhost" in lowered_url or "127.0.0.1" in lowered_url:
        raise RuntimeError(
            "Bu script Cloud için. Localhost URL görüldü, local Qdrant'a dokunmamak için durduruldu."
        )

    if not ROOT_DIR.exists():
        raise RuntimeError(f"Veri klasörü bulunamadı: {ROOT_DIR}")


# =========================
# YARDIMCI FONKSİYONLAR
# =========================

def normalize_for_id(text: str) -> str:
    text = str(text).lower().strip()
    text = text.replace("â", "a").replace("î", "i").replace("û", "u")
    text = re.sub(r"\s+", " ", text)
    return text


def make_document_id(court, year, case_no, decision_no):
    raw = (
        f"{normalize_for_id(court)}|"
        f"{year}|"
        f"{normalize_for_id(case_no)}|"
        f"{normalize_for_id(decision_no)}"
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def chunk_text(text, chunk_size=220, overlap=0.20):
    words = str(text or "").split()

    if not words:
        return []

    step = max(1, int(chunk_size * (1 - overlap)))
    chunks = []

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size]).strip()

        if chunk:
            chunks.append(chunk)

        if i + chunk_size >= len(words):
            break

    return chunks


def iter_jsonl_files(root_dir: Path):
    for file_path in root_dir.rglob("*.jsonl"):
        if ".ipynb_checkpoints" in str(file_path):
            continue

        yield file_path


def create_fresh_collection(client: QdrantClient):
    existing_collections = client.get_collections().collections
    existing_names = {collection.name for collection in existing_collections}

    if COLLECTION_NAME in existing_names:
        print(f"Koleksiyon zaten mevcut, SILINMEYECEK: {COLLECTION_NAME}")
        print("Yukleme mevcut koleksiyona ayni ID'lerle guvenle devam edecek.")
        info = client.get_collection(collection_name=COLLECTION_NAME)
        vectors = info.config.params.vectors
        configured_dim = getattr(vectors, "size", None)
        if configured_dim is not None and configured_dim != VECTOR_SIZE:
            raise RuntimeError(f"Beklenen vektor boyutu {VECTOR_SIZE}, mevcut {configured_dim}. Islem durduruldu.")
        return

    print(f"Yeni koleksiyon olusturuluyor: {COLLECTION_NAME}")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )


# =========================
# MAIN
# =========================

def main():
    safety_check()

    print("=" * 80)
    print("LEXAI QDRANT CLOUD UPLOAD")
    print("=" * 80)
    print("Veri klasörü:", ROOT_DIR)
    print("Cloud URL:", QDRANT_CLOUD_URL)
    print("Collection:", COLLECTION_NAME)
    print("Embedding model:", MODEL_NAME)
    print("Vector size:", VECTOR_SIZE)
    print("Distance: COSINE")
    print("=" * 80)

    print("Embedding modeli yükleniyor...")
    embedder = SentenceTransformer(MODEL_NAME, device="cpu")

    print("Qdrant Cloud'a bağlanıyor...")
    client = QdrantClient(
        url=QDRANT_CLOUD_URL,
        api_key=QDRANT_CLOUD_API_KEY,
        timeout=120,
    )

    print("Bağlantı testi:")
    print(client.get_collections())

    create_fresh_collection(client)

    batch_points = []
    seen_document_ids = set()
    duplicate_documents = 0
    total_docs = 0
    total_chunks = 0
    total_files = 0

    jsonl_files = list(iter_jsonl_files(ROOT_DIR))

    if not jsonl_files:
        raise RuntimeError(f"Hiç .jsonl dosyası bulunamadı: {ROOT_DIR}")

    print(f"Bulunan jsonl dosyası: {len(jsonl_files)}")
    print("=" * 80)

    for file_path in jsonl_files:
        total_files += 1
        folder = file_path.parent.name
        filename = file_path.name

        print(f"[{total_files}/{len(jsonl_files)}] İşleniyor: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                for line_idx, line in enumerate(f):
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except Exception:
                        continue

                    full_text = data.get("full_text", "") or data.get("text", "")

                    if not full_text or len(full_text) < 80:
                        continue

                    court = data.get("court", "Bilinmiyor")
                    year = data.get("year", "")
                    case_no = data.get("case_no", "")
                    decision_no = data.get("decision_no", "")
                    title = data.get("title", "")
                    decision_date = data.get("decision_date", "")
                    url = data.get("url", "")

                    document_id = make_document_id(
                        court=court,
                        year=year,
                        case_no=case_no,
                        decision_no=decision_no,
                    )

                    # Ayni mahkeme/yil/esas/karar kimligi tekrarlaniyorsa
                    # ayni kararin embedding'lerini tekrar hesaplama.
                    if document_id in seen_document_ids:
                        duplicate_documents += 1
                        continue
                    seen_document_ids.add(document_id)

                    chunks = chunk_text(
                        full_text,
                        chunk_size=CHUNK_SIZE,
                        overlap=OVERLAP,
                    )

                    if not chunks:
                        continue

                    vectors = embedder.encode(
                        chunks,
                        batch_size=32,
                        show_progress_bar=False,
                    )

                    total_chunk_count = len(chunks)

                    for chunk_index, (chunk_text_value, vec) in enumerate(zip(chunks, vectors)):
                        point_id = hashlib.md5(
                            f"{document_id}_{chunk_index}".encode("utf-8")
                        ).hexdigest()

                        payload = {
                            "document_id": document_id,
                            "chunk_index": chunk_index,
                            "total_chunks": total_chunk_count,
                            "text": chunk_text_value,
                            "folder": folder,
                            "subdomain": data.get("subdomain", "general"),
                            "title": title,
                            "year": year,
                            "court": court,
                            "case_no": case_no,
                            "decision_no": decision_no,
                            "decision_date": decision_date,
                            "filename": filename,
                            "source_file": filename,
                            "url": url,
                            "line_index": line_idx,
                        }

                        batch_points.append(
                            models.PointStruct(
                                id=point_id,
                                vector=vec.tolist(),
                                payload=payload,
                            )
                        )

                        total_chunks += 1

                        if len(batch_points) >= BATCH_SIZE:
                            client.upsert(
                                collection_name=COLLECTION_NAME,
                                points=batch_points,
                                wait=True,
                            )
                            print(f"Yüklendi chunk: {total_chunks}")
                            batch_points = []

                    total_docs += 1

        except Exception as e:
            print(f"HATA: {file_path}: {e}")
            print("Verileri korumak icin islem durduruldu. Tekrar calistirmak mevcut koleksiyonu SILMEZ.")
            raise

    if batch_points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=batch_points,
            wait=True,
        )

    print("=" * 80)
    print("BİTTİ")
    print("Toplam dosya:", total_files)
    print("Benzersiz yuklenen belge:", total_docs)
    print("Atlanan tekrar kayit:", duplicate_documents)
    print("Yuklenen chunk:", total_chunks)
    print("Collection:", COLLECTION_NAME)

    info = client.get_collection(collection_name=COLLECTION_NAME)
    print("Cloud collection info:")
    print(info)
    print("=" * 80)


if __name__ == "__main__":
    main()
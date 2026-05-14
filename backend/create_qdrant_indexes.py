import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "hukuk_kararlari_updated")

if not QDRANT_URL:
    raise RuntimeError("QDRANT_URL .env içinde yok.")

client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY or None,
    timeout=60,
)

indexes = [
    ("document_id", models.PayloadSchemaType.KEYWORD),
    ("chunk_index", models.PayloadSchemaType.INTEGER),
]

for field_name, field_schema in indexes:
    try:
        print(f"Index oluşturuluyor: {field_name} -> {field_schema}")
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=field_schema,
            wait=True,
        )
        print(f"OK: {field_name}")
    except Exception as e:
        message = str(e).lower()
        if "already exists" in message or "already" in message:
            print(f"Zaten var: {field_name}")
        else:
            raise

print("Payload index işlemi tamam.")
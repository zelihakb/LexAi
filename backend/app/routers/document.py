from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.llm_service import (
    DOCUMENT_EXPLAIN_WARNING,
    DOCUMENT_OCR_WARNING,
    LLMFormatError,
    TemporaryLLMServiceError,
    explain_document_text_with_llm,
    extract_text_from_image_with_gemini,
)

router = APIRouter(prefix="/document", tags=["document"])

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}

EXTENSION_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

MAX_IMAGE_BYTES = 10 * 1024 * 1024


class DocumentExplainRequest(BaseModel):
    text: str
    document_type: str = "Diğer"


def resolve_mime_type(file: UploadFile) -> str:
    content_type = (file.content_type or "").lower().strip()
    suffix = Path(file.filename or "").suffix.lower()

    if content_type in ALLOWED_MIME_TYPES:
        return content_type

    if suffix in EXTENSION_TO_MIME:
        return EXTENSION_TO_MIME[suffix]

    raise HTTPException(
        status_code=400,
        detail="Sadece png, jpg, jpeg veya webp görsel yükleyebilirsin.",
    )


@router.post("/ocr")
async def ocr_document_image(
    image: UploadFile = File(...),
    document_type: str = Form("Diğer"),
):
    mime_type = resolve_mime_type(image)
    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Görsel dosyası boş görünüyor.",
        )

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Görsel çok büyük. Lütfen 10 MB altı bir dosya yükle.",
        )

    try:
        extracted_text = extract_text_from_image_with_gemini(
            image_bytes=image_bytes,
            mime_type=mime_type,
            document_type=document_type,
        )

        return {
            "extracted_text": extracted_text,
            "document_type": document_type or "Diğer",
            "warning": DOCUMENT_OCR_WARNING,
        }

    except TemporaryLLMServiceError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Belge metni okunamadı: {str(e)}",
        )


@router.post("/explain")
def explain_document(payload: DocumentExplainRequest):
    text = str(payload.text or "").strip()

    if len(text) < 10:
        raise HTTPException(
            status_code=400,
            detail="Açıklama için OCR metni çok kısa. Lütfen metni kontrol et.",
        )

    try:
        result = explain_document_text_with_llm(
            text=text,
            document_type=payload.document_type or "Diğer",
        )

        return {
            "plain_explanation": result["plain_explanation"],
            "important_points": result["important_points"],
            "possible_actions": result["possible_actions"],
            "warning": DOCUMENT_EXPLAIN_WARNING,
        }

    except TemporaryLLMServiceError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )

    except LLMFormatError as e:
        raise HTTPException(
            status_code=502,
            detail=str(e),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Belge açıklanamadı: {str(e)}",
        )
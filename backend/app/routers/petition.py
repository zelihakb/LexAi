from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.services.llm_service import generate_petition_with_llm


router = APIRouter()


class PetitionRequest(BaseModel):
    petition_type: str = ""
    authority: str = ""
    applicant: str = ""
    opponent: str = ""
    event_summary: str = ""
    request_summary: str = ""
    extra_notes: str = ""


@router.post("/petition")
def create_petition(payload: PetitionRequest):
    try:
        result = generate_petition_with_llm(
            petition_type=payload.petition_type,
            authority=payload.authority,
            applicant=payload.applicant,
            opponent=payload.opponent,
            event_summary=payload.event_summary,
            request_summary=payload.request_summary,
            extra_notes=payload.extra_notes,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Dilekçe oluşturulamadı: {str(e)}",
        )
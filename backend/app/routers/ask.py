from fastapi import APIRouter

from app.schemas.request_response import AskRequest
from app.services.pipeline import run_ask_pipeline

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("")
def ask_question(payload: AskRequest):
    return run_ask_pipeline(payload.question)
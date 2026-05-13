from fastapi import APIRouter

from app.schemas.request_response import FindRequest
from app.services.pipeline import run_find_pipeline

router = APIRouter(prefix="/find", tags=["find"])


@router.post("")
def find_decisions(payload: FindRequest):
    return run_find_pipeline(payload.query, payload.filters or {})
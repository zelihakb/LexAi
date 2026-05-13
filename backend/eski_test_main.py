from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


app = FastAPI(title="LexAI Backend")


# Frontend localde bağlanabilsin diye
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Request modelleri
# -------------------------
class AskRequest(BaseModel):
    question: str


class FindRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, str]] = None


# -------------------------
# Test endpoint
# -------------------------
@app.get("/")
def root():
    return {"message": "LexAI backend çalışıyor"}


# -------------------------
# Ask endpoint
# -------------------------
@app.post("/ask")
def ask_question(payload: AskRequest):
    return {
        "mode": "ask",
        "final_answer": f"Test cevap: '{payload.question}' sorusu backend'e ulaştı.",
        "confidence": {
            "status": "ok",
            "reason": "test modu"
        },
        "final_direction": "yes",
        "final_items": [
            {
                "final_score": 0.95,
                "payload": {
                    "court": "YARGITAY TEST DAİRESİ",
                    "case_no": "2025/123",
                    "decision_no": "2025/456",
                    "decision_date": "01.05.2025",
                    "folder": "test_data",
                    "text": "Bu alan şimdilik test verisidir. Gerçek retrieval daha sonra bağlanacaktır."
                }
            }
        ]
    }


# -------------------------
# Find endpoint
# -------------------------
@app.post("/find")
def find_decisions(payload: FindRequest):
    return {
        "mode": "find",
        "query": payload.query,
        "filters": payload.filters or {},
        "final_items": [
            {
                "final_score": 0.88,
                "payload": {
                    "court": "YARGITAY 12. HUKUK DAİRESİ",
                    "case_no": "2016/22283",
                    "decision_no": "2016/26288",
                    "decision_date": "28.12.2016",
                    "folder": "icra_data",
                    "text": "Bu alan filtreli karar bulma modu için test verisidir."
                }
            }
        ]
    }
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.ask import router as ask_router
from app.routers.find import router as find_router
from app.routers.petition import router as petition_router
from app.routers.document import router as document_router

app = FastAPI(title="LexAI Backend")

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

app.include_router(ask_router)
app.include_router(find_router)
app.include_router(petition_router)
app.include_router(document_router)


@app.get("/")
def root():
    return {"message": "LexAI backend çalışıyor"}

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import document

app = FastAPI()
app.include_router(document.router)
client = TestClient(app)


def test_ocr_rejects_get_request():
    response = client.get("/document/ocr")
    assert response.status_code == 405


def test_ocr_rejects_unsupported_file():
    response = client.post(
        "/document/ocr",
        files={
            "image": (
                "test.pdf",
                b"%PDF-test",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 400


def test_ocr_rejects_empty_image():
    response = client.post(
        "/document/ocr",
        files={
            "image": ("empty.png", b"", "image/png")
        },
    )
    assert response.status_code == 400


def test_explain_rejects_short_text():
    response = client.post(
        "/document/explain",
        json={"text": "kisa"},
    )
    assert response.status_code == 400


def test_explain_returns_mocked_response(monkeypatch):
    def fake_explain(*, text, document_type):
        return {
            "plain_explanation": "Ornek aciklama",
            "important_points": ["Madde 1"],
            "possible_actions": ["Kontrol et"],
        }

    monkeypatch.setattr(
        document,
        "explain_document_text_with_llm",
        fake_explain,
    )

    response = client.post(
        "/document/explain",
        json={
            "text": "Bu belge test amaciyla hazirlanmistir.",
            "document_type": "Diger",
        },
    )

    assert response.status_code == 200
    assert response.json()["plain_explanation"] == "Ornek aciklama"
    assert response.json()["important_points"] == ["Madde 1"]
    assert "warning" in response.json()

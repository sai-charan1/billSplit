from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_split_missing_description() -> None:
    response = client.post("/split", json={"receipt_base64": "abc", "description": ""})
    assert response.status_code == 400


def test_enriched_missing_description() -> None:
    response = client.post("/split/enriched", json={"receipt_base64": "abc", "description": ""})
    assert response.status_code == 400


def test_split_response_schema_matches_assignment() -> None:
    from app.models import SplitEnrichedResponse, SplitResponse

    contract_fields = set(SplitResponse.model_fields.keys())
    assert contract_fields == {
        "per_person", "grand_total", "reconciliation", "paid_by", "settle_up", "assumptions", "flags"
    }
    enriched_fields = set(SplitEnrichedResponse.model_fields.keys())
    assert "bill_health" in enriched_fields
    assert "share_message" in enriched_fields

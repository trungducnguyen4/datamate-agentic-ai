import pytest
from fastapi.testclient import TestClient
from datamate.ui.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_ui_index_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "DataMate Agentic AI" in res.text


def test_ui_get_businesses(client):
    res = client.get("/api/businesses")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(b["id"] == "biz_118" for b in data)


def test_ui_ask_endpoint(client):
    payload = {
        "business_id": "biz_118",
        "question": "sp bán dc nhiều nhất tuần rồi là gì",
        "as_of_date": "2026-03-04",
    }
    res = client.post("/api/ask", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "submission" in data
    assert data["submission"]["type"] == "string"
    assert "Xi măng" in data["submission"]["answer"]
    assert "plan" in data
    assert "latency_ms" in data

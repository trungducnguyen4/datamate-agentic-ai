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
    res = client.get("/api/businesses?dataset=train")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert any(b["id"] == "biz_118" for b in data)


def test_ui_ask_endpoint(client):
    payload = {
        "business_id": "biz_118",
        "question": "sp bán dc nhiều nhất tuần rồi là gì",
        "as_of_date": "2026-03-04",
        "dataset": "train",
    }
    res = client.post("/api/ask", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "submission" in data
    assert data["submission"]["type"] == "string"
    assert any(expected in data["submission"]["answer"] for expected in ["Xi măng", "Tôn lạnh"])
    assert "plan" in data
    assert "latency_ms" in data
    assert "trace" in data


def test_ui_qa_checklist_endpoint(client):
    res = client.get("/api/qa-checklist")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 15
    assert any(c["id"] == "VN-02" for c in data)


def test_ui_run_all_tests_endpoint(client):
    res = client.post("/api/run-all-tests")
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert data["summary"]["total"] == 15
    assert data["summary"]["passed"] == 15
    assert data["summary"]["penalized_score"] == 15.0
    assert len(data["results"]) == 15

import pytest
from unittest.mock import MagicMock, patch

from app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@patch("routes.data_ingestion.process_data_async")
@patch("routes.data_ingestion.get_redis_client")
def test_ingest_data(mock_get_redis, mock_task, client):
    # Redis 返回原子自增结果
    redis_stub = MagicMock()
    redis_stub.incr.return_value = 100
    mock_get_redis.return_value = redis_stub

    response = client.post(
        "/api/data/ingest",
        json={"server_name": "test-server", "cpu_usage": 45.0},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["eventId"] == 100
    assert data["message"] == "Data ingested successfully"

    # 异步任务应被投递
    mock_task.delay.assert_called_once()


@patch("routes.data_ingestion.get_redis_client")
def test_get_stats(mock_get_redis, client):
    redis_stub = MagicMock()
    redis_stub.get.return_value = "100"
    mock_get_redis.return_value = redis_stub

    response = client.get("/api/data/stats")

    assert response.status_code == 200
    data = response.get_json()
    assert data["totalIngested"] == 100


@patch("routes.data_ingestion.process_data_async")
@patch("routes.data_ingestion.get_redis_client")
def test_ingest_degrades_when_redis_unavailable(mock_get_redis, mock_task, client):
    """Redis 不可用时降级为 eventId=1，接口仍应成功。"""
    mock_get_redis.return_value = None

    response = client.post("/api/data/ingest", json={"server_name": "x"})

    assert response.status_code == 200
    assert response.get_json()["eventId"] == 1
    mock_task.delay.assert_called_once()


@patch("routes.data_ingestion.process_data_async")
@patch("routes.data_ingestion.get_redis_client")
def test_ingest_handles_empty_body(mock_get_redis, mock_task, client):
    """空请求体不应触发 500。"""
    mock_get_redis.return_value = None
    response = client.post("/api/data/ingest", data="", content_type="application/json")
    assert response.status_code == 200

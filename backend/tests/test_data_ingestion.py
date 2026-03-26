import pytest
from app import create_app
from unittest.mock import patch

@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@patch('routes.data_ingestion.redis_client')
@patch('routes.data_ingestion.process_data_async')
def test_ingest_data(mock_task, mock_redis, client):
    # 模拟 Redis 返回的原子计数
    mock_redis.incr.return_value = 100
    
    response = client.post('/api/data/ingest', json={
        "server_name": "test-server",
        "cpu_usage": 45.0
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['eventId'] == 100
    assert data['message'] == 'Data ingested successfully'
    
    # 验证异步任务是否被调用
    mock_task.delay.assert_called_once()

@patch('routes.data_ingestion.redis_client')
def test_get_stats(mock_redis, client):
    mock_redis.get.return_value = "100"
    
    response = client.get('/api/data/stats')
    assert response.status_code == 200
    data = response.get_json()
    assert data['totalIngested'] == 100
    assert data['status'] == 'running'

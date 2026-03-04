# CHANGED: Flask-Integrationstests mit Mock-Renderer (ohne echte Kamera)
import pytest
from unittest.mock import MagicMock
from config import Config
from web.server import create_app

@pytest.fixture
def client():
    cfg      = Config()
    renderer = MagicMock()
    renderer.status   = {"faces": 0, "fps": 25}
    renderer.uptime.return_value = 42.0
    camera   = MagicMock()
    camera.queue.empty.return_value = False
    app = create_app(cfg, renderer, camera)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"FaceTrack" in r.data

def test_status(client):
    r = client.get("/status")
    assert r.status_code == 200
    data = r.get_json()
    assert "faces" in data and "fps" in data

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["camera_ok"] is True
    assert "uptime_s" in data

"""FaceTrack web package."""
from .server import create_app, METRICS
from .template import HTML

__all__ = ["create_app", "METRICS", "HTML"]

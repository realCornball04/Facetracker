from dataclasses import dataclass
from dotenv import load_dotenv # pyright: ignore[reportMissingImports]
import os, logging

load_dotenv()

def _hex_to_bgr(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)

@dataclass
class Config:
    cam_id: int = int(os.getenv("CAM_ID", "0"))
    cam_w: int = int(os.getenv("CAM_W", "480"))
    cam_h: int = int(os.getenv("CAM_H", "360"))
    detect_w: int = int(os.getenv("DETECT_W", "240"))
    detect_h: int = int(os.getenv("DETECT_H", "180"))
    target_fps: int = int(os.getenv("TARGET_FPS", "30"))
    detect_fps: int = int(os.getenv("DETECT_FPS", "12"))
    smooth_alpha: float = float(os.getenv("SMOOTH_ALPHA", "0.25"))
    jpeg_quality: int = int(os.getenv("JPEG_QUALITY", "65"))
    diff_thresh: int = int(os.getenv("DIFF_THRESH", "15"))
    detector: str = os.getenv("DETECTOR", "haar")
    yunet_model: str = os.getenv("YUNET_MODEL", "models/face_detection_yunet_2023mar.onnx")
    yunet_score: float = float(os.getenv("YUNET_SCORE", "0.75"))
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "5000"))
    auth_user: str = os.getenv("AUTH_USER", "")
    auth_pass: str = os.getenv("AUTH_PASS", "")
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "*")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "")
    box_color: str = os.getenv("BOX_COLOR", "#FFFFFF")

    @property
    def box_color_bgr(self) -> tuple:
        try:
            return _hex_to_bgr(self.box_color)
        except Exception:
            return (255, 255, 255)

    @property
    def frame_time(self) -> float:
        return 1.0 / self.target_fps

    @property
    def detect_interval(self) -> float:
        return 1.0 / self.detect_fps

    @property
    def scale_x(self) -> float:
        return self.cam_w / self.detect_w

    @property
    def scale_y(self) -> float:
        return self.cam_h / self.detect_h


def setup_logging(cfg: Config) -> logging.Logger:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if cfg.log_file:
        handlers.append(logging.FileHandler(cfg.log_file))
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    return logging.getLogger("facetrack")

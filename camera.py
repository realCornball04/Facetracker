import cv2, sys, threading, time, logging # pyright: ignore[reportMissingImports]
from queue import Queue

log = logging.getLogger("facetrack.camera")

class CameraManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self.queue: Queue = Queue(maxsize=1)
        self._stop = threading.Event()
        self._cap = None
        self._last_frame_time: float = 0.0

    def _get_backend(self) -> int:
        if sys.platform == "win32":
            return cv2.CAP_DSHOW
        return cv2.CAP_V4L2

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self.cfg.cam_id, self._get_backend())
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.cam_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.cam_h)
        cap.set(cv2.CAP_PROP_FPS, self.cfg.target_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        if actual_w != self.cfg.cam_w or actual_h != self.cfg.cam_h:
            log.warning("Auflösung: gewünscht %dx%d, erhalten %dx%d",
                        self.cfg.cam_w, self.cfg.cam_h, int(actual_w), int(actual_h))
        if actual_fps != self.cfg.target_fps:
            log.warning("FPS: gewünscht %d, erhalten %d",
                        self.cfg.target_fps, int(actual_fps))
        return cap

    def switch_camera(self, cam_id: int):
        log.info("Kamera-Wechsel zu ID %d", cam_id)
        self.cfg.cam_id = cam_id
        if self._cap:
            self._cap.release()

    def run(self):
        backoff = 0.5
        while not self._stop.is_set():
            try:
                self._cap = self._open()
                if not self._cap.isOpened():
                    raise RuntimeError("Kamera konnte nicht geöffnet werden")
                log.info("Kamera geöffnet (id=%d)", self.cfg.cam_id)
                backoff = 0.5
                fail = 0
                while not self._stop.is_set():
                    ret, frame = self._cap.read()
                    if ret:
                        fail = 0
                        self._last_frame_time = time.monotonic()
                        if self.queue.full():
                            try:
                                self.queue.get_nowait()
                            except Exception:
                                pass
                        self.queue.put_nowait(frame)
                    else:
                        fail += 1
                        if fail > 10:
                            log.error("Zu viele Lesefehler — reconnect...")
                            break
            except Exception as e:
                log.error("Kamera-Fehler: %s — retry in %.1fs", e, backoff)
            finally:
                if self._cap:
                    self._cap.release()
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def is_alive(self, max_age: float = 2.0) -> bool:
        return (time.monotonic() - self._last_frame_time) < max_age

    def get_frame(self):
        try:
            return self.queue.get(timeout=0.1)
        except Exception:
            return None

    def stop(self):
        self._stop.set()

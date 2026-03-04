import cv2, time, threading, logging, os, math # pyright: ignore[reportMissingImports]
from queue import Queue
from typing import Optional, Callable, Tuple

log = logging.getLogger("facetrack.renderer")
Color = Tuple[int, int, int]

# ── Box-Style Funktionen ──────────────────────────────────────────────────────

def _style_none(out, rx, ry, rw, rh, cx, cy, c, lw): pass

def _style_rect(out, rx, ry, rw, rh, cx, cy, c, lw):
    cv2.rectangle(out, (rx, ry), (rx+rw, ry+rh), c, lw, cv2.LINE_AA)

def _style_corners(out, rx, ry, rw, rh, cx, cy, c, lw):
    k = max(12, rw // 7)
    for pts in [
        ((rx, ry), (rx+k, ry)), ((rx, ry), (rx, ry+k)),
        ((rx+rw, ry), (rx+rw-k, ry)), ((rx+rw, ry), (rx+rw, ry+k)),
        ((rx, ry+rh), (rx+k, ry+rh)), ((rx, ry+rh), (rx, ry+rh-k)),
        ((rx+rw, ry+rh), (rx+rw-k, ry+rh)), ((rx+rw, ry+rh), (rx+rw, ry+rh-k)),
    ]:
        cv2.line(out, pts[0], pts[1], c, lw, cv2.LINE_AA)

def _style_circle(out, rx, ry, rw, rh, cx, cy, c, lw):
    cv2.circle(out, (cx, cy), max(rw, rh) // 2, c, lw, cv2.LINE_AA)

def _style_crosshair(out, rx, ry, rw, rh, cx, cy, c, lw):
    arm = int(min(rw, rh) * 0.55)
    cv2.line(out, (cx-arm, cy), (cx+arm, cy), c, lw, cv2.LINE_AA)
    cv2.line(out, (cx, cy-arm), (cx, cy+arm), c, lw, cv2.LINE_AA)
    cv2.circle(out, (cx, cy), arm // 3, c, lw, cv2.LINE_AA)

def _style_dot(out, rx, ry, rw, rh, cx, cy, c, lw):
    cv2.circle(out, (cx, cy), 6, c, -1, cv2.LINE_AA)

def _style_sniper(out, rx, ry, rw, rh, cx, cy, c, lw):
    r = max(rw, rh) // 2
    cv2.circle(out, (cx, cy), r, c, lw, cv2.LINE_AA)
    cv2.circle(out, (cx, cy), r // 6, c, lw, cv2.LINE_AA)
    h_img, w_img = out.shape[:2]
    cv2.line(out, (0, cy), (w_img, cy), c, 1, cv2.LINE_AA)
    cv2.line(out, (cx, 0), (cx, h_img), c, 1, cv2.LINE_AA)

def _make_hitmarker(gap=4, arm=8, with_circle=False, with_corners=False,
                    color_override=None):
    def fn(out, rx, ry, rw, rh, cx, cy, c, lw):
        col = color_override or c
        w   = lw + (1 if color_override else 0)
        cv2.line(out, (cx-gap-arm, cy-gap-arm), (cx-gap, cy-gap), col, w, cv2.LINE_AA)
        cv2.line(out, (cx+gap, cy-gap), (cx+gap+arm, cy-gap-arm), col, w, cv2.LINE_AA)
        cv2.line(out, (cx-gap, cy+gap), (cx-gap-arm, cy+gap+arm), col, w, cv2.LINE_AA)
        cv2.line(out, (cx+gap, cy+gap), (cx+gap+arm, cy+gap+arm), col, w, cv2.LINE_AA)
        if with_circle:
            cv2.circle(out, (cx, cy), gap, col, w, cv2.LINE_AA)
        if with_corners:
            _style_corners(out, rx, ry, rw, rh, cx, cy, c, lw)
    return fn

DRAW_STYLES: dict[str, Callable] = {
    "none":           _style_none,
    "rect":           _style_rect,
    "corners":        _style_corners,
    "circle":         _style_circle,
    "crosshair":      _style_crosshair,
    "dot":            _style_dot,
    "sniper":         _style_sniper,
    "hitmarker":      _make_hitmarker(),
    "hitmarker_red":  _make_hitmarker(color_override=(0, 0, 255)),
    "hitmarker_plus": _make_hitmarker(with_circle=True),
    "hitmarker_box":  _make_hitmarker(with_corners=True),
}

# ── Face-Filter Funktionen ────────────────────────────────────────────────────

def _apply_sunglasses(out, rx, ry, rw, rh):
    eye_y   = ry + int(rh * 0.38)
    eye_h   = int(rh * 0.18)
    left_x  = rx + int(rw * 0.08)
    right_x = rx + int(rw * 0.52)
    ew      = int(rw * 0.38)
    cv2.rectangle(out, (left_x, eye_y),  (left_x+ew,  eye_y+eye_h), (20,20,20), -1)
    cv2.rectangle(out, (right_x, eye_y), (right_x+ew, eye_y+eye_h), (20,20,20), -1)
    cv2.rectangle(out, (left_x, eye_y),  (left_x+ew,  eye_y+eye_h), (180,180,180), 2)
    cv2.rectangle(out, (right_x, eye_y), (right_x+ew, eye_y+eye_h), (180,180,180), 2)
    cv2.line(out, (left_x+ew, eye_y+eye_h//2), (right_x, eye_y+eye_h//2), (180,180,180), 2)
    cv2.line(out, (left_x, eye_y+eye_h//2), (rx, eye_y+eye_h//2), (180,180,180), 2)
    cv2.line(out, (right_x+ew, eye_y+eye_h//2), (rx+rw, eye_y+eye_h//2), (180,180,180), 2)

def _apply_hat(out, rx, ry, rw, rh):
    hat_w  = int(rw * 0.8)
    hat_h  = int(rh * 0.45)
    brim_h = int(rh * 0.08)
    hx     = rx + (rw - hat_w) // 2
    hy     = ry - hat_h - brim_h
    cv2.rectangle(out, (rx - int(rw*0.1), hy+hat_h),
                  (rx+rw+int(rw*0.1), hy+hat_h+brim_h), (30,30,30), -1)
    cv2.rectangle(out, (hx, hy), (hx+hat_w, hy+hat_h), (30,30,30), -1)
    cv2.rectangle(out, (hx, hy), (hx+hat_w, hy+hat_h), (80,80,80), 2)
    cv2.rectangle(out, (hx, hy+hat_h-int(hat_h*0.15)),
                  (hx+hat_w, hy+hat_h), (0,0,180), -1)

def _apply_clown_nose(out, rx, ry, rw, rh):
    nx = rx + rw // 2
    ny = ry + int(rh * 0.62)
    r  = max(8, int(rw * 0.09))
    cv2.circle(out, (nx, ny), r, (0, 0, 220), -1, cv2.LINE_AA)
    cv2.circle(out, (nx - r//3, ny - r//3), r//3, (80, 80, 255), -1, cv2.LINE_AA)

def _apply_pixel_blur(out, rx, ry, rw, rh):
    if rw < 4 or rh < 4:
        return
    roi      = out[ry:ry+rh, rx:rx+rw]
    small    = cv2.resize(roi, (max(1, rw//10), max(1, rh//10)),
                          interpolation=cv2.INTER_LINEAR)
    pixelated = cv2.resize(small, (rw, rh), interpolation=cv2.INTER_NEAREST)
    out[ry:ry+rh, rx:rx+rw] = pixelated

def _apply_matrix(out, rx, ry, rw, rh):
    import numpy as np, random # pyright: ignore[reportMissingImports]
    if rw < 4 or rh < 4:
        return
    overlay    = out[ry:ry+rh, rx:rx+rw].copy()
    green_mask = overlay.copy()
    green_mask[:] = (0, 0, 0)
    for _ in range(rw // 6):
        x  = random.randint(0, rw-1)
        y  = random.randint(0, rh-1)
        ch = chr(random.randint(0x30A0, 0x30FF))
        cv2.putText(green_mask, ch, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 70), 1, cv2.LINE_AA)
    blended = cv2.addWeighted(overlay, 0.55, green_mask, 0.85, 0)
    out[ry:ry+rh, rx:rx+rw] = blended

FACE_FILTERS: dict[str, Callable] = {
    "none":       None,
    "sunglasses": _apply_sunglasses,
    "hat":        _apply_hat,
    "clown":      _apply_clown_nose,
    "pixel":      _apply_pixel_blur,
    "matrix":     _apply_matrix,
}

# ── Hilfsfunktion Regenbogen ──────────────────────────────────────────────────

def _rainbow_bgr(t: float) -> Color:
    r = int((math.sin(t * 2.0)          + 1) * 127)
    g = int((math.sin(t * 2.0 + 2.094)  + 1) * 127)
    b = int((math.sin(t * 2.0 + 4.189)  + 1) * 127)
    return (b, g, r)

# ── RenderEngine ──────────────────────────────────────────────────────────────

class RenderEngine:
    def __init__(self, cfg, camera, detection, metrics=None):
        self.cfg       = cfg
        self.camera    = camera
        self.detection = detection
        self.metrics   = metrics
        self._stop     = threading.Event()
        self.frame_q: Queue = Queue(maxsize=1)
        self.status    = {"faces": 0, "fps": 0}
        self._start_time = time.monotonic()

        self.box_style   = "corners"
        self.face_filter = "none"
        self.last_faces  = []
        self.disco_mode  = False
        self.matrix_mode = False

        self.auto_snapshot     = False
        self.auto_snapshot_dir = "snapshots"
        self._prev_face_count  = 0
        self._face_highscore   = 0
        self._total_faces_seen = 0

        self._recorder  = None
        self._recording = False
        self._rec_lock  = threading.Lock()

    # ── Recording ─────────────────────────────────────────────────────────────

    def start_recording(self, path: str = "recording.avi"):
        with self._rec_lock:
            if self._recording:
                return False
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self._recorder = cv2.VideoWriter(
                path, fourcc, self.cfg.target_fps,
                (self.cfg.cam_w, self.cfg.cam_h))
            self._recording = True
            log.info("Recording gestartet: %s", path)
            return True

    def stop_recording(self):
        with self._rec_lock:
            if not self._recording:
                return False
            self._recording = False
            if self._recorder:
                self._recorder.release()
                self._recorder = None
            log.info("Recording gestoppt")
            return True

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw(self, out, tracked_faces):
        sx, sy    = self.cfg.scale_x, self.cfg.scale_y
        style_fn  = DRAW_STYLES.get(self.box_style, _style_corners)
        filter_fn = FACE_FILTERS.get(self.face_filter)
        lw        = 2
        t         = time.monotonic()

        for tf in tracked_faces:
            x, y, w, h = tf["box"]
            rx, ry = int(x * sx), int(y * sy)
            rw, rh = int(w * sx), int(h * sy)
            cx, cy = rx + rw // 2, ry + rh // 2

            if self.disco_mode:
                c = _rainbow_bgr(t + tf["id"] * 0.7)
            else:
                c = self.cfg.box_color_bgr

            if self.matrix_mode:
                _apply_matrix(out, rx, ry, rw, rh)
                continue

            if filter_fn:
                try:
                    filter_fn(out, rx, ry, rw, rh)
                except Exception as e:
                    log.debug("Filter-Fehler: %s", e)

            style_fn(out, rx, ry, rw, rh, cx, cy, c, lw)

        if self._face_highscore > 0:
            cv2.putText(out, f"Best: {self._face_highscore}",
                        (8, out.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200,200,200), 1, cv2.LINE_AA)

    # ── Auto-Snapshot ─────────────────────────────────────────────────────────

    def _check_auto_snapshot(self, out, face_count: int):
        if not self.auto_snapshot:
            return
        if face_count > self._prev_face_count:
            os.makedirs(self.auto_snapshot_dir, exist_ok=True)
            ts   = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self.auto_snapshot_dir, f"face_{ts}.jpg")
            cv2.imwrite(path, out)
            log.info("Auto-Snapshot: %s", path)
            self._total_faces_seen += (face_count - self._prev_face_count)
        self._prev_face_count = face_count
        if face_count > self._face_highscore:
            self._face_highscore = face_count

    # ── Main Loop ─────────────────────────────────────────────────────────────

    def run(self):
        cnt, t0 = 0, time.monotonic()
        last_r  = 0.0
        while not self._stop.is_set():
            now  = time.monotonic()
            wait = self.cfg.frame_time - (now - last_r)
            if wait > 0:
                time.sleep(wait)
                continue
            last_r = time.monotonic()
            frame  = self.camera.get_frame()
            if frame is None:
                continue
            out   = frame.copy()
            faces = self.detection.get_faces()
            self.last_faces = faces
            self._draw(out, faces)
            self._check_auto_snapshot(out, len(faces))

            cnt += 1
            elapsed = time.monotonic() - t0
            if elapsed >= 1.0:
                fps = round(cnt / elapsed)
                self.status.update({
                    "fps":         fps,
                    "faces":       len(faces),
                    "highscore":   self._face_highscore,
                    "total_seen":  self._total_faces_seen,
                    "disco":       self.disco_mode,
                    "matrix":      self.matrix_mode,
                    "face_filter": self.face_filter,
                    "recording":   self._recording,
                })
                if self.metrics:
                    self.metrics["render_fps"].set(fps)
                cnt, t0 = 0, time.monotonic()

            with self._rec_lock:
                if self._recording and self._recorder:
                    self._recorder.write(out)

            ok, buf = cv2.imencode(".jpg", out,
                                   [cv2.IMWRITE_JPEG_QUALITY, self.cfg.jpeg_quality])
            if ok:
                if self.frame_q.full():
                    try:
                        self.frame_q.get_nowait()
                    except Exception:
                        pass
                self.frame_q.put_nowait(buf.tobytes())

    def get_jpeg(self) -> Optional[bytes]:
        try:
            return self.frame_q.get_nowait()
        except Exception:
            return None

    def get_snapshot(self) -> Optional[bytes]:
        frame = self.camera.get_frame()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".png", frame)
        return buf.tobytes() if ok else None

    def uptime(self) -> float:
        return time.monotonic() - self._start_time

    def stop(self):
        self.stop_recording()
        self._stop.set()

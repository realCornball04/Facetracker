import json, time, logging, io
from flask import Flask, Response, make_response, request, send_file, jsonify # pyright: ignore[reportMissingImports]
from flask_cors import CORS # pyright: ignore[reportMissingModuleSource]
from prometheus_client import make_wsgi_app, Gauge, Histogram, Counter # pyright: ignore[reportMissingImports]
from werkzeug.middleware.dispatcher import DispatcherMiddleware # pyright: ignore[reportMissingImports]
import cv2 # pyright: ignore[reportMissingImports]

log = logging.getLogger("facetrack.web")

METRICS = {
    "face_count":     Gauge("facetrack_face_count", "Erkannte Gesichter"),
    "render_fps":     Gauge("facetrack_render_fps", "Render FPS"),
    "frame_drops":    Counter("facetrack_frame_drops_total", "Gedropte Frames"),
    "detect_latency": Histogram("facetrack_detect_latency_seconds",
                                "Detektions-Latenz",
                                buckets=[.005,.01,.025,.05,.1,.25]),
}

_box_style = {"value": "corners"}


def _check_auth(cfg) -> bool:
    if not cfg.auth_user:
        return True
    auth = request.authorization
    return bool(auth and auth.username == cfg.auth_user
                and auth.password == cfg.auth_pass)


def _require_auth():
    return Response("Authentifizierung erforderlich", 401,
                    {"WWW-Authenticate": 'Basic realm="FaceTrack"'})


def create_app(cfg, renderer, camera_manager, detection):
    from web.template import HTML
    flask_app = Flask(__name__)

    origins = [o.strip() for o in cfg.allowed_origins.split(",")] \
        if cfg.allowed_origins != "*" else "*"
    CORS(flask_app, resources={r"/*": {"origins": origins}})

    # ── Öffentlich ────────────────────────────────────────────────────────────

    @flask_app.route("/")
    def index():
        r = make_response(HTML)
        r.headers.update({"Cache-Control": "no-cache, no-store",
                           "Pragma": "no-cache", "Expires": "0"})
        return r

    @flask_app.route("/health")
    def health():
        cam_ok = camera_manager.is_alive(max_age=2.0)
        det_ok = detection.is_running()
        fps_ok = renderer.status.get("fps", 0) > 0
        status = "ok" if (cam_ok and det_ok and fps_ok) else "degraded"
        return jsonify({
            "status":       status,
            "uptime_s":     round(renderer.uptime(), 1),
            "fps":          renderer.status.get("fps", 0),
            "faces":        renderer.status.get("faces", 0),
            "camera_ok":    cam_ok,
            "detection_ok": det_ok,
            "fps_ok":       fps_ok,
        })

    @flask_app.route("/cameras")
    def cameras():
        available = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return jsonify({"cameras": available})

    # ── Geschützt ─────────────────────────────────────────────────────────────

    @flask_app.route("/video_feed")
    def video_feed():
        if not _check_auth(cfg):
            return _require_auth()
        def gen():
            BND = (b"--frame\r\nContent-Type: image/jpeg\r\n"
                   b"Cache-Control: no-cache\r\n\r\n")
            END = b"\r\n"
            last = 0.0
            while True:
                now = time.monotonic()
                if now - last < cfg.frame_time:
                    time.sleep(0.004)
                    continue
                last = now
                f = renderer.get_jpeg()
                if f:
                    yield BND + f + END
        r = Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")
        r.headers.update({"Cache-Control": "no-cache, no-store",
                           "X-Accel-Buffering": "no"})
        return r

    @flask_app.route("/events")
    def events():
        if not _check_auth(cfg):
            return _require_auth()
        def sse_gen():
            while True:
                faces = renderer.last_faces
                data  = {
                    **renderer.status,
                    "uptime_s":    round(renderer.uptime()),
                    "faces_coords": [
                        {"id": f["id"], "box": list(f["box"])} for f in faces
                    ],
                    "frame_w":  cfg.cam_w,
                    "frame_h":  cfg.cam_h,
                    "recording": renderer._recording,
                }
                yield f"data: {json.dumps(data)}\n\n"
                time.sleep(0.5)
        return Response(sse_gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache",
                                 "X-Accel-Buffering": "no"})

    @flask_app.route("/snapshot")
    def snapshot():
        if not _check_auth(cfg):
            return _require_auth()
        data = renderer.get_snapshot()
        if data is None:
            return jsonify({"error": "Kein Frame verfügbar"}), 503
        return send_file(io.BytesIO(data), mimetype="image/png",
                         download_name="snapshot.png", as_attachment=True)

    @flask_app.route("/status")
    def status():
        if not _check_auth(cfg):
            return _require_auth()
        r = make_response(jsonify(renderer.status))
        r.headers["Cache-Control"] = "no-cache"
        return r

    @flask_app.route("/set_style", methods=["POST"])
    def set_style():
        if not _check_auth(cfg):
            return _require_auth()
        data  = request.get_json(silent=True) or {}
        style = data.get("style", "corners")
        _box_style["value"] = style
        renderer.box_style  = style
        log.info("Box-Style: %s", style)
        return jsonify({"ok": True, "style": style})

    @flask_app.route("/set_color", methods=["POST"])
    def set_color():
        if not _check_auth(cfg):
            return _require_auth()
        data  = request.get_json(silent=True) or {}
        color = data.get("color", "#FFFFFF")
        cfg.box_color = color
        log.info("Box-Farbe: %s", color)
        return jsonify({"ok": True, "color": color})

    @flask_app.route("/set_camera", methods=["POST"])
    def set_camera():
        if not _check_auth(cfg):
            return _require_auth()
        data   = request.get_json(silent=True) or {}
        cam_id = data.get("id")
        if cam_id is None or not isinstance(cam_id, int):
            return jsonify({"error": "Ungültige Kamera-ID"}), 400
        camera_manager.switch_camera(cam_id)
        return jsonify({"ok": True, "camera_id": cam_id})

    @flask_app.route("/set_filter", methods=["POST"])
    def set_filter():
        if not _check_auth(cfg):
            return _require_auth()
        data = request.get_json(silent=True) or {}
        f    = data.get("filter", "none")
        if f not in ["none", "sunglasses", "hat", "clown", "pixel", "matrix"]:
            return jsonify({"error": "Unbekannter Filter"}), 400
        renderer.face_filter = f
        log.info("Face-Filter: %s", f)
        return jsonify({"ok": True, "filter": f})

    @flask_app.route("/set_disco", methods=["POST"])
    def set_disco():
        if not _check_auth(cfg):
            return _require_auth()
        data  = request.get_json(silent=True) or {}
        state = bool(data.get("enabled", False))
        renderer.disco_mode = state
        log.info("Disco-Modus: %s", state)
        return jsonify({"ok": True, "disco": state})

    @flask_app.route("/set_matrix", methods=["POST"])
    def set_matrix():
        if not _check_auth(cfg):
            return _require_auth()
        data  = request.get_json(silent=True) or {}
        state = bool(data.get("enabled", False))
        renderer.matrix_mode = state
        log.info("Matrix-Modus: %s", state)
        return jsonify({"ok": True, "matrix": state})

    @flask_app.route("/set_auto_snapshot", methods=["POST"])
    def set_auto_snapshot():
        if not _check_auth(cfg):
            return _require_auth()
        data  = request.get_json(silent=True) or {}
        state = bool(data.get("enabled", False))
        renderer.auto_snapshot = state
        log.info("Auto-Snapshot: %s", state)
        return jsonify({"ok": True, "auto_snapshot": state})

    @flask_app.route("/recording/start", methods=["POST"])
    def recording_start():
        if not _check_auth(cfg):
            return _require_auth()
        data = request.get_json(silent=True) or {}
        path = data.get("path", "recording.avi")
        ok   = renderer.start_recording(path)
        return jsonify({"ok": ok, "recording": True, "path": path})

    @flask_app.route("/recording/stop", methods=["POST"])
    def recording_stop():
        if not _check_auth(cfg):
            return _require_auth()
        ok = renderer.stop_recording()
        return jsonify({"ok": ok, "recording": False})

    @flask_app.route("/stats")
    def stats():
        if not _check_auth(cfg):
            return _require_auth()
        return jsonify({
            "highscore":   renderer._face_highscore,
            "total_seen":  renderer._total_faces_seen,
            "uptime_s":    round(renderer.uptime(), 1),
            "disco":       renderer.disco_mode,
            "matrix":      renderer.matrix_mode,
            "face_filter": renderer.face_filter,
            "recording":   renderer._recording,
        })

    flask_app.wsgi_app = DispatcherMiddleware(
        flask_app.wsgi_app, {"/metrics": make_wsgi_app()}
    )
    return flask_app

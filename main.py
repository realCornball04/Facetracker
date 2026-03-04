#!/usr/bin/env python3
import argparse, signal, sys, threading, os

def parse_args():
    p = argparse.ArgumentParser(description="FaceTrack v22")
    p.add_argument("--camera-id", type=int,   default=None)
    p.add_argument("--port",      type=int,   default=None)
    p.add_argument("--fps",       type=int,   default=None)
    p.add_argument("--detector",  choices=["haar", "yunet", "mediapipe"], default=None)
    p.add_argument("--debug",     action="store_true",
                   help="Werkzeug Debug-Modus (nur Entwicklung!)")
    return p.parse_args()

def main():
    os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "0")
    args = parse_args()

    from config import Config, setup_logging
    cfg = Config()

    if args.camera_id is not None: cfg.cam_id     = args.camera_id
    if args.port      is not None: cfg.port       = args.port
    if args.fps       is not None: cfg.target_fps = args.fps
    if args.detector  is not None: cfg.detector   = args.detector
    if args.debug:                 cfg.log_level  = "DEBUG"

    log = setup_logging(cfg)
    log.info("FaceTrack v22 startet | Detektor=%s Port=%d", cfg.detector, cfg.port)

    from camera     import CameraManager
    from detection  import DetectionEngine
    from renderer   import RenderEngine
    from web.server import create_app, METRICS

    camera    = CameraManager(cfg)
    detection = DetectionEngine(cfg, camera, METRICS)
    renderer  = RenderEngine(cfg, camera, detection, METRICS)
    app       = create_app(cfg, renderer, camera, detection)

    threads = [
        threading.Thread(target=camera.run,    name="camera",    daemon=True),
        threading.Thread(target=detection.run,  name="detection", daemon=True),
        threading.Thread(target=renderer.run,   name="renderer",  daemon=True),
    ]

    def shutdown(sig, _frame):
        log.info("Shutdown (%s)...", signal.Signals(sig).name)
        camera.stop(); detection.stop(); renderer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for t in threads:
        t.start()

    log.info("FaceTrack läuft → http://localhost:%d", cfg.port)
    app.run(
        host=cfg.host,
        port=cfg.port,
        debug=args.debug,
        threaded=True,
        use_reloader=False,
    )

if __name__ == "__main__":
    main()

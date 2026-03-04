import cv2, numpy as np, time, threading, logging # pyright: ignore[reportMissingImports]
from queue import Queue
from typing import List, Tuple, Dict

log = logging.getLogger("facetrack.detection")
Box = Tuple[int, int, int, int]
TrackedFace = Dict

class DetectionEngine:
    def __init__(self, cfg, camera, metrics=None):
        self.cfg = cfg
        self.camera = camera
        self.metrics = metrics
        self._stop = threading.Event()
        self.faces_q: Queue = Queue(maxsize=1)
        self._prev_faces: List[Box] = []
        self._prev_gray = None
        self._tracked: List[TrackedFace] = []
        self._next_id: int = 1
        self._thread: threading.Thread | None = None

    def _build_detector(self):
        if self.cfg.detector == "yunet":
            det = cv2.FaceDetectorYN.create(
                self.cfg.yunet_model, "",
                (self.cfg.detect_w, self.cfg.detect_h),
                self.cfg.yunet_score, 0.3, 5000)
            log.info("Detektor: YuNet")
            return det
        if self.cfg.detector == "mediapipe":
            try:
                import mediapipe as mp # pyright: ignore[reportMissingImports]
                log.info("Detektor: MediaPipe")
                return mp.solutions.face_detection.FaceDetection(
                    model_selection=0, min_detection_confidence=0.6)
            except ImportError:
                log.warning("MediaPipe nicht installiert — Fallback auf Haar")
        log.info("Detektor: Haar Cascade")
        return None

    @staticmethod
    def nms(boxes: List[Box], overlap: float = 0.4) -> List[Box]:
        if not boxes:
            return []
        boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        kept: List[Box] = []
        for b in boxes:
            bx, by, bw, bh = b
            skip = False
            for k in kept:
                kx, ky, kw, kh = k
                ix = max(0, min(bx+bw, kx+kw) - max(bx, kx))
                iy = max(0, min(by+bh, ky+kh) - max(by, ky))
                inter = ix * iy
                union = bw*bh + kw*kh - inter
                if union > 0 and inter / union > overlap:
                    skip = True
                    break
            if not skip:
                kept.append(b)
        return kept

    @staticmethod
    def smooth_boxes(new: List[Box], old: List[Box], alpha: float) -> List[Box]:
        if not old or not new:
            return [(int(x), int(y), int(w), int(h)) for x, y, w, h in new]
        try:
            from scipy.spatial import cKDTree # pyright: ignore[reportMissingImports]
            import numpy as np # pyright: ignore[reportMissingImports]
            old_centers = np.array([(ox+ow//2, oy+oh//2) for ox, oy, ow, oh in old])
            new_centers = np.array([(nx+nw//2, ny+nh//2) for nx, ny, nw, nh in new])
            tree = cKDTree(old_centers)
            dists, idxs = tree.query(new_centers, k=1)
            result = []
            for i, (nx, ny, nw, nh) in enumerate(new):
                ox, oy, ow, oh = old[idxs[i]]
                a = min(1.0, alpha + dists[i] / 100.0)
                result.append((
                    int(a*nx+(1-a)*ox), int(a*ny+(1-a)*oy),
                    int(a*nw+(1-a)*ow), int(a*nh+(1-a)*oh)))
            return result
        except ImportError:
            pass
        result, used = [], set()
        for nx, ny, nw, nh in new:
            cx, cy = nx+nw//2, ny+nh//2
            bi, bd = -1, float("inf")
            for i, (ox, oy, ow, oh) in enumerate(old):
                if i in used:
                    continue
                d = (cx-(ox+ow//2))**2 + (cy-(oy+oh//2))**2
                if d < bd:
                    bd, bi = d, i
            if bi >= 0:
                ox, oy, ow, oh = old[bi]
                used.add(bi)
                a = min(1.0, alpha + bd**0.5/100.0)
                result.append((
                    int(a*nx+(1-a)*ox), int(a*ny+(1-a)*oy),
                    int(a*nw+(1-a)*ow), int(a*nh+(1-a)*oh)))
            else:
                result.append((int(nx), int(ny), int(nw), int(nh)))
        return result

    def _assign_ids(self, boxes: List[Box]) -> List[TrackedFace]:
        MAX_DIST = 80
        new_tracked: List[TrackedFace] = []
        used_old = set()
        for box in boxes:
            bx, by, bw, bh = box
            cx, cy = bx+bw//2, by+bh//2
            best_i, best_d = -1, float("inf")
            for i, tf in enumerate(self._tracked):
                if i in used_old:
                    continue
                ox, oy, ow, oh = tf["box"]
                d = ((cx-(ox+ow//2))**2 + (cy-(oy+oh//2))**2)**0.5
                if d < best_d:
                    best_d, best_i = d, i
            if best_i >= 0 and best_d < MAX_DIST:
                used_old.add(best_i)
                new_tracked.append({"id": self._tracked[best_i]["id"], "box": box})
            else:
                new_tracked.append({"id": self._next_id, "box": box})
                self._next_id += 1
        self._tracked = new_tracked
        return new_tracked

    def _frame_changed(self, gray: np.ndarray) -> bool:
        if self._prev_gray is None:
            self._prev_gray = gray
            return True
        diff = cv2.absdiff(gray, self._prev_gray)
        changed = np.mean(diff) > self.cfg.diff_thresh
        if changed:
            self._prev_gray = gray
        return changed

    def _detect_haar(self, gray, c_front, c_profile, dw: int) -> List[Box]:
        new: List[Box] = []
        rf = c_front.detectMultiScale(
            gray, 1.2, 5, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
        if len(rf) > 0:
            new += [tuple(b) for b in rf]
        rp = c_profile.detectMultiScale(
            gray, 1.2, 4, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
        if len(rp) > 0:
            new += [tuple(b) for b in rp]
        gray_flip = cv2.flip(gray, 1)
        rp2 = c_profile.detectMultiScale(
            gray_flip, 1.2, 4, minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
        if len(rp2) > 0:
            for (x, y, w, h) in rp2:
                new.append((dw - x - w, y, w, h))
        return new

    def _detect_yunet(self, frame, det) -> List[Box]:
        _, faces = det.detect(frame)
        if faces is None:
            return []
        return [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]

    def _detect_mediapipe(self, frame, det) -> List[Box]:
        import mediapipe as mp # pyright: ignore[reportMissingImports]
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = det.process(rgb)
        boxes = []
        if res.detections:
            for d in res.detections:
                bb = d.location_data.relative_bounding_box
                x  = max(0, int(bb.xmin * w))
                y  = max(0, int(bb.ymin * h))
                bw = int(bb.width * w)
                bh = int(bb.height * h)
                boxes.append((x, y, bw, bh))
        return boxes

    def run(self):
        self._thread = threading.current_thread()
        det = self._build_detector()
        c_front = c_profile = None
        if self.cfg.detector == "haar":
            c_front = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
            c_profile = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_profileface.xml")
        last = 0.0
        while not self._stop.is_set():
            now = time.monotonic()
            remaining = self.cfg.detect_interval - (now - last)
            if remaining > 0:
                time.sleep(remaining)
                continue
            last = time.monotonic()
            frame = self.camera.get_frame()
            if frame is None:
                continue
            t_start = time.monotonic()
            small = cv2.resize(frame, (self.cfg.detect_w, self.cfg.detect_h),
                               interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            cv2.equalizeHist(gray, gray)
            if not self._frame_changed(gray):
                continue
            if self.cfg.detector == "yunet":
                new = self._detect_yunet(small, det)
            elif self.cfg.detector == "mediapipe":
                new = self._detect_mediapipe(small, det)
            else:
                new = self._detect_haar(gray, c_front, c_profile, self.cfg.detect_w)
            new     = self.nms(new)
            sm      = self.smooth_boxes(new, self._prev_faces, self.cfg.smooth_alpha)
            self._prev_faces = sm
            tracked = self._assign_ids(sm)
            if self.metrics:
                self.metrics["detect_latency"].observe(time.monotonic() - t_start)
                self.metrics["face_count"].set(len(sm))
            if self.faces_q.full():
                try:
                    self.faces_q.get_nowait()
                except Exception:
                    pass
            self.faces_q.put_nowait(tracked)

    def get_faces(self) -> List[TrackedFace]:
        try:
            return self.faces_q.get_nowait()
        except Exception:
            return self._tracked

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def stop(self):
        self._stop.set()

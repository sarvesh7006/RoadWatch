import os
import threading
import time
from pathlib import Path
from .database import ROOT

MODEL_PATH = Path(os.getenv('MODEL_PATH', ROOT / 'models' / 'pothole.pt'))


def severity_for(area_ratio):
    # Relative image footprint is a triage proxy, never a physical depth estimate.
    return 'high' if area_ratio >= .08 else 'medium' if area_ratio >= .025 else 'low'


class Detector:
    def __init__(self):
        self.model = None
        self.lock = threading.Lock()

    def predict(self, image, confidence):
        if not MODEL_PATH.is_file():
            raise FileNotFoundError('Pothole model is missing. Run: .venv/bin/python scripts/download_model.py')
        with self.lock:
            if self.model is None:
                from ultralytics import YOLO
                self.model = YOLO(str(MODEL_PATH))
            start = time.perf_counter()
            result = self.model.predict(image, imgsz=640, rect=False, conf=confidence, iou=.5,
                                        device=os.getenv('YOLO_DEVICE', 'cpu'), verbose=False, max_det=50)[0]
            elapsed = (time.perf_counter() - start) * 1000
            width, height = image.size
            detections = []
            for box in result.boxes:
                label = str(result.names[int(box.cls[0])]).lower()
                if 'pothole' not in label and label != 'd40':
                    continue
                xyxy = [round(float(v), 1) for v in box.xyxy[0].tolist()]
                area = (xyxy[2]-xyxy[0]) * (xyxy[3]-xyxy[1]) / (width*height)
                detections.append({'box': xyxy, 'confidence': round(float(box.conf[0]), 4),
                                   'severity': severity_for(area), 'area_ratio': round(area, 5)})
            return detections, round(elapsed, 1)


detector = Detector()

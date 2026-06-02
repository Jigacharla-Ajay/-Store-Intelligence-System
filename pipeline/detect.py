"""
Person detector using YOLOv8.

Detects people in CCTV frames and returns bounding boxes
with confidence scores. Falls back to a mock detector
if ultralytics is not installed.
"""

import logging

logger = logging.getLogger(__name__)


class PersonDetector:
    """YOLOv8-based person detector with mock fallback."""

    def __init__(self, model_name: str = "yolov8n.pt", conf_threshold: float = 0.5):
        self.conf_threshold = conf_threshold
        self.model = None

        try:
            from ultralytics import YOLO
            self.model = YOLO(model_name)
            logger.info(f"Loaded YOLO model: {model_name}")
        except ImportError:
            logger.warning("ultralytics not installed. Using mock detector.")
        except Exception as e:
            logger.warning(f"Failed to load YOLO model: {e}. Using mock detector.")

    def detect(self, frame) -> list:
        """
        Detect people in a frame.

        Returns list of dicts with keys:
          - bbox: [x1, y1, x2, y2]
          - confidence: float (0-1)
          - class_id: int (0 = person)
        """
        if self.model is not None:
            return self._detect_yolo(frame)
        else:
            return self._detect_mock(frame)

    def _detect_yolo(self, frame) -> list:
        """Run YOLO inference on a frame."""
        results = self.model(frame, verbose=False, conf=self.conf_threshold)
        detections = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id != 0:  # 0 = person in COCO
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detections.append({
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "confidence": round(conf, 3),
                    "class_id": 0,
                })

        return detections

    def _detect_mock(self, frame) -> list:
        """
        Mock detector for testing without GPU/YOLO.
        Generates synthetic detections based on frame dimensions.
        """
        import random

        if frame is None:
            return []

        h, w = frame.shape[:2]
        num_people = random.randint(1, 5)
        detections = []

        for i in range(num_people):
            cx = random.randint(50, w - 50)
            cy = random.randint(50, h - 50)
            bw = random.randint(30, 80)
            bh = random.randint(60, 160)

            detections.append({
                "bbox": [cx - bw//2, cy - bh//2, cx + bw//2, cy + bh//2],
                "confidence": round(random.uniform(0.6, 0.98), 3),
                "class_id": 0,
            })

        return detections

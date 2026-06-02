"""
Simple object tracker using centroid-based tracking.

Assigns consistent visitor_ids to detections across frames.
Uses IoU (Intersection over Union) for association and maintains
track state (active, lost, removed).

For production, DeepSORT would replace this — this is a lightweight
fallback that works without deep appearance embeddings.
"""

import uuid
from collections import OrderedDict

import numpy as np


class Track:
    """A single tracked object."""

    def __init__(self, track_id: str, bbox: list, confidence: float):
        self.track_id = track_id
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.confidence = confidence
        self.age = 0  # Frames since creation
        self.lost_frames = 0  # Frames since last detection
        self.centroid_history = []  # Track path
        self._update_centroid()

    def _update_centroid(self):
        x1, y1, x2, y2 = self.bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        self.centroid = (cx, cy)
        self.centroid_history.append((cx, cy))

    def update(self, bbox: list, confidence: float):
        self.bbox = bbox
        self.confidence = confidence
        self.lost_frames = 0
        self.age += 1
        self._update_centroid()

    def mark_lost(self):
        self.lost_frames += 1
        self.age += 1


class CentroidTracker:
    """
    Simple IoU-based multi-object tracker.

    Assigns each detection to the closest existing track using IoU.
    Creates new tracks for unmatched detections.
    Removes tracks after max_lost_frames.
    """

    def __init__(self, max_lost_frames: int = 30, iou_threshold: float = 0.3):
        self.tracks = OrderedDict()
        self.max_lost_frames = max_lost_frames
        self.iou_threshold = iou_threshold
        self._next_id = 0

    def _generate_id(self) -> str:
        """Generate a visitor ID."""
        vid = f"VIS_{self._next_id:04d}"
        self._next_id += 1
        return vid

    def update(self, detections: list) -> list:
        """
        Update tracks with new detections.

        Args:
            detections: list of {"bbox": [x1,y1,x2,y2], "confidence": float}

        Returns:
            list of active tracks as dicts with track_id, bbox, centroid, confidence
        """
        if len(detections) == 0:
            # Mark all tracks as lost
            to_remove = []
            for tid, track in self.tracks.items():
                track.mark_lost()
                if track.lost_frames > self.max_lost_frames:
                    to_remove.append(tid)
            for tid in to_remove:
                del self.tracks[tid]
            return self._get_active_tracks()

        det_bboxes = [d["bbox"] for d in detections]
        det_confs = [d["confidence"] for d in detections]

        if len(self.tracks) == 0:
            # Create new tracks for all detections
            for bbox, conf in zip(det_bboxes, det_confs):
                tid = self._generate_id()
                self.tracks[tid] = Track(tid, bbox, conf)
            return self._get_active_tracks()

        # Compute IoU matrix between existing tracks and new detections
        track_ids = list(self.tracks.keys())
        track_bboxes = [self.tracks[tid].bbox for tid in track_ids]

        iou_matrix = self._compute_iou_matrix(track_bboxes, det_bboxes)

        # Greedy matching: assign best IoU pairs
        matched_tracks = set()
        matched_dets = set()

        # Sort by IoU descending
        pairs = []
        for i in range(len(track_ids)):
            for j in range(len(det_bboxes)):
                pairs.append((iou_matrix[i][j], i, j))
        pairs.sort(key=lambda x: -x[0])

        for iou_val, i, j in pairs:
            if i in matched_tracks or j in matched_dets:
                continue
            if iou_val < self.iou_threshold:
                break
            self.tracks[track_ids[i]].update(det_bboxes[j], det_confs[j])
            matched_tracks.add(i)
            matched_dets.add(j)

        # Mark unmatched tracks as lost
        to_remove = []
        for i, tid in enumerate(track_ids):
            if i not in matched_tracks:
                self.tracks[tid].mark_lost()
                if self.tracks[tid].lost_frames > self.max_lost_frames:
                    to_remove.append(tid)
        for tid in to_remove:
            del self.tracks[tid]

        # Create new tracks for unmatched detections
        for j in range(len(det_bboxes)):
            if j not in matched_dets:
                tid = self._generate_id()
                self.tracks[tid] = Track(tid, det_bboxes[j], det_confs[j])

        return self._get_active_tracks()

    def _get_active_tracks(self) -> list:
        """Return active (non-lost) tracks."""
        result = []
        for tid, track in self.tracks.items():
            if track.lost_frames == 0:
                result.append({
                    "track_id": track.track_id,
                    "bbox": track.bbox,
                    "centroid": track.centroid,
                    "confidence": track.confidence,
                })
        return result

    @staticmethod
    def _compute_iou_matrix(boxes_a: list, boxes_b: list) -> list:
        """Compute IoU between two sets of bounding boxes."""
        matrix = []
        for a in boxes_a:
            row = []
            for b in boxes_b:
                iou = CentroidTracker._iou(a, b)
                row.append(iou)
            matrix.append(row)
        return matrix

    @staticmethod
    def _iou(box_a: list, box_b: list) -> float:
        """Compute IoU between two boxes [x1, y1, x2, y2]."""
        x1 = max(box_a[0], box_b[0])
        y1 = max(box_a[1], box_b[1])
        x2 = min(box_a[2], box_b[2])
        y2 = min(box_a[3], box_b[3])

        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter

        return inter / union if union > 0 else 0.0

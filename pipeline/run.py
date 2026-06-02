"""
Main detection pipeline runner.

Processes CCTV video files through the detection → tracking → event emission pipeline.
Sends batched events to the API via HTTP POST.

Usage:
    python -m pipeline.run --videos-dir ./data --api-url http://localhost:8000
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path

import httpx

from pipeline.detect import PersonDetector
from pipeline.tracker import CentroidTracker
from pipeline.emit import emit_events
from pipeline.store_layout import STORE_LAYOUT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")

# Configuration
BATCH_SIZE = 50
FRAME_SKIP = 3  # Process every Nth frame for performance
API_TIMEOUT = 10


def process_video(
    video_path: str,
    camera_id: str,
    detector: PersonDetector,
    api_url: str,
    store_id: str = "STORE_BLR_002",
):
    """
    Process a single video file through the detection pipeline.

    Args:
        video_path: Path to the MP4 file
        camera_id: Camera identifier for this video
        detector: PersonDetector instance
        api_url: Base URL of the API
        store_id: Store identifier
    """
    try:
        import cv2
    except ImportError:
        logger.error("OpenCV (cv2) not installed. Install with: pip install opencv-python")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"Processing {camera_id}: {video_path} ({total_frames} frames, {fps:.0f} FPS)")

    tracker = CentroidTracker(max_lost_frames=int(fps * 2))
    previous_tracks = {}
    event_buffer = []
    frame_count = 0
    events_sent = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        # Skip frames for performance
        if frame_count % FRAME_SKIP != 0:
            continue

        # Detect people
        detections = detector.detect(frame)

        # Update tracker
        current_tracks = tracker.update(detections)

        # Emit events from state transitions
        events = emit_events(
            camera_id=camera_id,
            current_tracks=current_tracks,
            previous_tracks=previous_tracks,
            store_id=store_id,
        )

        # Update previous tracks
        previous_tracks = {t["track_id"]: t for t in current_tracks}

        # Buffer events
        event_buffer.extend(events)

        # Send batch when buffer is full
        if len(event_buffer) >= BATCH_SIZE:
            sent = _send_batch(api_url, event_buffer)
            events_sent += sent
            event_buffer = []

        # Progress log every 500 frames
        if frame_count % 500 == 0:
            pct = (frame_count / total_frames * 100) if total_frames > 0 else 0
            logger.info(f"  {camera_id}: {frame_count}/{total_frames} frames ({pct:.0f}%), {events_sent} events sent")

    # Send remaining events
    if event_buffer:
        sent = _send_batch(api_url, event_buffer)
        events_sent += sent

    cap.release()
    logger.info(f"Completed {camera_id}: {frame_count} frames processed, {events_sent} events sent")


def _send_batch(api_url: str, events: list) -> int:
    """Send a batch of events to the API. Returns count of accepted events."""
    if not events:
        return 0

    try:
        r = httpx.post(
            f"{api_url}/events/ingest",
            json={"events": events},
            timeout=API_TIMEOUT,
        )
        if r.status_code in (200, 207):
            data = r.json()
            accepted = data.get("accepted", 0)
            duplicates = data.get("duplicate", 0)
            if duplicates > 0:
                logger.debug(f"Batch: {accepted} accepted, {duplicates} duplicates")
            return accepted
        else:
            logger.warning(f"API returned {r.status_code}: {r.text[:200]}")
            return 0
    except Exception as e:
        logger.error(f"Failed to send batch: {e}")
        return 0


def find_videos(videos_dir: str) -> dict:
    """
    Find video files and map them to camera IDs using the store layout.

    Returns dict of {camera_id: video_path}.
    """
    result = {}
    video_dir = Path(videos_dir)

    for cam_id, cam_config in STORE_LAYOUT["cameras"].items():
        source = cam_config["source"]
        video_path = video_dir / source

        if video_path.exists():
            result[cam_id] = str(video_path)
        else:
            logger.warning(f"Video not found for {cam_id}: {video_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Store Intelligence Detection Pipeline")
    parser.add_argument("--videos-dir", default="./data", help="Directory containing CCTV videos")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--store-id", default="STORE_BLR_002", help="Store ID")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO model to use")
    parser.add_argument("--conf", type=float, default=0.5, help="Detection confidence threshold")
    args = parser.parse_args()

    logger.info("=== Store Intelligence Detection Pipeline ===")
    logger.info(f"Videos: {args.videos_dir}")
    logger.info(f"API: {args.api_url}")
    logger.info(f"Store: {args.store_id}")

    # Check API health with retry logic
    api_ready = False
    max_retries = 10
    for i in range(max_retries):
        try:
            r = httpx.get(f"{args.api_url}/health", timeout=5)
            if r.status_code == 200:
                logger.info("API is healthy and ready")
                api_ready = True
                break
            else:
                logger.warning(f"API health check returned {r.status_code}. Retrying...")
        except Exception as e:
            logger.info(f"Waiting for API to become available ({i+1}/{max_retries})...")
        
        time.sleep(3)
        
    if not api_ready:
        logger.error(f"Cannot reach API at {args.api_url} after {max_retries} attempts.")
        logger.error("Start the API first: python -m uvicorn app.main:app")
        sys.exit(1)

    # Find videos
    videos = find_videos(args.videos_dir)
    if not videos:
        logger.error(f"No videos found in {args.videos_dir}")
        sys.exit(1)

    logger.info(f"Found {len(videos)} videos: {list(videos.keys())}")

    # Initialize detector
    detector = PersonDetector(model_name=args.model, conf_threshold=args.conf)

    # Process each video
    start_time = time.time()
    for camera_id, video_path in videos.items():
        process_video(
            video_path=video_path,
            camera_id=camera_id,
            detector=detector,
            api_url=args.api_url,
            store_id=args.store_id,
        )

    elapsed = time.time() - start_time
    logger.info(f"Pipeline complete in {elapsed:.1f}s")


if __name__ == "__main__":
    main()

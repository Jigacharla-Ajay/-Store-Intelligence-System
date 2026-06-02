"""
WebSocket connection manager.

Manages active WebSocket connections per store, supports:
  - Per-store subscription (clients only get events for their store)
  - Broadcast to all subscribers of a store
  - Graceful disconnect handling
  - Connection heartbeat tracking

Satisfies FR-A07 (real-time event push).
"""

import asyncio
import json
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections grouped by store_id.

    Usage:
        manager = ConnectionManager()

        # In WebSocket route:
        await manager.connect(ws, store_id)
        try:
            while True:
                data = await ws.receive_text()
                # handle pings, filters, etc.
        except WebSocketDisconnect:
            manager.disconnect(ws, store_id)

        # In ingestion service:
        await manager.broadcast(store_id, event_data)
    """

    def __init__(self):
        # {store_id: [WebSocket, ...]}
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        # {id(ws): {"connected_at": ..., "last_ping": ..., "store_id": ...}}
        self._metadata: dict[int, dict] = {}

    async def connect(self, websocket: WebSocket, store_id: str):
        """Accept and register a WebSocket connection for a store."""
        await websocket.accept()
        self._connections[store_id].append(websocket)
        self._metadata[id(websocket)] = {
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "last_ping": time.time(),
            "store_id": store_id,
        }

        # Send welcome message
        await websocket.send_json({
            "type": "CONNECTED",
            "store_id": store_id,
            "message": f"Subscribed to live events for {store_id}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        logger.info(f"WebSocket connected: store={store_id}, total={len(self._connections[store_id])}")

    def disconnect(self, websocket: WebSocket, store_id: str):
        """Remove a WebSocket connection."""
        if websocket in self._connections[store_id]:
            self._connections[store_id].remove(websocket)
        self._metadata.pop(id(websocket), None)

        # Clean up empty store lists
        if not self._connections[store_id]:
            del self._connections[store_id]

        logger.info(f"WebSocket disconnected: store={store_id}")

    async def broadcast(self, store_id: str, data: dict):
        """
        Send data to all WebSocket clients subscribed to a store.
        Silently removes dead connections.
        """
        if store_id not in self._connections:
            return

        dead = []
        message = json.dumps(data)

        for ws in self._connections[store_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        for ws in dead:
            self.disconnect(ws, store_id)

    async def broadcast_events(self, store_id: str, events: list):
        """
        Broadcast a batch of ingested events to subscribers.
        Each event is sent as a separate message with type=EVENT.
        """
        if store_id not in self._connections:
            return

        for event in events:
            await self.broadcast(store_id, {
                "type": "EVENT",
                "data": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    async def broadcast_anomaly(self, store_id: str, anomaly: dict):
        """Broadcast an anomaly alert to store subscribers."""
        await self.broadcast(store_id, {
            "type": "ANOMALY",
            "data": anomaly,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def broadcast_metric_update(self, store_id: str, metrics: dict):
        """Broadcast a metrics snapshot to store subscribers."""
        await self.broadcast(store_id, {
            "type": "METRICS_UPDATE",
            "data": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_connection_count(self, store_id: str = None) -> int:
        """Get number of active connections, optionally filtered by store."""
        if store_id:
            return len(self._connections.get(store_id, []))
        return sum(len(conns) for conns in self._connections.values())

    def get_status(self) -> dict:
        """Get connection manager status for health checks."""
        return {
            "total_connections": self.get_connection_count(),
            "stores": {
                sid: len(conns)
                for sid, conns in self._connections.items()
            },
        }


# Singleton instance — imported by routers and services
ws_manager = ConnectionManager()

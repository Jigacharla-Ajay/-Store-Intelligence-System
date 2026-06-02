"""
WebSocket router for live event and metric pushes.

Clients connect to /ws/stores/{store_id} to receive real-time updates.
Satisfies FR-A07.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import ws_manager

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/stores/{store_id}")
async def websocket_endpoint(websocket: WebSocket, store_id: str):
    """
    WebSocket endpoint for real-time store events and anomalies.
    Clients receive JSON messages with type: CONNECTED, EVENT, ANOMALY, METRICS_UPDATE.
    """
    await ws_manager.connect(websocket, store_id)
    try:
        while True:
            # We don't expect much client->server data, but we must receive
            # to keep the connection alive and handle disconnects.
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, store_id)

"""
VaakSetu v2.0 — WebSocket Connection Manager
Broadcast messages to all connected dashboard clients
"""
import json, logging, asyncio
from typing import List, Dict, Set
from fastapi import WebSocket

logger = logging.getLogger("vaaksetu.ws")


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[str, Set[WebSocket]] = {}
        self.message_buffer: List[Dict] = []  # Last 50 messages for reconnecting clients
        self.max_buffer = 50

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WS connected. Total: {len(self.active_connections)}")
        # Send buffered messages to newly connected client
        for msg in self.message_buffer[-10:]:
            try:
                await websocket.send_json(msg)
            except Exception:
                break

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for channel in self.subscriptions.values():
            channel.discard(websocket)
        logger.info(f"WS disconnected. Total: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, channel: str):
        if channel not in self.subscriptions:
            self.subscriptions[channel] = set()
        self.subscriptions[channel].add(websocket)

    async def broadcast(self, message: Dict):
        """Send message to all connected clients"""
        # Buffer the message
        self.message_buffer.append(message)
        if len(self.message_buffer) > self.max_buffer:
            self.message_buffer = self.message_buffer[-self.max_buffer:]

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def send_to_channel(self, channel: str, message: Dict):
        """Send message to specific channel subscribers"""
        subscribers = self.subscriptions.get(channel, set())
        disconnected = []
        for connection in subscribers:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    async def heartbeat_loop(self):
        """Ping all connected clients every 30s to keep connections alive"""
        while True:
            await asyncio.sleep(30)
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json({"type": "pong", "connections": len(self.active_connections)})
                except Exception:
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn)


"""
WebSocket routes for realtime notifications.
"""
from typing import Dict, List, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core import security
from app.db.session import AsyncSessionLocal
from app.models.user import User

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.user_ids: Dict[WebSocket, Tuple[str, str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, location_id: str) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_ids[websocket] = (user_id, location_id)

    async def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.user_ids.pop(websocket, None)

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    token = websocket.headers.get("Authorization")
    if token is None or not token.startswith("Bearer "):
        await websocket.close(code=1008)
        return

    token = token.split(" ")[1]
    try:
        payload = security.verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008)
            return
        async with AsyncSessionLocal() as db:
            user_result = await db.execute(select(User).where(User.user_id == user_id))
            user = user_result.scalars().first()
            if not user:
                await websocket.close(code=1008)
                return
            await manager.connect(websocket, str(user.user_id), user.location_id)
    except Exception:
        await websocket.close(code=1008)
        return

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message("pong", websocket)
            else:
                await manager.broadcast(data)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)

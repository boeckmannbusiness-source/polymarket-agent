from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.ws.manager import manager

ws_router = APIRouter()


@ws_router.websocket("/ws/portfolio")
async def ws_portfolio(websocket: WebSocket, entity_ids: str | None = Query(default=None)):
    filters = entity_ids.split(",") if entity_ids else None
    await manager.connect(websocket, "portfolio")
    if filters:
        await manager.subscribe(websocket, "portfolio", filters)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "portfolio")
    except Exception:
        await manager.disconnect(websocket, "portfolio")


@ws_router.websocket("/ws/trades")
async def ws_trades(websocket: WebSocket, trade_ids: str | None = Query(default=None)):
    filters = trade_ids.split(",") if trade_ids else None
    await manager.connect(websocket, "trades")
    if filters:
        await manager.subscribe(websocket, "trades", filters)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "trades")
    except Exception:
        await manager.disconnect(websocket, "trades")


@ws_router.websocket("/ws/orders")
async def ws_orders(websocket: WebSocket, order_ids: str | None = Query(default=None)):
    filters = order_ids.split(",") if order_ids else None
    await manager.connect(websocket, "orders")
    if filters:
        await manager.subscribe(websocket, "orders", filters)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "orders")
    except Exception:
        await manager.disconnect(websocket, "orders")


@ws_router.websocket("/ws/fills")
async def ws_fills(websocket: WebSocket, market_ids: str | None = Query(default=None)):
    filters = market_ids.split(",") if market_ids else None
    await manager.connect(websocket, "fills")
    if filters:
        await manager.subscribe(websocket, "fills", filters)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "fills")
    except Exception:
        await manager.disconnect(websocket, "fills")


@ws_router.websocket("/ws/monitoring")
async def ws_monitoring(websocket: WebSocket, strategy: str | None = Query(default=None)):
    filters = [strategy] if strategy else None
    await manager.connect(websocket, "monitoring")
    if filters:
        await manager.subscribe(websocket, "monitoring", filters)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "monitoring")
    except Exception:
        await manager.disconnect(websocket, "monitoring")


@ws_router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await manager.connect(websocket, "alerts")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "alerts")
    except Exception:
        await manager.disconnect(websocket, "alerts")


@ws_router.websocket("/ws/control")
async def ws_control(websocket: WebSocket):
    await manager.connect(websocket, "control")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "control")
    except Exception:
        await manager.disconnect(websocket, "control")

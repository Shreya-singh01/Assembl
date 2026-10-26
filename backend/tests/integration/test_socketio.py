"""Socket.IO against a real in-process uvicorn server."""

import asyncio
import socket

import httpx
import pytest
import socketio
import uvicorn

from tests.integration.conftest import Api, profile

ORIGIN = "http://localhost:5173"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
async def live(app_and_db):
    asgi, db = app_and_db
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(asgi, host="127.0.0.1", port=port, log_level="warning", lifespan="off"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.02)
    base = f"http://127.0.0.1:{port}"
    clients: list = []
    yield base, clients
    for c in clients:
        if isinstance(c, socketio.AsyncClient) and c.connected:
            await c.disconnect()
        elif isinstance(c, httpx.AsyncClient):
            await c.aclose()
    server.should_exit = True
    await task


async def _user(base, clients, name) -> tuple[Api, str]:
    c = httpx.AsyncClient(base_url=base)
    clients.append(c)
    api = await Api(c).register(name)
    return api, c.cookies.get("assembl_session")


async def _socket(base, clients, token: str | None, origin: str = ORIGIN):
    sio = socketio.AsyncClient(reconnection=False)
    clients.append(sio)
    headers = {"Origin": origin}
    if token:
        headers["Cookie"] = f"assembl_session={token}"
    inbox: list = []
    sio.on("message:new", lambda data: inbox.append(data))
    await sio.connect(base, headers=headers, transports=["websocket"], wait_timeout=5)
    return sio, inbox


async def test_unauthenticated_and_foreign_origin_rejected(live):
    base, clients = live
    with pytest.raises(socketio.exceptions.ConnectionError):
        await _socket(base, clients, None)
    _, token = await _user(base, clients, "asha")
    with pytest.raises(socketio.exceptions.ConnectionError):
        await _socket(base, clients, token, origin="https://evil.example")


async def test_realtime_delivery_only_to_participants(live):
    base, clients = live
    a, ta = await _user(base, clients, "asha")
    b, tb = await _user(base, clients, "bilal")
    c, tc = await _user(base, clients, "chen")
    await b.put("/api/v1/profiles/me", profile({"React": 3}))
    conv = (await a.post("/api/v1/conversations", {"user_id": b.user["id"]})).json()

    sa, _ = await _socket(base, clients, ta)
    sb, inbox_b = await _socket(base, clients, tb)
    sc, inbox_c = await _socket(base, clients, tc)

    ack = await sa.call("message:send", {"conversation_id": conv["id"], "body": "hello over sockets",
                                         "client_id": "client-000001"}, timeout=5)
    assert ack["ok"] is True and ack["message"]["body"] == "hello over sockets"
    for _ in range(50):
        if inbox_b:
            break
        await asyncio.sleep(0.05)
    assert [m["body"] for m in inbox_b] == ["hello over sockets"]
    assert inbox_c == []

    # persisted: visible over HTTP
    msgs = (await b.get(f"/api/v1/conversations/{conv['id']}/messages")).json()
    assert [m["body"] for m in msgs] == ["hello over sockets"]

    # non-participant cannot send into the conversation over the socket either
    denied = await sc.call("message:send", {"conversation_id": conv["id"], "body": "intrude"}, timeout=5)
    assert denied == {"ok": False, "error": "Conversation not found"}
    bad = await sa.call("message:send", {"conversation_id": 123}, timeout=5)
    assert bad["ok"] is False

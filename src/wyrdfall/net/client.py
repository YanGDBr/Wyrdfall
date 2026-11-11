"""Low-level websocket connection to a HostServer.

Just moves protocol messages back and forth; :class:`~wyrdfall.net.remote_client.RemoteGameClient`
is what turns this into a :class:`~wyrdfall.net.game_client.GameClient`.
"""

from __future__ import annotations

import asyncio
from typing import Callable

import websockets
import websockets.exceptions

from wyrdfall.net.protocol import ClientHello, ClientMessage, ServerMessage, ServerWelcome, ServerStateUpdate, ServerError, ProtocolError, decode_server_message, encode


class ConnectionError_(ConnectionError):
    pass


class NetworkConnection:
    def __init__(self, uri: str):
        self.uri = uri
        self._ws = None
        self._listen_task: asyncio.Task | None = None
        self._message_handlers: list[Callable[[ServerMessage], None]] = []
        self._disconnect_handlers: list[Callable[[], None]] = []
        self.resume_token = ""
        self.run_id: str | None = None
        self.player_name = "Herói"
        self.connected = False
        self.last_error = ""
        self._closed = False
        self._terminal = False
        self._reconnect_task: asyncio.Task | None = None

    def on_message(self, callback: Callable[[ServerMessage], None]) -> None:
        self._message_handlers.append(callback)

    def off_message(self, callback: Callable[[ServerMessage], None]) -> None:
        if callback in self._message_handlers:
            self._message_handlers.remove(callback)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        self._disconnect_handlers.append(callback)

    def off_disconnect(self, callback: Callable[[], None]) -> None:
        if callback in self._disconnect_handlers:
            self._disconnect_handlers.remove(callback)

    async def connect(self) -> None:
        self._closed = False
        await self._open()

    async def _open(self) -> None:
        self._ws = await websockets.connect(self.uri, open_timeout=10, ping_interval=5, ping_timeout=5)
        self.connected = True
        self._listen_task = asyncio.ensure_future(self._listen())

    async def _listen(self) -> None:
        ws = self._ws
        assert ws is not None
        try:
            async for raw in ws:
                message = decode_server_message(raw)
                if isinstance(message, ServerWelcome):
                    self.resume_token = message.resume_token
                    self.last_error = ""
                elif isinstance(message, ServerStateUpdate):
                    self.run_id = message.run.run_id
                    self._terminal = message.summary is not None
                elif isinstance(message, ServerError) and message.fatal:
                    self.last_error = message.message
                for handler in list(self._message_handlers):
                    handler(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        except ProtocolError:
            await ws.close(code=1002, reason="Mensagem inválida do servidor")
        finally:
            self.connected = False
            for handler in list(self._disconnect_handlers):
                handler()
            if ws.close_code == 1008:
                self._terminal = True  # credentials rejected; do not retry indefinitely
            if not self._closed and not self._terminal and self.resume_token:
                if self._reconnect_task is None or self._reconnect_task.done():
                    self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        while not self._closed and not self._terminal:
            await asyncio.sleep(1.0)
            try:
                await self._open()
                await self.send(ClientHello(player_name=self.player_name,
                    resume_token=self.resume_token, run_id=self.run_id))
                await self._listen_task
            except (OSError, TimeoutError, websockets.exceptions.WebSocketException):
                self.connected = False

    def resume_in_background(self) -> None:
        self._closed = False
        self._terminal = False
        self._reconnect_task = asyncio.create_task(self._reconnect())

    async def send(self, message: ClientMessage) -> None:
        if self._ws is None or not self.connected:
            raise ConnectionError_("Conexão interrompida. Aguarde a reconexão.")
        if isinstance(message, ClientHello):
            self.player_name = message.player_name
        await self._ws.send(encode(message))

    async def close(self) -> None:
        self._closed = True
        retry = self._reconnect_task
        if retry is not None and retry is not asyncio.current_task():
            retry.cancel()
            try:
                await retry
            except asyncio.CancelledError:
                pass
        self._reconnect_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        task = self._listen_task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._listen_task = None

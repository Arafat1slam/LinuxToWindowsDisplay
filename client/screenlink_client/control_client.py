from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Callable, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'common'))
try:
    from screenlink_common.protocol import MessageReader, MessageType
except ImportError:
    # Dummy classes for standalone tests without common
    class MessageReader:
        pass
    class MessageType:
        HELLO = "HELLO"
        HELLO_ACK = "HELLO_ACK"
        START_STREAM = "START_STREAM"
        STOP_STREAM = "STOP_STREAM"
        INPUT_EVENT = "INPUT_EVENT"
        RESOLUTION_CHANGE = "RESOLUTION_CHANGE"
        HEARTBEAT = "HEARTBEAT"
        HEARTBEAT_ACK = "HEARTBEAT_ACK"
        DISCONNECT = "DISCONNECT"

logger = logging.getLogger(__name__)

class ControlClient:
    """
    TCP control channel client (ARCHITECTURE.md §6).
    Handles communication with the ScreenLink server.
    """

    def __init__(
        self, on_disconnected: Callable[[str], None], on_reconnected: Callable[[], None]
    ) -> None:
        self.on_disconnected = on_disconnected
        self.on_reconnected = on_reconnected
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.host: str = ""
        self.port: int = 48321

        self.heartbeat_task: Optional[asyncio.Task] = None
        self.receive_task: Optional[asyncio.Task] = None

        self.missed_heartbeats: int = 0
        self.is_connected: bool = False

        self.reconnect_base_delay: float = 1.0
        self.reconnect_max_attempts: int = 10
        self._reconnecting: bool = False

    async def connect(self, host: str, port: int) -> None:
        """Establishes a TCP connection to the server."""
        self.host = host
        self.port = port
        logger.info("Connecting to %s:%d", host, port)
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
            self.is_connected = True
            self.missed_heartbeats = 0

            self.receive_task = asyncio.create_task(self._receive_loop())
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("Connected to %s:%d", host, port)
        except Exception as e:
            logger.error("Failed to connect: %s", e)
            raise

    async def _send_message(self, msg_type: str, payload: Dict[str, Any]) -> None:
        """Sends a JSON message over the TCP socket."""
        if not self.is_connected or self.writer is None:
            return

        msg = {
            "type": msg_type,
            "payload": payload
        }
        data = json.dumps(msg).encode('utf-8') + b'\n'
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.error("Error sending message: %s", e)
            await self._handle_disconnect("Write error")

    async def send_hello(self, requested_res: str, requested_fps: int) -> Dict[str, Any]:
        """Sends a HELLO message and waits for HELLO_ACK."""
        await self._send_message(MessageType.HELLO, {
            "client_version": "0.1.0",
            "requested_res": requested_res,
            "requested_fps": requested_fps
        })

        # Wait for HELLO_ACK (basic implementation, assumes next msg is ACK)
        if self.reader:
            try:
                line = await self.reader.readline()
                if line:
                    msg = json.loads(line.decode('utf-8'))
                    if msg.get("type") == MessageType.HELLO_ACK:
                        return msg.get("payload", {})
            except Exception as e:
                logger.error("Error receiving HELLO_ACK: %s", e)
        return {}

    async def send_start_stream(self) -> None:
        """Sends a START_STREAM message."""
        await self._send_message(MessageType.START_STREAM, {})

    async def send_stop_stream(self) -> None:
        """Sends a STOP_STREAM message."""
        await self._send_message(MessageType.STOP_STREAM, {})

    async def send_input_event(self, payload: Dict[str, Any]) -> None:
        """Sends an INPUT_EVENT message."""
        await self._send_message(MessageType.INPUT_EVENT, payload)

    async def send_resolution_change(self, width: int, height: int) -> None:
        """Sends a RESOLUTION_CHANGE message."""
        await self._send_message(MessageType.RESOLUTION_CHANGE, {
            "width": width,
            "height": height
        })

    async def send_disconnect(self, reason: str) -> None:
        """Sends a DISCONNECT message and closes connection."""
        await self._send_message(MessageType.DISCONNECT, {"reason": reason})
        await self.disconnect()

    async def disconnect(self) -> None:
        """Closes the connection gracefully."""
        self.is_connected = False
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.receive_task:
            self.receive_task.cancel()

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

        self.writer = None
        self.reader = None
        logger.info("Disconnected from server")

    async def _handle_disconnect(self, reason: str) -> None:
        """Handles unexpected disconnects and triggers reconnect."""
        if not self.is_connected or self._reconnecting:
            return

        logger.warning("Disconnected abruptly: %s", reason)
        await self.disconnect()
        self.on_disconnected(reason)

        # Start reconnect loop (ARCHITECTURE.md §15)
        self._reconnecting = True
        asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Exponential backoff reconnection logic."""
        delay = self.reconnect_base_delay
        for attempt in range(self.reconnect_max_attempts):
            logger.info(
                "Reconnect attempt %d/%d in %.1fs...",
                attempt + 1,
                self.reconnect_max_attempts,
                delay,
            )
            await asyncio.sleep(delay)

            try:
                await self.connect(self.host, self.port)
                self._reconnecting = False
                logger.info("Reconnection successful")
                self.on_reconnected()
                return
            except Exception as e:
                logger.warning("Reconnect attempt failed: %s", e)
                delay = min(delay * 2, 30.0)

        logger.error("Max reconnect attempts reached. Giving up.")
        self._reconnecting = False

    async def _heartbeat_loop(self) -> None:
        """Sends HEARTBEAT every 2s, tracks missed ACKs."""
        try:
            while self.is_connected:
                await asyncio.sleep(2.0)
                self.missed_heartbeats += 1

                if self.missed_heartbeats >= 3:
                    logger.error("Missed 3 heartbeats, assuming disconnected")
                    await self._handle_disconnect("Heartbeat timeout")
                    break

                await self._send_message(MessageType.HEARTBEAT, {"ts": time.time()})
        except asyncio.CancelledError:
            pass

    async def _receive_loop(self) -> None:
        """Continuously reads messages from the stream."""
        if not self.reader:
            return

        try:
            while self.is_connected:
                line = await self.reader.readline()
                if not line:
                    await self._handle_disconnect("Connection closed by peer")
                    break

                try:
                    msg = json.loads(line.decode('utf-8'))
                    msg_type = msg.get("type")

                    if msg_type == MessageType.HEARTBEAT_ACK:
                        self.missed_heartbeats = 0
                    elif msg_type == MessageType.HEARTBEAT:
                        await self._send_message(MessageType.HEARTBEAT_ACK, {"ts": time.time()})
                    elif msg_type == MessageType.DISCONNECT:
                        reason = msg.get("payload", {}).get("reason", "Unknown")
                        await self._handle_disconnect(f"Server disconnected: {reason}")
                        break

                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Error in receive loop: %s", e)
            await self._handle_disconnect(str(e))

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

# Ensure we can import from common
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'common'))
try:
    from screenlink_common.protocol import Message, MessageType
except ImportError:
    # Dummy classes if common is not found in standalone run
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
    class Message:
        pass

from .capture_pipeline import CapturePipeline
from .display_manager import DisplayManager
from .input_injector import InputInjector

logger = logging.getLogger(__name__)

class ControlServer:
    """
    TCP control channel server.
    See ARCHITECTURE.md §6.
    """
    def __init__(
        self,
        host: str,
        port: int,
        display_manager: DisplayManager,
        capture_pipeline: CapturePipeline,
    ):
        self.host = host
        self.port = port
        self.display_manager = display_manager
        self.capture_pipeline = capture_pipeline
        self.input_injector: Optional[InputInjector] = None
        self.server: Optional[asyncio.AbstractServer] = None
        self.active_writer: Optional[asyncio.StreamWriter] = None
        self.missed_heartbeats = 0
        self.heartbeat_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Starts the TCP control server."""
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logger.info(f"Control server listening on {self.host}:{self.port}")

    async def stop(self) -> None:
        """Stops the control server and tears down resources."""
        if self.active_writer:
            try:
                msg = {"type": MessageType.DISCONNECT, "payload": {"reason": "server_shutdown"}}
                self.active_writer.write((json.dumps(msg) + "\n").encode())
                await self.active_writer.drain()
                self.active_writer.close()
                await self.active_writer.wait_closed()
            except Exception:
                pass
            self.active_writer = None

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        self._teardown_session()
        logger.info("Control server stopped.")

    def _teardown_session(self) -> None:
        """Tears down an active session."""
        self.capture_pipeline.stop()
        self.display_manager.remove_virtual_display()
        if self.input_injector:
            self.input_injector.teardown()
            self.input_injector = None
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        self.missed_heartbeats = 0

    async def _heartbeat_loop(self) -> None:
        """Monitors heartbeats and disconnects if too many are missed."""
        while True:
            await asyncio.sleep(2)
            self.missed_heartbeats += 1
            if self.missed_heartbeats >= 3:
                logger.error("Too many missed heartbeats. Dropping connection.")
                if self.active_writer:
                    self.active_writer.close()
                    await self.active_writer.wait_closed()
                self._teardown_session()
                break

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handles an incoming client connection."""
        addr = writer.get_extra_info("peername")
        logger.info(f"New connection from {addr}")

        if self.active_writer:
            logger.warning(f"Rejecting concurrent connection from {addr}")
            msg = {"type": MessageType.DISCONNECT, "payload": {"reason": "already_connected"}}
            writer.write((json.dumps(msg) + "\n").encode())
            await writer.drain()
            writer.close()
            return

        self.active_writer = writer
        self.missed_heartbeats = 0
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        client_ip = addr[0]

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    msg = json.loads(data.decode().strip())
                    await self._process_message(msg, writer, client_ip)
                except json.JSONDecodeError:
                    logger.error("Received invalid JSON")
        except ConnectionResetError:
            logger.warning("Connection reset by peer.")
        except Exception as e:
            logger.error(f"Error in client handler: {e}")
        finally:
            logger.info(f"Connection from {addr} closed.")
            if self.active_writer == writer:
                self.active_writer = None
                self._teardown_session()

    async def _process_message(
        self, msg: Dict[str, Any], writer: asyncio.StreamWriter, client_ip: str
    ) -> None:
        """Processes a single parsed message."""
        msg_type = msg.get("type")
        payload = msg.get("payload", {})

        if msg_type == MessageType.HELLO:
            res = payload.get("requested_res", "1920x1080")
            fps = payload.get("requested_fps", 60)
            width, height = map(int, res.split("x"))

            self.display_manager.create_virtual_display(width, height)
            self.input_injector = InputInjector(width, height)
            self.input_injector.setup()

            udp_port = 49152 # Ideally dynamically assigned from config range
            ack_msg = {
                "type": MessageType.HELLO_ACK,
                "payload": {
                    "server_version": "0.1.0",
                    "udp_video_port": udp_port,
                    "session_id": "session-123",
                    "granted_res": f"{width}x{height}",
                    "granted_fps": fps
                }
            }
            writer.write((json.dumps(ack_msg) + "\n").encode())
            await writer.drain()

        elif msg_type == MessageType.START_STREAM:
            geom = self.display_manager.get_geometry()
            # Hardcoded UDP port and settings for now, should store from HELLO
            self.capture_pipeline.start(client_ip, 49152, geom, 60, 8000)

        elif msg_type == MessageType.STOP_STREAM:
            self.capture_pipeline.stop()

        elif msg_type == MessageType.INPUT_EVENT:
            if self.input_injector:
                self.input_injector.handle_input_event(payload)

        elif msg_type == MessageType.RESOLUTION_CHANGE:
            width = payload.get("width")
            height = payload.get("height")
            if width and height:
                self.display_manager.create_virtual_display(width, height)

        elif msg_type == MessageType.HEARTBEAT:
            self.missed_heartbeats = 0
            ack = {"type": MessageType.HEARTBEAT_ACK, "payload": {"ts": payload.get("ts")}}
            writer.write((json.dumps(ack) + "\n").encode())
            await writer.drain()

        elif msg_type == MessageType.DISCONNECT:
            logger.info(f"Client disconnected gracefully: {payload.get('reason')}")
            writer.close()

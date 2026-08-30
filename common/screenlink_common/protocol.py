"""Shared message schema and (de)serialization for the ScreenLink control channel.

This module is the **single source of truth** for every message type that travels
over the TCP control channel between server and client.  Both sides import from
here — never duplicate these definitions.

Wire format (ARCHITECTURE.md §6):
    Newline-delimited JSON.  Each message is a single JSON object followed by
    ``\\n``.  The envelope is::

        {"type": "<MESSAGE_TYPE>", "seq": <int>, "payload": { ... }}

Message types and payload shapes are documented inline below and correspond
1-to-1 with the table in ARCHITECTURE.md §6.

Input-event payload shapes follow ARCHITECTURE.md §8.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 1
DEFAULT_CONTROL_PORT = 48321
DEFAULT_VIDEO_PORT_RANGE = (49152, 49200)
HEARTBEAT_INTERVAL_S = 2.0
HEARTBEAT_MISS_LIMIT = 3
MDNS_SERVICE_TYPE = "_screenlink._tcp.local."


class MessageType(str, Enum):
    """Every valid ``type`` value in a control-channel message envelope.

    Maps 1-to-1 with the table in ARCHITECTURE.md §6.
    """

    HELLO = "HELLO"
    HELLO_ACK = "HELLO_ACK"
    START_STREAM = "START_STREAM"
    STOP_STREAM = "STOP_STREAM"
    INPUT_EVENT = "INPUT_EVENT"
    RESOLUTION_CHANGE = "RESOLUTION_CHANGE"
    HEARTBEAT = "HEARTBEAT"
    HEARTBEAT_ACK = "HEARTBEAT_ACK"
    DISCONNECT = "DISCONNECT"


class InputEventKind(str, Enum):
    """Discriminator for the ``kind`` field inside an ``INPUT_EVENT`` payload.

    Defined in ARCHITECTURE.md §8.
    """

    MOUSE_MOVE = "mouse_move"
    MOUSE_BUTTON = "mouse_button"
    SCROLL = "scroll"
    KEY = "key"


# ---------------------------------------------------------------------------
# Payload dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HelloPayload:
    """``HELLO`` payload — sent C→S to open a session (ARCHITECTURE.md §6).

    Attributes:
        client_version: Protocol version the client speaks.
        requested_res: Desired resolution string, e.g. ``"1920x1080"``.
        requested_fps: Desired framerate.
    """

    client_version: int
    requested_res: str
    requested_fps: int


@dataclass(frozen=True)
class HelloAckPayload:
    """``HELLO_ACK`` payload — sent S→C to confirm session params (ARCHITECTURE.md §6).

    Attributes:
        server_version: Protocol version the server speaks.
        udp_video_port: UDP port the server will stream video from.
        session_id: Unique session identifier.
        granted_res: Actual resolution granted (may differ from requested).
        granted_fps: Actual framerate granted.
    """

    server_version: int
    udp_video_port: int
    session_id: str
    granted_res: str
    granted_fps: int


@dataclass(frozen=True)
class ResolutionChangePayload:
    """``RESOLUTION_CHANGE`` payload — sent C→S (ARCHITECTURE.md §6).

    Attributes:
        width: Requested new width in pixels.
        height: Requested new height in pixels.
    """

    width: int
    height: int


@dataclass(frozen=True)
class HeartbeatPayload:
    """``HEARTBEAT`` / ``HEARTBEAT_ACK`` payload (ARCHITECTURE.md §6).

    Attributes:
        ts: Timestamp (seconds since epoch) for round-trip-time measurement.
    """

    ts: float = field(default_factory=time.time)


@dataclass(frozen=True)
class DisconnectPayload:
    """``DISCONNECT`` payload (ARCHITECTURE.md §6).

    Attributes:
        reason: Human-readable disconnect reason.
    """

    reason: str


# Input-event sub-payloads (ARCHITECTURE.md §8) --------------------------


@dataclass(frozen=True)
class MouseMovePayload:
    """Absolute mouse-move event with normalised 0.0–1.0 coordinates.

    Resolution-independent so the protocol survives live resolution changes
    (ARCHITECTURE.md §8).
    """

    kind: str = field(default="mouse_move", init=False)
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True)
class MouseButtonPayload:
    """Mouse button press/release event (ARCHITECTURE.md §8).

    Attributes:
        button: One of ``"left"``, ``"right"``, ``"middle"``.
        action: ``"down"`` or ``"up"``.
    """

    kind: str = field(default="mouse_button", init=False)
    button: str = "left"
    action: str = "down"


@dataclass(frozen=True)
class ScrollPayload:
    """Scroll-wheel event (ARCHITECTURE.md §8).

    Attributes:
        delta_x: Horizontal scroll amount.
        delta_y: Vertical scroll amount (negative = scroll down).
    """

    kind: str = field(default="scroll", init=False)
    delta_x: int = 0
    delta_y: int = 0


@dataclass(frozen=True)
class KeyPayload:
    """Keyboard key press/release event (ARCHITECTURE.md §8).

    Attributes:
        code: evdev key-code name, e.g. ``"KEY_LEFTSHIFT"``.
        action: ``"down"`` or ``"up"``.
    """

    kind: str = field(default="key", init=False)
    code: str = "KEY_A"
    action: str = "down"


# Union-style alias for type annotations.
InputPayload = Union[MouseMovePayload, MouseButtonPayload, ScrollPayload, KeyPayload]

# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

_SEQ_COUNTER: int = 0


def _next_seq() -> int:
    """Return a monotonically increasing sequence number for this process."""
    global _SEQ_COUNTER  # noqa: PLW0603
    _SEQ_COUNTER += 1
    return _SEQ_COUNTER


def reset_seq() -> None:
    """Reset the global sequence counter (useful in tests)."""
    global _SEQ_COUNTER  # noqa: PLW0603
    _SEQ_COUNTER = 0


@dataclass()
class Message:
    """A single control-channel message envelope (ARCHITECTURE.md §6).

    Attributes:
        type: The ``MessageType`` discriminator.
        seq: Monotonic sequence number (auto-assigned on creation if omitted).
        payload: Type-specific payload dict or dataclass instance.
    """

    type: MessageType
    payload: Union[dict[str, Any], Any] = field(default_factory=dict)
    seq: int = field(default_factory=_next_seq)


# ---------------------------------------------------------------------------
# Serialization / Deserialization
# ---------------------------------------------------------------------------


def serialize(msg: Message) -> bytes:
    """Encode a ``Message`` to its wire representation (UTF-8 JSON + newline).

    Follows the newline-delimited JSON framing specified in ARCHITECTURE.md §6.
    Dataclass payloads are automatically converted to plain dicts.

    Returns:
        Raw bytes ready to write to the TCP socket.
    """
    payload = msg.payload
    if hasattr(payload, "__dataclass_fields__"):
        payload = asdict(payload)
    elif not isinstance(payload, dict):
        raise TypeError(f"payload must be a dict or dataclass, got {type(payload).__name__}")

    envelope: dict[str, Any] = {
        "type": msg.type.value if isinstance(msg.type, MessageType) else str(msg.type),
        "seq": msg.seq,
        "payload": payload,
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8") + b"\n"


def deserialize(data: Union[bytes, str]) -> Message:
    """Parse raw wire bytes into a ``Message``.

    Raises:
        ValueError: If the data is not valid JSON, is missing required envelope
            fields, or contains an unknown message type.
        json.JSONDecodeError: If the data is not valid JSON at all.
    """
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    text = text.strip()
    if not text:
        raise ValueError("Empty message")

    obj = json.loads(text)

    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object, got {type(obj).__name__}")

    for required in ("type", "seq", "payload"):
        if required not in obj:
            raise ValueError(f"Missing required field: {required!r}")

    try:
        msg_type = MessageType(obj["type"])
    except ValueError:
        raise ValueError(f"Unknown message type: {obj['type']!r}") from None

    seq = obj["seq"]
    if not isinstance(seq, int):
        raise ValueError(f"'seq' must be an integer, got {type(seq).__name__}")

    payload = obj["payload"]
    if not isinstance(payload, dict):
        raise ValueError(f"'payload' must be an object, got {type(payload).__name__}")

    return Message(type=msg_type, payload=payload, seq=seq)


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------


def make_hello(requested_res: str = "1920x1080", requested_fps: int = 60) -> Message:
    """Build a ``HELLO`` message (C→S) per ARCHITECTURE.md §6."""
    return Message(
        type=MessageType.HELLO,
        payload=HelloPayload(
            client_version=PROTOCOL_VERSION,
            requested_res=requested_res,
            requested_fps=requested_fps,
        ),
    )


def make_hello_ack(
    udp_video_port: int,
    session_id: str,
    granted_res: str = "1920x1080",
    granted_fps: int = 60,
) -> Message:
    """Build a ``HELLO_ACK`` message (S→C) per ARCHITECTURE.md §6."""
    return Message(
        type=MessageType.HELLO_ACK,
        payload=HelloAckPayload(
            server_version=PROTOCOL_VERSION,
            udp_video_port=udp_video_port,
            session_id=session_id,
            granted_res=granted_res,
            granted_fps=granted_fps,
        ),
    )


def make_start_stream() -> Message:
    """Build a ``START_STREAM`` message (C→S) per ARCHITECTURE.md §6."""
    return Message(type=MessageType.START_STREAM, payload={})


def make_stop_stream() -> Message:
    """Build a ``STOP_STREAM`` message (C→S) per ARCHITECTURE.md §6."""
    return Message(type=MessageType.STOP_STREAM, payload={})


def make_heartbeat() -> Message:
    """Build a ``HEARTBEAT`` message per ARCHITECTURE.md §6."""
    return Message(type=MessageType.HEARTBEAT, payload=HeartbeatPayload())


def make_heartbeat_ack(ts: Union[float, None] = None) -> Message:
    """Build a ``HEARTBEAT_ACK`` message per ARCHITECTURE.md §6."""
    return Message(
        type=MessageType.HEARTBEAT_ACK,
        payload=HeartbeatPayload(ts=ts if ts is not None else time.time()),
    )


def make_disconnect(reason: str = "user requested") -> Message:
    """Build a ``DISCONNECT`` message per ARCHITECTURE.md §6."""
    return Message(type=MessageType.DISCONNECT, payload=DisconnectPayload(reason=reason))


def make_resolution_change(width: int, height: int) -> Message:
    """Build a ``RESOLUTION_CHANGE`` message (C→S) per ARCHITECTURE.md §6."""
    return Message(
        type=MessageType.RESOLUTION_CHANGE,
        payload=ResolutionChangePayload(width=width, height=height),
    )


def make_input_event(input_payload: InputPayload) -> Message:
    """Build an ``INPUT_EVENT`` message wrapping a specific input sub-payload.

    The ``input_payload`` should be one of ``MouseMovePayload``,
    ``MouseButtonPayload``, ``ScrollPayload``, or ``KeyPayload`` — matching
    ARCHITECTURE.md §8 exactly.
    """
    return Message(type=MessageType.INPUT_EVENT, payload=input_payload)


# ---------------------------------------------------------------------------
# Stream reader helper
# ---------------------------------------------------------------------------


class MessageReader:
    """Incrementally reads newline-delimited JSON messages from a byte stream.

    Because TCP is a stream protocol, a single ``recv()`` may contain zero,
    one, or multiple complete messages.  This class buffers partial reads and
    yields complete ``Message`` objects as they become available.
    """

    def __init__(self) -> None:
        self._buffer: bytes = b""

    def feed(self, data: bytes) -> list[Message]:
        """Feed raw bytes from the socket and return any complete messages.

        Malformed lines are logged and skipped rather than crashing the
        connection — the protocol is designed to be resilient to transient
        corruption on the control channel.
        """
        self._buffer += data
        messages: list[Message] = []
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                messages.append(deserialize(line))
            except (ValueError, json.JSONDecodeError) as exc:
                logger.warning("Skipping malformed message: %s — %s", line[:200], exc)
        return messages

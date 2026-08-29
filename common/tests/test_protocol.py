from __future__ import annotations

import json

import pytest
from screenlink_common.protocol import (
    DEFAULT_CONTROL_PORT,
    MDNS_SERVICE_TYPE,
    PROTOCOL_VERSION,
    KeyPayload,
    MessageReader,
    MessageType,
    MouseButtonPayload,
    MouseMovePayload,
    ScrollPayload,
    deserialize,
    make_disconnect,
    make_heartbeat,
    make_heartbeat_ack,
    make_hello,
    make_hello_ack,
    make_input_event,
    make_resolution_change,
    make_start_stream,
    make_stop_stream,
    serialize,
)


def test_hello_roundtrip():
    """Test round-trip serialization for HELLO message."""
    msg = make_hello("1920x1080", 60)
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.HELLO
    assert decoded.payload["client_version"] == PROTOCOL_VERSION
    assert decoded.payload["requested_res"] == "1920x1080"


def test_hello_ack_roundtrip():
    """Test round-trip serialization for HELLO_ACK message."""
    msg = make_hello_ack(udp_video_port=5000, session_id="test_session")
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.HELLO_ACK
    assert decoded.payload["udp_video_port"] == 5000
    assert decoded.payload["session_id"] == "test_session"


def test_start_stream_roundtrip():
    """Test round-trip serialization for START_STREAM message."""
    msg = make_start_stream()
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.START_STREAM
    assert decoded.payload == {}


def test_stop_stream_roundtrip():
    """Test round-trip serialization for STOP_STREAM message."""
    msg = make_stop_stream()
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.STOP_STREAM
    assert decoded.payload == {}


def test_input_event_mouse_move_roundtrip():
    """Test round-trip serialization for INPUT_EVENT (mouse_move) message."""
    msg = make_input_event(MouseMovePayload(x=0.5, y=0.25))
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.INPUT_EVENT
    assert decoded.payload["kind"] == "mouse_move"
    assert decoded.payload["x"] == 0.5
    assert decoded.payload["y"] == 0.25


def test_input_event_mouse_button_roundtrip():
    """Test round-trip serialization for INPUT_EVENT (mouse_button) message."""
    msg = make_input_event(MouseButtonPayload(button="right", action="up"))
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.INPUT_EVENT
    assert decoded.payload["kind"] == "mouse_button"
    assert decoded.payload["button"] == "right"
    assert decoded.payload["action"] == "up"


def test_input_event_scroll_roundtrip():
    """Test round-trip serialization for INPUT_EVENT (scroll) message."""
    msg = make_input_event(ScrollPayload(delta_x=0, delta_y=-1))
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.INPUT_EVENT
    assert decoded.payload["kind"] == "scroll"
    assert decoded.payload["delta_y"] == -1


def test_input_event_key_roundtrip():
    """Test round-trip serialization for INPUT_EVENT (key) message."""
    msg = make_input_event(KeyPayload(code="KEY_B", action="up"))
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.INPUT_EVENT
    assert decoded.payload["kind"] == "key"
    assert decoded.payload["code"] == "KEY_B"
    assert decoded.payload["action"] == "up"


def test_resolution_change_roundtrip():
    """Test round-trip serialization for RESOLUTION_CHANGE message."""
    msg = make_resolution_change(800, 600)
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.RESOLUTION_CHANGE
    assert decoded.payload["width"] == 800
    assert decoded.payload["height"] == 600


def test_heartbeat_roundtrip():
    """Test round-trip serialization for HEARTBEAT message."""
    msg = make_heartbeat()
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.HEARTBEAT
    assert "ts" in decoded.payload


def test_heartbeat_ack_roundtrip():
    """Test round-trip serialization for HEARTBEAT_ACK message."""
    msg = make_heartbeat_ack(ts=123.45)
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.HEARTBEAT_ACK
    assert decoded.payload["ts"] == 123.45


def test_disconnect_roundtrip():
    """Test round-trip serialization for DISCONNECT message."""
    msg = make_disconnect(reason="timeout")
    data = serialize(msg)
    decoded = deserialize(data)
    assert decoded.type == MessageType.DISCONNECT
    assert decoded.payload["reason"] == "timeout"


def test_empty_message_raises():
    """Test that empty string raises ValueError on deserialize."""
    with pytest.raises(ValueError, match="Empty message"):
        deserialize(b"")


def test_missing_type_raises():
    """Test that missing type raises ValueError."""
    data = json.dumps({"seq": 1, "payload": {}}).encode("utf-8")
    with pytest.raises(ValueError, match="Missing required field: 'type'"):
        deserialize(data)


def test_missing_seq_raises():
    """Test that missing seq raises ValueError."""
    data = json.dumps({"type": "HELLO", "payload": {}}).encode("utf-8")
    with pytest.raises(ValueError, match="Missing required field: 'seq'"):
        deserialize(data)


def test_missing_payload_raises():
    """Test that missing payload raises ValueError."""
    data = json.dumps({"type": "HELLO", "seq": 1}).encode("utf-8")
    with pytest.raises(ValueError, match="Missing required field: 'payload'"):
        deserialize(data)


def test_unknown_type_raises():
    """Test that unknown type raises ValueError."""
    data = json.dumps({"type": "BOGUS", "seq": 1, "payload": {}}).encode("utf-8")
    with pytest.raises(ValueError, match="Unknown message type"):
        deserialize(data)


def test_invalid_json_raises():
    """Test that invalid json raises JSONDecodeError."""
    with pytest.raises(json.JSONDecodeError):
        deserialize(b"{bogus-json")


def test_non_dict_payload_raises():
    """Test that a non-dict payload raises ValueError."""
    data = json.dumps({"type": "HELLO", "seq": 1, "payload": 123}).encode("utf-8")
    with pytest.raises(ValueError, match="'payload' must be an object"):
        deserialize(data)


def test_non_integer_seq_raises():
    """Test that a non-integer seq raises ValueError."""
    data = json.dumps({"type": "HELLO", "seq": "1", "payload": {}}).encode("utf-8")
    with pytest.raises(ValueError, match="'seq' must be an integer"):
        deserialize(data)


def test_reader_single_message():
    """Test MessageReader correctly parses a single message."""
    reader = MessageReader()
    msg = make_hello()
    data = serialize(msg)
    msgs = reader.feed(data)
    assert len(msgs) == 1
    assert msgs[0].type == MessageType.HELLO


def test_reader_multiple_messages():
    """Test MessageReader correctly parses multiple messages."""
    reader = MessageReader()
    msg1 = make_hello()
    msg2 = make_start_stream()
    data = serialize(msg1) + serialize(msg2)
    msgs = reader.feed(data)
    assert len(msgs) == 2
    assert msgs[0].type == MessageType.HELLO
    assert msgs[1].type == MessageType.START_STREAM


def test_reader_partial_message():
    """Test MessageReader can buffer partial messages."""
    reader = MessageReader()
    msg = make_hello()
    data = serialize(msg)
    msgs = reader.feed(data[:10])
    assert len(msgs) == 0
    msgs = reader.feed(data[10:])
    assert len(msgs) == 1
    assert msgs[0].type == MessageType.HELLO


def test_reader_malformed_skipped():
    """Test MessageReader gracefully handles and skips malformed messages."""
    reader = MessageReader()
    msg = make_hello()
    data = b"bogus_line\n" + serialize(msg)
    msgs = reader.feed(data)
    assert len(msgs) == 1
    assert msgs[0].type == MessageType.HELLO


def test_make_hello():
    """Test make_hello convenience builder."""
    msg = make_hello("800x600", 30)
    assert msg.type == MessageType.HELLO
    assert msg.payload.requested_res == "800x600"
    assert msg.payload.requested_fps == 30


def test_make_hello_ack():
    """Test make_hello_ack convenience builder."""
    msg = make_hello_ack(1234, "abc", "1024x768", 60)
    assert msg.type == MessageType.HELLO_ACK
    assert msg.payload.udp_video_port == 1234
    assert msg.payload.session_id == "abc"


def test_make_input_event():
    """Test make_input_event convenience builder."""
    msg = make_input_event(KeyPayload(code="KEY_ESC", action="down"))
    assert msg.type == MessageType.INPUT_EVENT
    assert msg.payload.kind == "key"
    assert msg.payload.code == "KEY_ESC"


def test_protocol_version():
    """Test protocol version constant is correct."""
    assert PROTOCOL_VERSION == 1


def test_default_port():
    """Test default port constant is correct."""
    assert DEFAULT_CONTROL_PORT == 48321


def test_mdns_service_type():
    """Test mdns service type constant is correct."""
    assert MDNS_SERVICE_TYPE == "_screenlink._tcp.local."

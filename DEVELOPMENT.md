# Development Guide

This document takes you from a clean machine to a working development build, then walks through implementing ScreenLink in order. Read [ARCHITECTURE.md](ARCHITECTURE.md) first — this guide assumes familiarity with the components and protocols it defines.

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Environment Setup — Linux (Server)](#2-environment-setup--linux-server)
3. [Environment Setup — Windows (Client)](#3-environment-setup--windows-client)
4. [Repository Structure](#4-repository-structure)
5. [Dependency Definitions](#5-dependency-definitions)
6. [Step-by-Step Implementation Guide](#6-step-by-step-implementation-guide)
7. [Testing Strategy](#7-testing-strategy)
8. [Debugging Tips](#8-debugging-tips)
9. [Packaging & Release](#9-packaging--release)

---

## 1. Prerequisites

Because this is a two-sided client/server project, you ideally want:
- A Linux machine (X11 session — see [ARCHITECTURE.md §9](ARCHITECTURE.md#9-virtual-display-creation-on-linux)) to run the server.
- A Windows machine or VM to run the client. A VM works for protocol/logic development but **cannot** validate real hardware video decode or actual Wi-Fi latency — budget time on real hardware before release testing.
- Both machines on the same LAN/Wi-Fi network, or a virtual network between VMs with realistic latency simulation (see §7).

## 2. Environment Setup — Linux (Server)

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-vaapi \
  gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 python3-gi \
  x11-xserver-utils xserver-xorg-video-dummy

git clone https://github.com/<your-username>/screenlink.git
cd screenlink/server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**One-time `uinput` permission setup** (required for input injection, see [ARCHITECTURE.md §12](ARCHITECTURE.md#12-input-capture--injection)):
```bash
sudo tee /etc/udev/rules.d/99-screenlink-uinput.rules > /dev/null <<'EOF'
KERNEL=="uinput", MODE="0660", GROUP="input"
EOF
sudo usermod -aG input $USER
sudo udevadm control --reload-rules
# log out and back in for the group change to take effect
```

**Sanity check GStreamer + VAAPI (or your GPU's equivalent) is working:**
```bash
gst-inspect-1.0 vaapih264enc   # or nvh264enc / qsvh264enc depending on your GPU
```
If none are present, the server will fall back to `x264enc` automatically (see [ARCHITECTURE.md §10](ARCHITECTURE.md#10-screen-capture--encode-pipeline-server)) — development can continue, just expect higher CPU use and latency.

## 3. Environment Setup — Windows (Client)

1. Install [Python 3.11+](https://www.python.org/downloads/windows/) (check "Add to PATH").
2. Install the [GStreamer Windows runtime](https://gstreamer.freedesktop.org/download/) — pick the **MSVC 64-bit, full** installer (not "base"), so the RTP and H.264 plugins are included.
3. Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/) (C++ build tools workload) — required by some PyQt6/GObject wheel builds.
4. Clone and set up:
```powershell
git clone https://github.com/<your-username>/screenlink.git
cd screenlink\client
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
5. Confirm GStreamer is on `PATH`:
```powershell
gst-inspect-1.0.exe d3d11h264dec
```

## 4. Repository Structure

```
screenlink/
├── server/
│   ├── screenlink_server/
│   │   ├── __init__.py
│   │   ├── display_manager.py     # xrandr virtual output creation/teardown
│   │   ├── capture_pipeline.py    # GStreamer capture+encode pipeline
│   │   ├── control_server.py      # TCP control channel, protocol handling
│   │   ├── input_injector.py      # uinput virtual device
│   │   ├── discovery.py           # mDNS advertisement
│   │   └── __main__.py
│   ├── requirements.txt
│   └── tests/
├── client/
│   ├── screenlink_client/
│   │   ├── __init__.py
│   │   ├── discovery.py           # mDNS browsing
│   │   ├── control_client.py      # TCP control channel
│   │   ├── render_pipeline.py     # GStreamer decode+render pipeline
│   │   ├── input_hooks.py         # global mouse/keyboard hooks
│   │   ├── ui/                    # PyQt6 windows (device list, settings, tray)
│   │   └── __main__.py
│   ├── requirements.txt
│   └── tests/
├── common/
│   └── screenlink_common/
│       └── protocol.py            # shared message schema + (de)serialization
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   └── CONTRIBUTING.md
├── LICENSE.md
└── pyproject.toml
```

`common/` exists so both `server` and `client` import the **same** protocol message definitions — this is a deliberate structural decision to prevent the two sides' JSON schemas from silently drifting apart as the project grows.

## 5. Dependency Definitions

**`server/requirements.txt`**
```
PyGObject>=3.46
zeroconf>=0.132
python-uinput>=1.0.0
```
*(GStreamer itself is a system package, not a pip package — installed in §2.)*

**`client/requirements.txt`**
```
PyGObject>=3.46
PyQt6>=6.6
zeroconf>=0.132
pynput>=1.7
```

**`pyproject.toml` (root, dev tooling)**
```toml
[tool.black]
line-length = 100

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
testpaths = ["server/tests", "client/tests", "common/tests"]
```

## 6. Step-by-Step Implementation Guide

Each step names its acceptance criteria — treat these as the definition of "done" for that step's PR. Cross-references point to the relevant ARCHITECTURE.md section.

### Step 1 — Project skeleton & shared protocol module
Set up the repo structure from §4 and implement `common/screenlink_common/protocol.py`: message envelope serialization/deserialization and constants for every message `type` in [ARCHITECTURE.md §6](ARCHITECTURE.md#6-control-channel-protocol-spec).
**Done when:** unit tests can construct, serialize, and parse every message type round-trip.

### Step 2 — Discovery
Implement `discovery.py` on both sides using `zeroconf`: server advertises `_screenlink._tcp.local.` with the TXT record from [ARCHITECTURE.md §4](ARCHITECTURE.md#4-discovery-protocol); client browses and lists found servers.
**Done when:** running both on the same LAN, the client prints discovered server names within a few seconds.

### Step 3 — Control channel handshake
Implement `control_server.py` / `control_client.py`: TCP connect, `HELLO`/`HELLO_ACK` exchange, heartbeat loop.
**Done when:** client connects to a real server instance and the heartbeat keeps the connection alive for several minutes without drift.

### Step 4 — Virtual display creation (Linux)
Implement `display_manager.py` per [ARCHITECTURE.md §9](ARCHITECTURE.md#9-virtual-display-creation-on-linux): create a virtual output at a requested resolution on `HELLO`, tear it down on disconnect.
**Done when:** `xrandr` shows the new virtual output appearing and disappearing as sessions connect/disconnect, and it's usable as a real desktop extension in the interim.

### Step 5 — Screen capture + encode pipeline
Implement `capture_pipeline.py`: build the GStreamer pipeline from [ARCHITECTURE.md §10](ARCHITECTURE.md#10-screen-capture--encode-pipeline-server), with runtime capability probing to pick hardware vs. software encoder.
**Done when:** you can point `udpsink` at your own machine's loopback and view the stream with `gst-launch` as a standalone sanity check, decoupled from the client.

### Step 6 — RTP/UDP video transmission wiring
Wire `capture_pipeline.py`'s output port to the port negotiated in the `HELLO_ACK` (§6), start on `START_STREAM`, stop on `STOP_STREAM`/disconnect.
**Done when:** the pipeline only runs while a client session is active — verify CPU/GPU usage drops to idle after disconnect.

### Step 7 — Client receive/decode/render pipeline
Implement `render_pipeline.py` per [ARCHITECTURE.md §11](ARCHITECTURE.md#11-decode--render-pipeline-client); render into a borderless full-screen PyQt6 window.
**Done when:** end-to-end video is visible on the Windows client from a real Linux server on the same Wi-Fi network.

### Step 8 — Client input capture
Implement `input_hooks.py` using global low-level hooks; translate raw events into `INPUT_EVENT` messages per [ARCHITECTURE.md §8](ARCHITECTURE.md#8-input-event-protocol) and send over the control channel.
**Done when:** moving the mouse on the client prints correctly normalized coordinates on the server's console.

### Step 9 — Server input injection
Implement `input_injector.py` using `uinput`, consuming `INPUT_EVENT` messages.
**Done when:** moving the mouse/typing on the Windows client visibly moves the cursor and types on the Linux virtual display.

### Step 10 — Reconnection & error handling
Implement the failure-mode table from [ARCHITECTURE.md §15](ARCHITECTURE.md#15-failure-modes--reconnection): heartbeat timeout detection, exponential-backoff reconnect loop, graceful pipeline teardown.
**Done when:** killing Wi-Fi on the client mid-session and restoring it later results in an automatic reconnect without restarting either app.

### Step 11 — Settings & quality controls
Expose resolution/framerate/bitrate and jitter-buffer latency (§13) as a PyQt6 settings panel on the client, sent via `RESOLUTION_CHANGE`/renegotiation.
**Done when:** changing quality settings live updates the stream without a full reconnect.

### Step 12 — Packaging
PyInstaller specs for both apps (see §9 below); tray icon for the client so it can run in the background.

## 7. Testing Strategy

- **Unit tests** (`pytest`) for `common/screenlink_common/protocol.py` — every message type, plus malformed/partial JSON handling.
- **Component tests** for `display_manager.py` against a real (or Xvfb-based headless) X server.
- **Manual integration checklist** (run before every release): discovery, connect, video quality at each resolution preset, input latency feel-test, disconnect/reconnect, lid-close/wake.
- **Network condition simulation:** use `tc`/`netem` on Linux to inject artificial latency/loss (`sudo tc qdisc add dev wlan0 root netem delay 20ms loss 1%`) to validate the jitter buffer and reconnection logic under realistic Wi-Fi conditions, not just ideal LAN.

## 8. Debugging Tips

- **Test GStreamer pipelines standalone first**, outside the Python app, using `gst-launch-1.0` with the exact pipeline strings from [ARCHITECTURE.md §10](ARCHITECTURE.md#10-screen-capture--encode-pipeline-server)/[§11](ARCHITECTURE.md#11-decode--render-pipeline-client). This isolates "is my pipeline wrong" from "is my Python wiring wrong."
- **Use Wireshark** to inspect the control channel (filter: `tcp.port == 48321`) — since it's plain JSON, you can read messages directly in the packet view.
- **`GST_DEBUG=3` environment variable** enables verbose GStreamer logging when a pipeline fails to link or negotiate caps.
- **`xrandr --verbose`** to confirm the virtual output's actual negotiated mode matches what was requested.

## 9. Packaging & Release

- **Windows client:** PyInstaller with `--onefile --windowed`, bundling the GStreamer runtime DLLs (use `--add-binary` for the GStreamer plugin directory, or document it as a separate prerequisite installer for v1 to keep the build simple).
- **Linux server:** PyInstaller `--onefile`, or ship as a `.deb`/AppImage in a later milestone; system GStreamer/X11 packages remain external dependencies since they're standard on virtually every Linux desktop distro already.
- **CI (GitHub Actions):** run `pytest` + `ruff` + `black --check` on every PR (matrix: Ubuntu for server, Windows for client); build release artifacts on tag push.

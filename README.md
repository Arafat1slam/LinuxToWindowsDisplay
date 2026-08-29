# ScreenLink

**Turn an old Windows laptop into a wireless second monitor for your Linux desktop — over Wi‑Fi, no dongles, no cables.**

> Working name. Rename freely before you publish — check that the name isn't already taken on GitHub/PyPI first.

ScreenLink is an open-source alternative to tools like Spacedesk: a **server** running on your Linux desktop creates a virtual display, captures it, and streams it over your LAN to a **client** app on a Windows laptop, which renders it full-screen and sends mouse/keyboard input back to the server.

---

## Table of Contents
- [Features](#features)
- [How It Works (30-second version)](#how-it-works-30-second-version)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Project Status](#project-status)
- [Documentation](#documentation)
- [License](#license)

---

## Features

**MVP (v0.1)**
- 🔍 Automatic discovery of Linux hosts from the Windows client (no manual IP entry)
- 🖥️ Extends the Linux desktop with a genuine virtual display (not screen mirroring)
- 📶 Low-latency H.264 video streaming, hardware-accelerated encode/decode where available
- 🖱️⌨️ Mouse and keyboard passthrough from the Windows client back to the Linux host
- ⚙️ Adjustable resolution, framerate, and bitrate
- 🔄 Auto-reconnect on Wi-Fi drop or client sleep/wake

**Roadmap (post-MVP)**
- Touch/pen input passthrough
- Multiple simultaneous client displays
- Wayland-native capture path (see [ARCHITECTURE.md](ARCHITECTURE.md#9-virtual-display-creation-on-linux))
- macOS and Android clients
- Optional wired (USB-Ethernet) transport for lower, more consistent latency
- Clipboard sync

## How It Works (30-second version)

```
┌─────────────────────┐         Wi-Fi (LAN)         ┌──────────────────────┐
│   Linux Desktop      │ ◄────────────────────────► │   Windows Laptop      │
│   (Server)           │                              │   (Client)            │
│                       │   1. mDNS discovery          │                       │
│  Virtual display  ────┼──► 2. Capture + encode ──────┼──► Decode + render    │
│  (xrandr/dummy)       │      (H.264 / RTP / UDP)      │   full-screen         │
│                       │                              │                       │
│  uinput virtual   ◄───┼──── 3. Input events ──────────┼─── Mouse/keyboard     │
│  mouse & keyboard     │      (JSON / TCP)              │   hooks               │
└─────────────────────┘                              └──────────────────────┘
```

Full protocol and pipeline details live in [ARCHITECTURE.md](ARCHITECTURE.md).

## Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Control-plane language | **Python 3.11+** | Fast to develop and review for an open-source contributor base; excellent bindings for every library this project needs (GStreamer, zeroconf, PyQt, uinput). |
| Media pipeline | **GStreamer** (via `PyGObject`/`gst-python`) | Cross-platform (runs on both Linux and Windows), gives us hardware-accelerated H.264 encode/decode, RTP packetization, and jitter buffering **for free** instead of hand-rolling a video pipeline — this is the single biggest risk-reduction decision in the stack. |
| GUI toolkit | **PyQt6** | Native look on both platforms, mature video widget support, system tray integration for a background client. |
| Video codec | **H.264** (`vaapih264enc`/`nvh264enc`/`qsvh264enc` hardware, `x264enc` software fallback) | Universally hardware-decodable on Windows laptops from the last decade; software fallback guarantees it always works, just slower. |
| Video transport | **RTP over UDP** | Real-time video tolerates dropped frames far better than added latency; UDP + RTP (via GStreamer's `rtph264pay`/`rtph264depay`) is the standard, battle-tested approach — see [ARCHITECTURE.md §7](ARCHITECTURE.md#7-video-channel-protocol-spec). |
| Control & input transport | **TCP + JSON** | Input events are small and infrequent enough that TCP's ordering/reliability guarantees matter more than its latency cost; JSON keeps the protocol trivially debuggable with Wireshark or `nc`. |
| Discovery | **mDNS/Zeroconf** (`zeroconf` Python package) | Zero-configuration LAN discovery, same mechanism Chromecast/AirPlay use; no need to type IP addresses. |
| Input injection (Linux) | **`uinput`** kernel module | Works identically under X11 *and* Wayland since it operates below the display server, unlike X11-specific input APIs (`XTestFakeKeyEvent` etc.) which don't work on Wayland. |
| Input capture (Windows) | **`pynput`** / raw Win32 hooks | Low-level global hooks for mouse/keyboard, independent of which window has focus. |
| Packaging | **PyInstaller** | Produces a single-file `.exe` for the Windows client and a standalone binary/AppImage for the Linux server — end users shouldn't need a Python environment. |

### Why not Go or Rust for v1?

Both were seriously considered:

- **Go** has a shallow multimedia ecosystem — there's no mature, actively maintained GStreamer or FFmpeg binding, so the project would end up either shelling out to `gst-launch`/`ffmpeg` as subprocesses (losing fine-grained pipeline control) or writing cgo bindings from scratch (a project in itself).
- **Rust** offers real performance and safety advantages, and `gstreamer-rs` is genuinely excellent — but it raises the contribution barrier for an open-source hobby project considerably, and the bottleneck in this system is the H.264 hardware encoder/network, not the language runtime. Python + GStreamer already reaches near-native pipeline performance because the hot path (encode/decode/network I/O) runs in GStreamer's C core, not in the Python interpreter.

A Rust rewrite of the client is listed as a stretch goal once the protocol is stable — see [ARCHITECTURE.md](ARCHITECTURE.md) for how the protocol is deliberately kept language-agnostic (plain JSON + standard RTP) to make that possible later without a breaking change.

## Installation

### Server (Linux)

```bash
# System dependencies (Debian/Ubuntu example)
sudo apt install python3-pip python3-venv \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-vaapi \
  gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 python3-gi \
  x11-xserver-utils

git clone https://github.com/<your-username>/screenlink.git
cd screenlink/server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Grant uinput access (one-time, see DEVELOPMENT.md for the udev rule)
sudo usermod -aG input $USER

python3 -m screenlink_server
```

### Client (Windows)

1. Install the [GStreamer runtime](https://gstreamer.freedesktop.org/download/) (full package, MSVC 64-bit).
2. Download the latest `ScreenLink-Client.exe` from the [Releases](../../releases) page — no Python install required.
3. Run it. It will auto-discover ScreenLink servers on your Wi-Fi network.

## Usage

1. Start `screenlink_server` on the Linux desktop.
2. Launch `ScreenLink-Client.exe` on the Windows laptop, on the **same Wi-Fi network**.
3. Select the discovered server from the client's device list and click **Connect**.
4. The Linux desktop gains a new display; drag windows onto it as usual.
5. Adjust resolution/quality from the client's settings panel if the picture is soft or laggy.

## Project Status

Early-stage / pre-alpha. This repository currently defines the architecture and contribution structure; implementation is tracked in the [Issues](../../issues) tab against the step list in [DEVELOPMENT.md](DEVELOPMENT.md).

## Documentation

| File | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, protocol specs, data flow |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Environment setup and step-by-step build guide |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, coding standards, PR process |

## License

MIT — see [LICENSE.md](LICENSE.md).

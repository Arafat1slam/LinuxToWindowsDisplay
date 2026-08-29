from __future__ import annotations

import logging
from typing import Optional, Tuple

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

logger = logging.getLogger(__name__)

class CapturePipeline:
    """
    GStreamer capture and encode pipeline.
    See ARCHITECTURE.md §10.
    """
    def __init__(self) -> None:
        self.pipeline: Optional[Gst.Pipeline] = None

    def probe_encoder(self) -> str:
        """Checks available encoders and returns the best available H264 encoder."""
        encoders = ["vaapih264enc", "nvh264enc", "qsvh264enc", "x264enc"]
        registry = Gst.Registry.get()
        for enc in encoders:
            if registry.find_plugin(enc) or registry.find_feature(enc, Gst.ElementFactory):
                logger.info(f"Selected encoder: {enc}")
                return enc
        logger.warning("No hardware encoder found, falling back to x264enc")
        return "x264enc"

    def start(
        self,
        client_ip: str,
        udp_port: int,
        geometry: Tuple[int, int, int, int],
        fps: int,
        bitrate: int,
    ) -> None:
        """Starts the capture pipeline."""
        if self.pipeline:
            logger.warning("Pipeline already running.")
            return

        startx, starty, endx, endy = geometry
        encoder = self.probe_encoder()

        pipeline_str = (
            f"ximagesrc use-damage=0 startx={startx} starty={starty} endx={endx} endy={endy} ! "
            f"video/x-raw,framerate={fps}/1 ! "
            f"videoconvert ! "
            f"{encoder} ! "
            f"h264parse config-interval=1 ! "
            f"rtph264pay pt=96 ! "
            f"udpsink host={client_ip} port={udp_port}"
        )

        logger.info(f"Starting GStreamer pipeline: {pipeline_str}")
        self.pipeline = Gst.parse_launch(pipeline_str)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self) -> None:
        """Stops the capture pipeline."""
        if self.pipeline:
            logger.info("Stopping GStreamer pipeline.")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

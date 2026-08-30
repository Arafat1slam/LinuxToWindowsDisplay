from __future__ import annotations

import logging
from typing import Union

import gi

try:
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
except (ImportError, ValueError) as e:
    logging.warning("GStreamer not found or failed to init: %s", e)
    Gst = None

logger = logging.getLogger(__name__)

class RenderPipeline:
    """
    GStreamer decode+render pipeline (ARCHITECTURE.md §11).
    """

    def __init__(self) -> None:
        self.pipeline: Union[gi.repository.Gst.Pipeline, None] = None
        self.jitter_buffer: Union[gi.repository.Gst.Element, None] = None
        self._is_playing: bool = False

    def probe_decoder(self) -> str:
        """Checks for hardware decoders, falls back to software."""
        if Gst is None:
            return "avdec_h264"

        factory = Gst.ElementFactory.find("d3d11h264dec")
        if factory:
            return "d3d11h264dec"
        return "avdec_h264"

    def probe_sink(self) -> str:
        """Checks for optimal video sink."""
        if Gst is None:
            return "autovideosink"

        factory = Gst.ElementFactory.find("d3d11videosink")
        if factory:
            return "d3d11videosink"
        return "autovideosink"

    def start(self, udp_port: int, jitter_buffer_latency: int) -> None:
        """Starts the GStreamer pipeline."""
        if Gst is None:
            logger.error("GStreamer not initialized")
            return

        if self._is_playing:
            self.stop()

        decoder = self.probe_decoder()
        sink = self.probe_sink()

        # Pipeline: udpsrc ! rtpjitterbuffer ! rtph264depay ! h264parse ! decoder ! sink
        pipeline_str = (
            f"udpsrc port={udp_port} caps=\"application/x-rtp,encoding-name=H264,payload=96\" ! "
            f"rtpjitterbuffer name=jbuf latency={jitter_buffer_latency} ! "
            f"rtph264depay ! h264parse ! {decoder} ! {sink} sync=false"
        )

        logger.info("Starting pipeline: %s", pipeline_str)
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            self.jitter_buffer = self.pipeline.get_by_name("jbuf")

            self.pipeline.set_state(Gst.State.PLAYING)
            self._is_playing = True
        except Exception as e:
            logger.error("Failed to start GStreamer pipeline: %s", e)

    def stop(self) -> None:
        """Stops the pipeline."""
        if self.pipeline and self._is_playing:
            logger.info("Stopping GStreamer pipeline")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.jitter_buffer = None
            self._is_playing = False

    def update_jitter_buffer(self, latency_ms: int) -> None:
        """Live updates the jitter buffer latency."""
        if self.jitter_buffer:
            logger.info("Updating jitter buffer latency to %d ms", latency_ms)
            self.jitter_buffer.set_property("latency", latency_ms)

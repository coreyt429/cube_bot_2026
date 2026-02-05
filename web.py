"""
Flask web API for CubeBot control.
"""

from __future__ import annotations

import io
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from flask import Flask, Response, jsonify, request, send_file

from cube_bot import CubeBot
from display import Display

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput

    PICAMERA2_AVAILABLE = True
except Exception:  # pragma: no cover - hardware/runtime dependent
    PICAMERA2_AVAILABLE = False


logger = logging.getLogger("web")


class StreamingOutput(io.BufferedIOBase):
    def __init__(self) -> None:
        self.frame: Optional[bytes] = None
        self.condition = threading.Condition()

    def write(self, buf: bytes) -> int:
        with self.condition:
            self.frame = bytes(buf)
            self.condition.notify_all()
        return len(buf)


class CameraManager:
    def __init__(self) -> None:
        self._picam2: Optional[Picamera2] = None
        self._output: Optional[StreamingOutput] = None
        self._streaming = False
        self._lock = threading.Lock()

    def _ensure_camera(self) -> Picamera2:
        if not PICAMERA2_AVAILABLE:
            raise RuntimeError("picamera2 is not available")
        if self._picam2 is None:
            picam2 = Picamera2()
            picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
            self._picam2 = picam2
        return self._picam2

    def capture_still(self, path: Path) -> None:
        picam2 = self._ensure_camera()
        with self._lock:
            if not picam2.started:
                picam2.start()
                time.sleep(0.2)
            picam2.capture_file(str(path))

    def start_stream(self) -> None:
        picam2 = self._ensure_camera()
        with self._lock:
            if self._streaming:
                return
            self._output = StreamingOutput()
            encoder = MJPEGEncoder()
            picam2.start_recording(encoder, FileOutput(self._output))
            self._streaming = True

    @property
    def output(self) -> Optional[StreamingOutput]:
        return self._output


def create_app() -> Flask:
    app = Flask(__name__)
    bot: Optional[CubeBot] = None
    bot_error: Optional[str] = None
    try:
        bot = CubeBot("calibration")
    except Exception as exc:  # pragma: no cover - hardware/runtime dependent
        logger.exception("CubeBot init failed")
        bot_error = str(exc)

    display: Optional[Display] = None
    display_error: Optional[str] = None
    try:
        display = Display()
    except Exception as exc:  # pragma: no cover - hardware/runtime dependent
        logger.exception("Display init failed")
        display_error = str(exc)
    camera = CameraManager()

    def resolve_arm(side: str):
        if bot is None:
            return None
        arm_key = {"left": "l", "right": "r"}.get(side)
        if arm_key is None or arm_key not in bot.arms:
            return None
        return bot.arms[arm_key]

    @app.get("/health")
    def health() -> Response:
        return jsonify({"status": "ok"})

    @app.route("/gripper/<side>/<action>", methods=["POST", "GET"])
    def gripper(side: str, action: str) -> Response:
        arm = resolve_arm(side)
        if arm is None:
            if bot_error:
                return jsonify({"error": bot_error}), 500
            return jsonify({"error": "invalid side"}), 400
        if action == "open":
            arm.open()
        elif action == "close":
            arm.close()
        else:
            return jsonify({"error": "invalid action"}), 400
        return jsonify({"status": "ok", "arm": side, "action": action})

    @app.route("/rotate/<side>/position/<int:degrees>", methods=["POST", "GET"])
    def rotate_position(side: str, degrees: int) -> Response:
        if degrees not in (0, 90, 180, 270):
            return jsonify({"error": "degrees must be 0/90/180/270"}), 400
        arm = resolve_arm(side)
        if arm is None:
            if bot_error:
                return jsonify({"error": bot_error}), 500
            return jsonify({"error": "invalid side"}), 400
        arm.set_degrees(degrees)
        return jsonify({"status": "ok", "arm": side, "degrees": degrees})

    @app.route("/rotate/<side>/degrees/<degrees>", methods=["POST", "GET"])
    def rotate_degrees(side: str, degrees: str) -> Response:
        arm = resolve_arm(side)
        if arm is None:
            if bot_error:
                return jsonify({"error": bot_error}), 500
            return jsonify({"error": "invalid side"}), 400
        try:
            deg_val = int(degrees)
        except ValueError:
            return jsonify({"error": "degrees must be int"}), 400
        arm.rotate(deg_val)
        return jsonify({"status": "ok", "arm": side, "degrees": deg_val})

    @app.route("/camera/pic", methods=["POST", "GET"])
    def camera_pic() -> Response:
        if not PICAMERA2_AVAILABLE:
            return jsonify({"error": "picamera2 not available"}), 501
        tmp_path = Path("/tmp/cube_bot_snap.jpg")
        try:
            camera.capture_still(tmp_path)
        except Exception as exc:  # pragma: no cover - hardware/runtime dependent
            logger.exception("capture_still failed")
            return jsonify({"error": str(exc)}), 500
        return send_file(tmp_path, mimetype="image/jpeg")

    @app.route("/camera/stream", methods=["POST", "GET"])
    def camera_stream() -> Response:
        if not PICAMERA2_AVAILABLE:
            return jsonify({"error": "picamera2 not available"}), 501
        try:
            camera.start_stream()
        except Exception as exc:  # pragma: no cover - hardware/runtime dependent
            logger.exception("start_stream failed")
            return jsonify({"error": str(exc)}), 500
        stream_url = request.host_url.rstrip("/") + "/camera/stream.mjpg"
        return jsonify({"status": "ok", "url": stream_url})

    @app.route("/camera/stream.mjpg", methods=["GET"])
    def camera_stream_mjpg() -> Response:
        if not PICAMERA2_AVAILABLE:
            return jsonify({"error": "picamera2 not available"}), 501
        if camera.output is None:
            return jsonify({"error": "stream not started"}), 400

        def generate():
            output = camera.output
            assert output is not None
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                if not frame:
                    continue
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii")
                    + frame
                    + b"\r\n"
                )

        return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/display/update", methods=["POST"])
    def display_update() -> Response:
        payload = request.get_json(silent=True)
        if not isinstance(payload, list):
            return jsonify({"error": "expected JSON list of strings"}), 400
        if display is None:
            return jsonify({"error": display_error or "display not available"}), 500
        messages = [str(item) for item in payload]
        header = request.args.get("header", "Message")
        try:
            display.draw_message(header, messages)
        except Exception as exc:  # pragma: no cover - hardware/runtime dependent
            logger.exception("display update failed")
            return jsonify({"error": str(exc)}), 500
        return jsonify({"status": "ok", "lines": len(messages)})

    @app.route("/config", methods=["GET"])
    def config_get() -> Response:
        if bot is None:
            return jsonify({"error": bot_error or "bot not available"}), 500
        return jsonify(bot.cfg)

    @app.route("/config", methods=["POST"])
    def config_set() -> Response:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "expected JSON object"}), 400
        if bot is None:
            return jsonify({"error": bot_error or "bot not available"}), 500
        bot.cfg.update(payload)
        bot.save_config()
        return jsonify({"status": "ok"})

    @app.route("/calibrate/nudge/<side>/<servo>/<int:delta>", methods=["POST", "GET"])
    def calibrate_nudge(side: str, servo: str, delta: int) -> Response:
        arm = resolve_arm(side)
        if arm is None:
            if bot_error:
                return jsonify({"error": bot_error}), 500
            return jsonify({"error": "invalid side"}), 400
        if servo not in ("open", "rotate"):
            return jsonify({"error": "invalid servo"}), 400
        current = int(getattr(arm.servos[servo], "qus", 0) or 0)
        arm.servos[servo].set_qus(current + delta, wait=True)
        return jsonify({"status": "ok", "arm": side, "servo": servo, "qus": arm.servos[servo].qus})

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(host="0.0.0.0", port=5000, threaded=True)

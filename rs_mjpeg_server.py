"""Podglad na zywo z RealSense D415 przez przegladarke (MJPEG po HTTP).

Uzycie na Pi:
    python rs_mjpeg_server.py [--port 8080] [--depth-res 424x240] [--max-mm 1500]

Glebia w nizszej rozdzielczosci ma mniejszy minimalny zasieg (MinZ w D4xx skaluje sie
z rozdzielczoscia glebi), wiec bliskie obiekty przestaja byc dziura. Kolor zostaje 640x480,
glebia jest wyrownywana do koloru przez rs.align.

Potem w przegladarce na laptopie: http://<IP_PI>:8080/
Zatrzymanie: Ctrl+C.
"""

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pyrealsense2 as rs

WIDTH, HEIGHT, FPS = 640, 480, 30
DEPTH_WIDTH, DEPTH_HEIGHT = 424, 240
MAX_MM = 1500  # odleglosc, przy ktorej kolormapa sie nasyca

latest_jpg = None
latest_lock = threading.Lock()
stop_event = threading.Event()


def capture_loop():
    global latest_jpg
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, WIDTH, HEIGHT, rs.format.bgr8, FPS)
    config.enable_stream(rs.stream.depth, DEPTH_WIDTH, DEPTH_HEIGHT, rs.format.z16, FPS)
    profile = pipeline.start(config)
    depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
    alpha = 255.0 / (MAX_MM / 1000.0 / depth_scale)
    print(f"RealSense: color {WIDTH}x{HEIGHT}, depth {DEPTH_WIDTH}x{DEPTH_HEIGHT}")
    align = rs.align(rs.stream.color)
    print("RealSense: stream started")
    try:
        while not stop_event.is_set():
            frames = pipeline.wait_for_frames()
            frames = align.process(frames)
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()
            if not color_frame or not depth_frame:
                continue
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())
            depth_colormap = cv2.applyColorMap(
                cv2.convertScaleAbs(depth_image, alpha=alpha), cv2.COLORMAP_JET
            )
            combined = np.hstack((color_image, depth_colormap))
            ok, buf = cv2.imencode(".jpg", combined, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                with latest_lock:
                    latest_jpg = buf.tobytes()
    finally:
        pipeline.stop()
        print("RealSense: stream stopped")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            body = (
                b"<html><body style='margin:0;background:#111'>"
                b"<img src='/stream' style='width:100%'></body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/stream":
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            try:
                while not stop_event.is_set():
                    with latest_lock:
                        frame = latest_jpg
                    if frame is None:
                        time.sleep(0.05)
                        continue
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    time.sleep(1 / FPS)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        self.send_response(404)
        self.end_headers()


def main():
    global DEPTH_WIDTH, DEPTH_HEIGHT, MAX_MM
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--depth-res", default=f"{DEPTH_WIDTH}x{DEPTH_HEIGHT}",
                        help="rozdzielczosc glebi, np. 424x240, 480x270, 640x480")
    parser.add_argument("--max-mm", type=int, default=MAX_MM,
                        help="odleglosc [mm] dla czerwonego koloru kolormapy")
    args = parser.parse_args()

    DEPTH_WIDTH, DEPTH_HEIGHT = (int(v) for v in args.depth_res.lower().split("x"))
    MAX_MM = args.max_mm

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Otworz w przegladarce: http://<IP_PI>:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.shutdown()


if __name__ == "__main__":
    main()

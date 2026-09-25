import sys
import numpy as np
import cv2
import pyrealsense2 as rs

WIDTH, HEIGHT, FPS = 640, 480, 30
OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "snapshot.png"

pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.color, WIDTH, HEIGHT, rs.format.bgr8, FPS)
config.enable_stream(rs.stream.depth, WIDTH, HEIGHT, rs.format.z16, FPS)

pipeline.start(config)
align = rs.align(rs.stream.color)

try:
    # drop a few frames so auto-exposure settles
    for _ in range(15):
        frames = pipeline.wait_for_frames()

    frames = align.process(frames)
    color_frame = frames.get_color_frame()
    depth_frame = frames.get_depth_frame()
    if not color_frame or not depth_frame:
        raise RuntimeError("brak klatki koloru/glebi")

    color_image = np.asanyarray(color_frame.get_data())
    depth_image = np.asanyarray(depth_frame.get_data())
    depth_colormap = cv2.applyColorMap(
        cv2.convertScaleAbs(depth_image, alpha=0.03), cv2.COLORMAP_JET
    )
    combined = np.hstack((color_image, depth_colormap))
    cv2.imwrite(OUT_PATH, combined)
    print(f"Zapisano: {OUT_PATH}, shape={combined.shape}")
finally:
    pipeline.stop()

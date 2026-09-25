"""
Strojenie progu HSV detektora szyszek na zywo albo na zapisanych klatkach.

Okno z suwakami H/S/V lo/hi + min_area. Obok siebie: obraz | maska | detekcje
(draw_debug). Suwaki startuja z wartosci z konfiguracji.

Uzycie (z katalogu repo):
    python tools/calibrate_hsv.py                         # RealSense
    python tools/calibrate_hsv.py --source frames/        # katalog PNG (zapetlony)
    python tools/calibrate_hsv.py --source klatka.png     # jeden obraz
    python tools/calibrate_hsv.py --source film.mp4
    python tools/calibrate_hsv.py --sample                # klik na obrazie = wypis HSV

Klawisze:
    s        zapisz hsv + min_area do JSON konfiguracji (--config albo domyslny)
    spacja   pauza / wznowienie klatek (na plikach: zatrzymaj sie na ciekawej)
    n        nastepna klatka (w pauzie)
    q / ESC  wyjscie

--sample: klikniecie na dowolnym z trzech paneli wypisuje HSV piksela oraz
min/max z lat 5x5 wokol niego. Klikaj po szyszce i po murawie, patrz, ktory
kanal je rozdziela (na tym torze o zmierzchu bylo to V, nie H - patrz
sample_colors.py).
"""
from __future__ import annotations

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pinecone_bot.camera import FileCamera, make_camera  # noqa: E402
from pinecone_bot.config import Config, HsvRange  # noqa: E402
from pinecone_bot.detector import HsvConeDetector  # noqa: E402

WINDOW = "calibrate_hsv"
BARS = [
    # (nazwa suwaka, max)
    ("H lo", 179), ("H hi", 179),
    ("S lo", 255), ("S hi", 255),
    ("V lo", 255), ("V hi", 255),
    ("min_area", 5000),
]
FILE_FPS = 10.0  # tempo odtwarzania zrodel plikowych


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Strojenie progu HSV detektora")
    p.add_argument("--source", help="plik/katalog/wideo zamiast RealSense")
    p.add_argument("--config", help="sciezka do JSON konfiguracji")
    p.add_argument("--sample", action="store_true",
                   help="klik na obrazie wypisuje HSV piksela i lat 5x5")
    p.add_argument("--scale", type=float, default=0.0,
                   help="skala okna (0 = automatycznie, zeby zmiescic 3 panele)")
    return p.parse_args()


def setup_trackbars(cfg: Config) -> None:
    lo, hi = cfg.detector.hsv.lo, cfg.detector.hsv.hi
    start = {
        "H lo": lo[0], "H hi": hi[0],
        "S lo": lo[1], "S hi": hi[1],
        "V lo": lo[2], "V hi": hi[2],
        "min_area": cfg.detector.min_area_px,
    }
    for name, maximum in BARS:
        value = int(max(0, min(maximum, start[name])))
        cv2.createTrackbar(name, WINDOW, value, maximum, lambda _v: None)


def apply_trackbars(cfg: Config) -> None:
    """Wpisz suwaki do cfg.detector - detektor trzyma referencje, wiec widzi zmiane."""
    g = lambda name: cv2.getTrackbarPos(name, WINDOW)  # noqa: E731
    lo = (g("H lo"), g("S lo"), g("V lo"))
    hi = (g("H hi"), g("S hi"), g("V hi"))
    cfg.detector.hsv = HsvRange(lo, hi)
    cfg.detector.min_area_px = int(g("min_area"))


def describe_pixel(bgr: np.ndarray, col: int, row: int) -> str:
    h, w = bgr.shape[:2]
    col = max(0, min(w - 1, col))
    row = max(0, min(h - 1, row))
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    px = hsv[row, col]
    r0, r1 = max(0, row - 2), min(h, row + 3)
    c0, c1 = max(0, col - 2), min(w, col + 3)
    patch = hsv[r0:r1, c0:c1].reshape(-1, 3)
    lo = patch.min(axis=0)
    hi = patch.max(axis=0)
    return (f"({col},{row}) HSV=({px[0]},{px[1]},{px[2]})  "
            f"5x5 min=({lo[0]},{lo[1]},{lo[2]}) max=({hi[0]},{hi[1]},{hi[2]})")


def main() -> None:
    args = parse_args()
    cfg_path = args.config or Config.default_path()
    cfg = Config.load(cfg_path)
    detector = HsvConeDetector(cfg.detector)
    cam = make_camera(cfg, args.source)
    is_file = isinstance(cam, FileCamera)

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    setup_trackbars(cfg)

    state = {"frame": None, "scale": 1.0}

    if args.sample:
        def on_mouse(event, x, y, _flags, _param):
            if event != cv2.EVENT_LBUTTONDOWN or state["frame"] is None:
                return
            frame = state["frame"]
            w = frame.shape[1]
            col = int(x / state["scale"]) % w
            row = int(y / state["scale"])
            print("  " + describe_pixel(frame, col, row))
        cv2.setMouseCallback(WINDOW, on_mouse)
        print("Tryb --sample: klikaj na obrazie, HSV leci do konsoli.")

    print(f"Konfiguracja: {cfg_path}  (s = zapis, spacja = pauza, n = nastepna, q = wyjscie)")
    wait_ms = int(1000 / FILE_FPS) if is_file else 1
    paused = False
    frame = None
    try:
        while True:
            if frame is None or not paused:
                frame, _ = cam.read()
                state["frame"] = frame
            apply_trackbars(cfg)
            dets = detector.detect(frame)
            mask_bgr = cv2.cvtColor(detector.last_mask, cv2.COLOR_GRAY2BGR)
            label = f"n={len(dets)} hsv={cfg.detector.hsv.lo}-{cfg.detector.hsv.hi} area>={cfg.detector.min_area_px}"
            if is_file:
                label += f" {cam.current_name}"
            if paused:
                label += " [PAUZA]"
            vis = HsvConeDetector.draw_debug(frame, dets, cx=cfg.cx, text=label)
            panel = np.hstack((frame, mask_bgr, vis))

            scale = args.scale
            if scale <= 0:
                scale = min(1.0, 1800.0 / panel.shape[1])
            state["scale"] = scale
            if scale != 1.0:
                panel = cv2.resize(panel, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            cv2.imshow(WINDOW, panel)

            key = cv2.waitKey(wait_ms) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                paused = not paused
            elif key == ord("n"):
                frame, _ = cam.read()
                state["frame"] = frame
            elif key == ord("s"):
                path = cfg.save(cfg_path)
                print(f"Zapisano hsv lo={cfg.detector.hsv.lo} hi={cfg.detector.hsv.hi} "
                      f"min_area={cfg.detector.min_area_px} -> {path}")
    except KeyboardInterrupt:
        print("\nPrzerwano.")
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

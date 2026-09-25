"""
Zbieranie klatek z kamery do strojenia detektora na sucho.

Zapisuje obraz kolorowy jako PNG co --every sekund przez --seconds sekund,
opcjonalnie glebie w metrach jako .npy (--depth; tylko z RealSense).
Tak zbieramy prawdziwe klatki murawy i szyszek, na ktorych potem odpalamy
tools/calibrate_hsv.py --source frames/.

Uzycie (z katalogu repo):
    python tools/snap_frames.py --out frames/ --every 0.5 --seconds 20
    python tools/snap_frames.py --out frames/ --depth --show
    python tools/snap_frames.py --out frames2/ --source film.mp4   # z pliku, do testow

Nazwy: frame_0000.png, depth_0000.npy (float32 HxW, 0 = brak pomiaru).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pinecone_bot.camera import make_camera  # noqa: E402
from pinecone_bot.config import Config  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Zapis klatek z kamery do PNG")
    p.add_argument("--out", default="frames", help="katalog wyjsciowy")
    p.add_argument("--every", type=float, default=0.5, help="odstep miedzy zapisami [s]")
    p.add_argument("--seconds", type=float, default=20.0, help="ile sekund zbierac")
    p.add_argument("--source", help="plik/katalog/wideo zamiast RealSense")
    p.add_argument("--depth", action="store_true", help="zapisuj tez glebie jako .npy")
    p.add_argument("--show", action="store_true", help="okno podgladu (q konczy)")
    p.add_argument("--config", help="sciezka do JSON konfiguracji")
    p.add_argument("--prefix", default="frame", help="prefiks nazw plikow")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = Config.load(args.config)
    os.makedirs(args.out, exist_ok=True)

    # Numeracja od pierwszego wolnego numeru, zeby kolejne sesje nie nadpisywaly.
    existing = [f for f in os.listdir(args.out)
                if f.startswith(args.prefix + "_") and f.endswith(".png")]
    start_idx = 0
    for f in existing:
        try:
            start_idx = max(start_idx, int(f[len(args.prefix) + 1:-4]) + 1)
        except ValueError:
            pass

    cam = make_camera(cfg, args.source, depth=args.depth)
    print(f"Zrodlo: {'RealSense' if args.source is None else args.source}, "
          f"zapis do {args.out}/ co {args.every:.2f} s przez {args.seconds:.0f} s")
    if args.depth and args.source is not None:
        print("UWAGA: --depth nie ma sensu ze zrodlem plikowym, glebi nie bedzie")

    saved = 0
    idx = start_idx
    t_start = time.monotonic()
    t_next = t_start
    try:
        while True:
            now = time.monotonic()
            if now - t_start >= args.seconds:
                break
            bgr, depth = cam.read()
            if now >= t_next:
                name = f"{args.prefix}_{idx:04d}"
                cv2.imwrite(os.path.join(args.out, name + ".png"), bgr)
                if args.depth and depth is not None:
                    np.save(os.path.join(args.out, f"depth_{idx:04d}.npy"), depth)
                saved += 1
                idx += 1
                t_next = now + args.every
                print(f"  zapisano {name}.png  (t={now - t_start:5.1f} s)")
            if args.show:
                view = bgr.copy()
                cv2.putText(view, f"saved {saved}  t={now - t_start:.1f}s", (8, 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.imshow("snap_frames", view)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
            elif args.source is not None:
                time.sleep(0.02)  # zrodlo plikowe nie blokuje, nie krecmy sie w miejscu
    except KeyboardInterrupt:
        print("\nPrzerwano.")
    finally:
        cam.close()
        if args.show:
            cv2.destroyAllWindows()
    print(f"Zapisano {saved} klatek do {args.out}/")


if __name__ == "__main__":
    main()

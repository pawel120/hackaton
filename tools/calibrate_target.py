"""
Kalibracja target_row nagranych chwytow i kolumny cfg.cx.

Robot ustawia sie do szyszki po obrazie: obraca sie, az szyszka jest w kolumnie
cfg.cx, i jedzie, az jest w wierszu grasp.target_row. Ten skrypt mierzy, gdzie
w obrazie lezy szyszka, gdy fizycznie stoi w punkcie, ktory dany chwyt podnosi.

Procedura:
    1. Odpal replay chwytu (np. grasp_near) i zobacz, gdzie chwytak sie zamyka.
    2. Poloz szyszke DOKLADNIE w tym miejscu.
    3. Tu: wybierz chwyt klawiszem 1/2/3 (albo --grasp NAME), poczekaj, az
       srednia z 15 klatek sie ustabilizuje, wcisnij s.
    4. Powtorz dla kazdego chwytu (near / mid / far).
    5. c zapisuje aktualna kolumne szyszki jako cfg.cx (srodek chwytaka w obrazie).
    6. w zapisuje JSON konfiguracji. q wychodzi.

Uzycie (z katalogu repo):
    python tools/calibrate_target.py                      # RealSense, okno OpenCV
    python tools/calibrate_target.py --grasp grasp_near
    python tools/calibrate_target.py --source frames/     # na zapisanych klatkach

Bez pulpitu (Pi OS Lite przez SSH - cv2.imshow nie dziala):
    python tools/calibrate_target.py --headless                          # tylko pomiar, nic nie zapisuje
    python tools/calibrate_target.py --headless --grasp grasp_mid --write --set-cx
        -> target_row chwytu grasp_mid = srednia py, cx = srednia px, zapis do configu
    python tools/calibrate_target.py --headless --set-cx --write         # tylko cx

Zapisywana jest SREDNIA z ostatnich 15 klatek (px, py) najblizszej detekcji,
nie jedna klatka - detekcja szumi o 1-2 px i to by sie przenioslo na dojazd.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import deque

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pinecone_bot.camera import FileCamera, make_camera  # noqa: E402
from pinecone_bot.config import Config  # noqa: E402
from pinecone_bot.detector import HsvConeDetector  # noqa: E402

WINDOW = "calibrate_target"
AVG_FRAMES = 15
FILE_FPS = 10.0
PRINT_EVERY_S = 0.5
GRASP_COLORS = [(0, 255, 255), (255, 200, 0), (200, 0, 255), (0, 200, 0), (255, 255, 255)]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kalibracja target_row chwytow i cx")
    p.add_argument("--source", help="plik/katalog/wideo zamiast RealSense")
    p.add_argument("--config", help="sciezka do JSON konfiguracji")
    p.add_argument("--grasp", help="nazwa chwytu do kalibracji na start")
    p.add_argument("--headless", action="store_true",
                   help="bez okna: zmierz srednia z --frames klatek, wypisz i (z --write) zapisz")
    p.add_argument("--frames", type=int, default=AVG_FRAMES,
                   help=f"headless: ile kolejnych klatek z detekcja usrednic (domyslnie {AVG_FRAMES})")
    p.add_argument("--write", action="store_true",
                   help="headless: zapisz wynik do configu (target_row chwytu z --grasp i/lub cx z --set-cx)")
    p.add_argument("--set-cx", action="store_true", help="headless: srednia kolumna szyszki -> cfg.cx")
    return p.parse_args()


def print_instructions(cfg: Config, cfg_path: str) -> None:
    print("=== calibrate_target ===")
    print(f"Konfiguracja: {cfg_path}")
    print(f"cx = {cfg.cx:.1f}")
    for i, g in enumerate(cfg.grasps):
        print(f"  [{i + 1}] {g.name}: target_row = {g.target_row:.1f}")
    print()
    print("Poloz szyszke DOKLADNIE tam, gdzie nagrany chwyt ja podnosi, wybierz chwyt")
    print("klawiszem 1/2/3, poczekaj na stabilna srednia i wcisnij s. Powtorz dla")
    print("near / mid / far. c = zapisz kolumne szyszki jako cx. w = zapisz JSON.")
    print("q = wyjscie. Srednia z ostatnich 15 klatek leci do konsoli.")
    print()


def collect_average(cam, detector, n_frames: int, max_reads: int | None = None):
    """
    Srednia (px, py) z n_frames KOLEJNYCH klatek z detekcja (najblizsza szyszka = dets[0]).
    Klatka bez detekcji zeruje serie, jak w trybie z oknem. Zwraca
    (avg_px, avg_py, std_px, std_py, n) albo None, gdy w max_reads odczytach
    (domyslnie 6 * n_frames) nie udalo sie zebrac serii.
    """
    if max_reads is None:
        max_reads = 6 * n_frames
    history: deque = deque(maxlen=n_frames)
    for _ in range(max_reads):
        try:
            frame, _depth = cam.read()
        except EOFError:
            break
        dets = detector.detect(frame)
        if dets:
            history.append((dets[0].px, dets[0].py))
        else:
            history.clear()
        if len(history) >= n_frames:
            arr = np.array(history)
            return (float(arr[:, 0].mean()), float(arr[:, 1].mean()),
                    float(arr[:, 0].std()), float(arr[:, 1].std()), len(history))
    return None


def apply_measurement(cfg: Config, avg_px: float, avg_py: float,
                      grasp_name: str | None, set_cx: bool) -> list[str]:
    """Wpisz pomiar do configu (bez zapisu na dysk). Zwraca opisy zmian."""
    changes: list[str] = []
    if grasp_name:
        names = [g.name for g in cfg.grasps]
        if grasp_name not in names:
            raise SystemExit(f"Nie ma chwytu {grasp_name!r}; sa: {names}")
        g = cfg.grasps[names.index(grasp_name)]
        g.target_row = round(avg_py, 1)
        changes.append(f"{g.name}.target_row = {g.target_row:.1f}")
    if set_cx:
        cfg.cx = round(avg_px, 1)
        changes.append(f"cx = {cfg.cx:.1f}")
    return changes


def run_headless(args, cfg: Config, cfg_path: str) -> int:
    if args.write and not (args.grasp or args.set_cx):
        raise SystemExit("--write wymaga --grasp NAME i/lub --set-cx (co zapisac?).")
    detector = HsvConeDetector(cfg.detector)
    cam = make_camera(cfg, args.source)
    try:
        print(f"headless: zbieram {args.frames} kolejnych klatek z detekcja...")
        res = collect_average(cam, detector, args.frames)
    finally:
        cam.close()
    if res is None:
        print("Brak stabilnej detekcji (szyszka nie w kadrze albo prog HSV nie pasuje). Nic nie zapisano.")
        return 1
    avg_px, avg_py, std_px, std_py, n = res
    print(f"srednia z {n} klatek: px={avg_px:.1f} py={avg_py:.1f}  (std {std_px:.1f}/{std_py:.1f})")
    print(f"config teraz: cx={cfg.cx:.1f} "
          + " ".join(f"{g.name}={g.target_row:.1f}" for g in cfg.grasps))
    if not args.write:
        print("Bez --write: nic nie zapisano. Dodaj --grasp NAME --write i/lub --set-cx --write.")
        return 0
    changes = apply_measurement(cfg, avg_px, avg_py, args.grasp, args.set_cx)
    path = cfg.save(cfg_path)
    print(f"Zapisano {path}: " + ", ".join(changes))
    return 0


def main() -> None:
    args = parse_args()
    cfg_path = args.config or Config.default_path()
    cfg = Config.load(cfg_path)
    if not cfg.grasps:
        raise SystemExit("Brak chwytow w konfiguracji - nie ma czego kalibrowac.")

    selected = 0
    if args.grasp:
        names = [g.name for g in cfg.grasps]
        if args.grasp not in names:
            raise SystemExit(f"Nie ma chwytu {args.grasp!r}; sa: {names}")
        selected = names.index(args.grasp)

    if args.headless:
        raise SystemExit(run_headless(args, cfg, cfg_path))

    print_instructions(cfg, cfg_path)

    detector = HsvConeDetector(cfg.detector)
    cam = make_camera(cfg, args.source)
    is_file = isinstance(cam, FileCamera)
    wait_ms = int(1000 / FILE_FPS) if is_file else 1

    history: deque = deque(maxlen=AVG_FRAMES)
    dirty = False
    last_print = 0.0
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            frame, _ = cam.read()
            dets = detector.detect(frame)
            h, w = frame.shape[:2]

            if dets:
                history.append((dets[0].px, dets[0].py))
            else:
                history.clear()  # zgubiona szyszka = srednia od nowa, nie mieszaj klatek
            avg = None
            if history:
                arr = np.array(history)
                avg = (float(arr[:, 0].mean()), float(arr[:, 1].mean()))
                spread = (float(arr[:, 0].std()), float(arr[:, 1].std()))

            g = cfg.grasps[selected]
            text = f"[{selected + 1}] {g.name} row={g.target_row:.0f} cx={cfg.cx:.0f}"
            if avg is not None:
                text += f"  avg({len(history)})=({avg[0]:.1f},{avg[1]:.1f})"
            if dirty:
                text += "  *niezapisane (w)*"
            vis = HsvConeDetector.draw_debug(frame, dets, cx=cfg.cx, text=text)

            # Linie target_row kazdego chwytu z nazwa; wybrany grubsza.
            for i, gg in enumerate(cfg.grasps):
                color = GRASP_COLORS[i % len(GRASP_COLORS)]
                y = int(round(gg.target_row))
                thick = 2 if i == selected else 1
                cv2.line(vis, (0, y), (w, y), color, thick)
                cv2.putText(vis, f"{i + 1}:{gg.name} {gg.target_row:.0f}", (w - 230, max(12, y - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
            if avg is not None:
                cv2.drawMarker(vis, (int(avg[0]), int(avg[1])), (255, 0, 255),
                               cv2.MARKER_CROSS, 16, 1)
            cv2.imshow(WINDOW, vis)

            now = time.monotonic()
            if avg is not None and now - last_print >= PRINT_EVERY_S:
                last_print = now
                print(f"  {g.name}: srednia z {len(history)} klatek "
                      f"px={avg[0]:.1f} py={avg[1]:.1f}  (std {spread[0]:.1f}/{spread[1]:.1f}) "
                      f"| teraz px={dets[0].px:.1f} py={dets[0].py:.1f}")

            key = cv2.waitKey(wait_ms) & 0xFF
            if key in (ord("q"), 27):
                if dirty:
                    print("UWAGA: niezapisane zmiany (w zapisuje). Wychodze bez zapisu.")
                break
            if ord("1") <= key <= ord("9"):
                idx = key - ord("1")
                if idx < len(cfg.grasps):
                    selected = idx
                    print(f"Wybrany chwyt: [{idx + 1}] {cfg.grasps[idx].name}")
            elif key == ord("s"):
                if avg is None:
                    print("Brak detekcji - nie ma czego zapisac.")
                else:
                    g.target_row = round(avg[1], 1)
                    dirty = True
                    print(f"{g.name}.target_row = {g.target_row:.1f} "
                          f"(srednia z {len(history)} klatek, px bylo {avg[0]:.1f})")
            elif key == ord("c"):
                if avg is None:
                    print("Brak detekcji - nie ma czego zapisac.")
                else:
                    cfg.cx = round(avg[0], 1)
                    dirty = True
                    print(f"cx = {cfg.cx:.1f} (srednia z {len(history)} klatek)")
            elif key == ord("w"):
                path = cfg.save(cfg_path)
                dirty = False
                print(f"Zapisano {path}: cx={cfg.cx:.1f}, "
                      + ", ".join(f"{gg.name}={gg.target_row:.1f}" for gg in cfg.grasps))
    except KeyboardInterrupt:
        print("\nPrzerwano.")
    finally:
        cam.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

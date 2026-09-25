"""Eksport nagrania RealSense (.db3 / .bag) do zestawu RGB-D dla RTAB-Map.

Po co to jest
------------
RTAB-Map (wersja desktop na Windows) nie otworzy naszego nagrania bezposrednio,
a `rs.align(rs.stream.color)` na tym pliku zwraca PUSTA glebie, bo w bagu
zapisane sa zdegenerowane ekstrinsyki (macierz obrotu depth->color to
[1,0,0,0,0,0,0,0,0], a `get_depth_scale()` z playbacku zwraca 0.0).

Dlatego rejestracje glebia->kolor robimy sami, na parametrach odczytanych
wprost z topicow bagu:

  /device_0/sensor_0/Depth_0/camera_info   intrinsyki glebi
  /device_0/sensor_1/Color_0/camera_info   intrinsyki koloru
  /device_0/sensor_1/Color_0/tf/ref_0      poza koloru wzgledem glebi
  /device_0/sensor_0/Depth_0/image/metadata  depth_units (0.001 m)

Wynik (domyslnie obok pliku wejsciowego, katalog `<nazwa>_rtabmap/`):

  rgb/000001.jpg      obraz kolorowy (JPEG, tak samo jak RTAB-Map trzyma u siebie)
  depth/000001.png    glebia 16-bit w mm, ZAREJESTROWANA do obrazu kolorowego
  calib/rs_color.yaml kalibracja w formacie OpenCV/RTAB-Map
  stamps.txt          znaczniki czasu w sekundach, jeden na klatke
  README_rtabmap.txt  jak z tego zrobic mape (CLI RTAB-Map)

Uzycie
------
  python bag_to_rtabmap.py NAGRANIE.db3 [-o KATALOG] [--step N] [--max N]
  python bag_to_rtabmap.py NAGRANIE.db3 --probe      # tylko metadane, bez eksportu
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import struct
import sys
import time

import cv2
import numpy as np
import pyrealsense2 as rs

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover
    zstd = None


# --------------------------------------------------------------------------
# czytanie metadanych prosto z sqlite (omijamy zepsute API playbacku)
# --------------------------------------------------------------------------

def _topic_first_message(db_path: str, topic: str) -> str | None:
    """Pierwsza wiadomosc danego topicu, rozpakowana i zdekodowana do stringa."""
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    try:
        row = con.execute(
            "SELECT m.data FROM messages m JOIN topics t ON t.id = m.topic_id "
            "WHERE t.name = ? LIMIT 1", (topic,)).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    blob = row[0]
    if blob[:4] == b"\x28\xb5\x2f\xfd":  # magic zstd
        if zstd is None:
            raise RuntimeError("wiadomosci sa spakowane zstd - zainstaluj: pip install zstandard")
        blob = zstd.ZstdDecompressor().decompress(blob, max_output_size=1 << 22)
    # CDR: 4 bajty naglowka enkapsulacji, potem uint32 dlugosc + bajty
    n = struct.unpack_from("<I", blob, 4)[0]
    return blob[8:8 + n].rstrip(b"\x00").decode("utf-8", "replace")


def _parse_kv(text: str) -> dict:
    out = {}
    for part in text.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class Intr:
    def __init__(self, kv: dict):
        self.width = int(kv["width"])
        self.height = int(kv["height"])
        self.fx = float(kv["fx"])
        self.fy = float(kv["fy"])
        self.cx = float(kv["ppx"])
        self.cy = float(kv["ppy"])

    def __repr__(self):
        return "%dx%d fx=%.3f fy=%.3f cx=%.3f cy=%.3f" % (
            self.width, self.height, self.fx, self.fy, self.cx, self.cy)


def read_bag_calibration(db_path: str):
    """Zwraca (intr_depth, intr_color, R_color_from_ref, t_color_in_ref, depth_units)."""
    depth_ci = _topic_first_message(db_path, "/device_0/sensor_0/Depth_0/camera_info")
    color_ci = _topic_first_message(db_path, "/device_0/sensor_1/Color_0/camera_info")
    color_tf = _topic_first_message(db_path, "/device_0/sensor_1/Color_0/tf/ref_0")
    meta = _topic_first_message(db_path, "/device_0/sensor_0/Depth_0/image/metadata")
    if not (depth_ci and color_ci and color_tf):
        raise RuntimeError("brak topicow kalibracyjnych - czy to na pewno bag RealSense?")

    di, ci = Intr(_parse_kv(depth_ci)), Intr(_parse_kv(color_ci))
    tf = _parse_kv(color_tf)
    R = np.array([float(x) for x in tf["rotation"].split(",")], dtype=np.float64).reshape(3, 3)
    t = np.array([float(x) for x in tf["translation"].split(",")], dtype=np.float64)

    units = 0.001
    if meta:
        units = float(_parse_kv(meta).get("depth_units", 0.001))
    return di, ci, R, t, units


# --------------------------------------------------------------------------
# rejestracja glebia -> kolor
# --------------------------------------------------------------------------

class DepthRegistrar:
    """Przerzuca obraz glebi do ukladu kamery kolorowej (forward warp + z-bufor).

    librealsense zapisuje `tf/ref_0` jako poze strumienia WZGLEDEM referencji
    (referencja = glebia, jej wlasne tf to identycznosc). Zatem punkt z ukladu
    glebi trafia do ukladu koloru przez P_c = R^T (P_d - t).
    """

    def __init__(self, di: Intr, ci: Intr, R: np.ndarray, t: np.ndarray, units: float):
        self.di, self.ci, self.units = di, ci, units
        self.Rt = R.T.astype(np.float32)
        self.t = t.astype(np.float32)
        u, v = np.meshgrid(np.arange(di.width, dtype=np.float32),
                           np.arange(di.height, dtype=np.float32))
        self.xn = ((u - di.cx) / di.fx).ravel()
        self.yn = ((v - di.cy) / di.fy).ravel()

    def __call__(self, depth_raw: np.ndarray) -> np.ndarray:
        z = depth_raw.ravel().astype(np.float32) * self.units
        m = z > 0
        if not m.any():
            return np.zeros((self.ci.height, self.ci.width), np.uint16)
        z = z[m]
        P = np.stack([self.xn[m] * z, self.yn[m] * z, z], axis=1) - self.t
        Pc = P @ self.Rt.T

        zc = Pc[:, 2]
        good = zc > 0
        Pc, zc = Pc[good], zc[good]
        uu = self.ci.fx * (Pc[:, 0] / zc) + self.ci.cx
        vv = self.ci.fy * (Pc[:, 1] / zc) + self.ci.cy

        mm = np.rint(zc * 1000.0).astype(np.int32)
        np.clip(mm, 1, 65534, out=mm)

        H, W = self.ci.height, self.ci.width
        buf = np.full(H * W, 65535, dtype=np.int32)
        ui, vi = np.rint(uu).astype(np.int32), np.rint(vv).astype(np.int32)
        # splat 2x2: intrinsyki glebi i koloru roznia sie skala, przez co czysty
        # warp 1:1 zostawia siatke jednopikselowych dziur
        for du in (0, 1):
            for dv in (0, 1):
                x, y = ui + du, vi + dv
                ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
                np.minimum.at(buf, y[ok] * W + x[ok], mm[ok])
        buf[buf == 65535] = 0
        return buf.astype(np.uint16).reshape(H, W)


# --------------------------------------------------------------------------
# kalibracja w formacie RTAB-Map
# --------------------------------------------------------------------------

CALIB_TEMPLATE = """%YAML:1.0
---
camera_name: {name}
image_width: {w}
image_height: {h}
camera_matrix: !!opencv-matrix
   rows: 3
   cols: 3
   dt: d
   data: [ {fx:.6f}, 0., {cx:.6f}, 0., {fy:.6f}, {cy:.6f}, 0., 0., 1. ]
distortion_coefficients: !!opencv-matrix
   rows: 1
   cols: 5
   dt: d
   data: [ 0., 0., 0., 0., 0. ]
distortion_model: plumb_bob
rectification_matrix: !!opencv-matrix
   rows: 3
   cols: 3
   dt: d
   data: [ 1., 0., 0., 0., 1., 0., 0., 0., 1. ]
projection_matrix: !!opencv-matrix
   rows: 3
   cols: 4
   dt: d
   data: [ {fx:.6f}, 0., {cx:.6f}, 0., 0., {fy:.6f}, {cy:.6f}, 0., 0., 0., 1., 0. ]
"""


def write_rtabmap_calibration(path: str, name: str, ci: Intr) -> None:
    # recznie, nie przez cv2.FileStorage: OpenCV 5 pisze naglowek "%YAML 1.2",
    # a RTAB-Map (OpenCV 4) oczekuje "%YAML:1.0"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(CALIB_TEMPLATE.format(name=name, w=ci.width, h=ci.height,
                                      fx=ci.fx, fy=ci.fy, cx=ci.cx, cy=ci.cy))


README = """Zestaw RGB-D dla RTAB-Map
========================

{n} par kolor+glebia, {dur:.1f} s, {hz:.1f} Hz, 1280x720. Glebia jest ZAREJESTROWANA
do obrazu kolorowego, wiec RTAB-Map traktuje to jak zwykla kamere RGB-D.

  rgb:   {rgb}
  depth: {depth}
  calib: {calib}

Mapowanie bez GUI (RTAB-Map 0.23.8 win64, sprawdzone 2026-09-25):
  1. rtabmap-dataRecorder -hide rtabmap_source.ini raw.db
     ini: [Camera] type=0, rgbd\\driver=7, calibrationName=<calib>,
          RGBDImages\\path_rgb / path_depth, RGBDImages\\scale=1,
          Images\\stamps=stamps.txt
  2. rtabmap-reprocess -odom --RGBD/LinearUpdate 0 --RGBD/AngularUpdate 0
       --Odom/ResetCountdown 1 --Vis/MinInliers 12 --Vis/CorType 1
       --Vis/MaxFeatures 2000 raw.db map.db
  3. rtabmap-detectMoreLoopClosures --inter -r 100 -a 180 -i 3 map.db
  4. rtabmap-export --cloud --poses --voxel 0.01 map.db

Pulapki: kinect20.dll w paczce RTAB-Map chce msvcr110/msvcp110 (VC++ 2012) -
bez nich kazde narzedzie pada z 0xC0000135. rtabmap-rgbd_dataset ma na sztywno
kalibracje TUM (640x480), do tego zestawu sie nie nadaje.
Szczegoly: PROGRESS.md w repo pawel120/hackaton.
"""


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bag", help="plik .db3 / .bag z RealSense")
    ap.add_argument("-o", "--out", default=None, help="katalog wyjsciowy")
    ap.add_argument("--step", type=int, default=1,
                    help="zapisuj co N-ta klatke (1 = wszystkie, 30 Hz)")
    ap.add_argument("--max", type=int, default=0, help="zatrzymaj sie po N klatkach (0 = bez limitu)")
    ap.add_argument("--jpeg-quality", type=int, default=95)
    ap.add_argument("--probe", action="store_true", help="wypisz kalibracje i wyjdz")
    ap.add_argument("--resume", action="store_true",
                    help="dokoncz przerwany eksport (te same --step), pomijajac gotowe klatki")
    args = ap.parse_args()

    if not os.path.isfile(args.bag):
        print("nie ma pliku:", args.bag)
        return 2

    di, ci, R, t, units = read_bag_calibration(args.bag)
    print("glebia  :", di)
    print("kolor   :", ci)
    print("depth->color translacja (m):", np.round(t, 6).tolist())
    print("depth_units:", units)
    if args.probe:
        return 0

    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.bag)),
        os.path.splitext(os.path.basename(args.bag))[0] + "_rtabmap")
    rgb_dir, depth_dir, calib_dir = (os.path.join(out, d) for d in ("rgb", "depth", "calib"))
    for d in (rgb_dir, depth_dir, calib_dir):
        os.makedirs(d, exist_ok=True)

    calib_path = os.path.join(calib_dir, "rs_color.yaml")
    write_rtabmap_calibration(calib_path, "rs_color", ci)

    reg = DepthRegistrar(di, ci, R, t, units)

    resume_from = 0
    if args.resume:
        done = min(len(os.listdir(rgb_dir)), len(os.listdir(depth_dir)))
        resume_from = done  # ostatnia gotowa klatka zostanie zapisana jeszcze raz
        print("wznawiam: %d klatek juz jest, licze od %d" % (done, resume_from))

    cfg = rs.config()
    cfg.enable_device_from_file(args.bag, repeat_playback=False)
    pipe = rs.pipeline()
    prof = pipe.start(cfg)
    playback = prof.get_device().as_playback()
    playback.set_real_time(False)  # bez tego gubi klatki
    duration = playback.get_duration().total_seconds()
    print("dlugosc nagrania: %.2f s" % duration)

    stamps, kept, seen, t0 = [], 0, 0, time.time()
    last_color_no = None
    first_stamp = None
    try:
        while True:
            ok, fs = pipe.try_wait_for_frames(5000)
            if not ok:
                # timeout to NIE to samo co koniec pliku - przy zajetym dysku odczyt
                # potrafi stanac na kilka sekund (tak uciety byl pierwszy --resume)
                if playback.current_status() == rs.playback_status.stopped:
                    break
                continue
            c, d = fs.get_color_frame(), fs.get_depth_frame()
            if not c or not d:
                continue
            # playback bez real-time potrafi oddac TE SAMA klatke koloru z nowa
            # glebia (w tym nagraniu 714 z 2611) - taka para jest rozsynchronizowana
            if c.get_frame_number() == last_color_no:
                continue
            last_color_no = c.get_frame_number()
            seen += 1
            if (seen - 1) % args.step:
                continue

            stamp = c.get_timestamp() / 1000.0  # ms -> s
            if first_stamp is None:
                first_stamp = stamp

            kept += 1
            base = "%06d" % kept
            rgb_path = os.path.join(rgb_dir, base + ".jpg")
            depth_path = os.path.join(depth_dir, base + ".png")
            stamps.append(stamp)
            # wznawianie przerwanego eksportu: gotowych klatek nie liczymy od nowa
            # (ostatnia moze byc ucieta, wiec jej nie ufamy - patrz --resume)
            if args.resume and kept < resume_from and os.path.exists(rgb_path) \
                    and os.path.exists(depth_path):
                if kept == resume_from // 2:
                    # kontrola: czy liczymy klatki tak samo jak poprzedni przebieg
                    fresh = cv2.cvtColor(np.asanyarray(c.get_data()), cv2.COLOR_RGB2BGR)
                    diff = float(np.abs(cv2.imread(rgb_path).astype(np.int16)
                                        - fresh.astype(np.int16)).mean())
                    print("kontrola wznowienia, klatka %d: sredni blad %.2f" % (kept, diff),
                          flush=True)
                    if diff > 4.0:  # sam JPEG q95 daje ~1
                        raise RuntimeError("numeracja klatek sie rozjechala - usun katalog "
                                           "i eksportuj od zera, bez --resume")
                continue

            color = cv2.cvtColor(np.asanyarray(c.get_data()), cv2.COLOR_RGB2BGR)
            depth = reg(np.asanyarray(d.get_data()))
            cv2.imwrite(rgb_path, color, [cv2.IMWRITE_JPEG_QUALITY, args.jpeg_quality])
            cv2.imwrite(depth_path, depth)

            if kept % 50 == 0:
                el = time.time() - t0
                print("  %5d klatek  %6.1f s  (%.1f klatek/s)" % (kept, el, kept / el),
                      flush=True)
            if args.max and kept >= args.max:
                break
    finally:
        pipe.stop()

    with open(os.path.join(out, "stamps.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join("%.6f" % s for s in stamps) + "\n")

    span = (stamps[-1] - stamps[0]) if len(stamps) > 1 else 0.0
    with open(os.path.join(out, "README_rtabmap.txt"), "w", encoding="utf-8") as f:
        f.write(README.format(rgb=rgb_dir, depth=depth_dir, calib=calib_path,
                              n=kept, dur=span, hz=(kept / span if span else 0.0)))

    el = time.time() - t0
    print("gotowe: %d klatek z %d odczytanych, %.1f s, katalog %s" % (kept, seen, el, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

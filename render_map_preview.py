"""Podglad mapy RTAB-Map bez open3d: rzut chmury .ply z gory + widok z ukosa.

  python render_map_preview.py chmura.ply [poses.txt] -o podglad.png

Uklad RTAB-Map: x do przodu, y w lewo, z do gory. Widok z gory to plaszczyzna x-y,
kolor punktu z kamery, jasnosc przyciemniona z wysokoscia (latwiej czytac sciany).
"""

from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

PLY_TYPES = {"float": "f4", "float32": "f4", "double": "f8", "uchar": "u1", "uint8": "u1",
             "char": "i1", "int8": "i1", "ushort": "u2", "uint16": "u2", "short": "i2",
             "int16": "i2", "uint": "u4", "uint32": "u4", "int": "i4", "int32": "i4"}


def read_ply(path: str):
    with open(path, "rb") as f:
        header, props, n, in_vertex = [], [], 0, False
        while True:
            line = f.readline().decode("ascii", "replace").strip()
            header.append(line)
            if line.startswith("element"):
                # PCL dopisuje po vertex jeszcze element "camera" z wlasnymi property
                in_vertex = line.startswith("element vertex")
                if in_vertex:
                    n = int(line.split()[-1])
            elif line.startswith("property") and in_vertex and not line.startswith("property list"):
                _, typ, name = line.split()
                props.append((name, PLY_TYPES[typ]))
            elif line == "end_header":
                break
        fmt = next(h for h in header if h.startswith("format"))
        if "ascii" in fmt:
            data = np.loadtxt(f, max_rows=n)
            arr = {name: data[:, i] for i, (name, _) in enumerate(props)}
        else:
            endian = "<" if "little" in fmt else ">"
            dt = np.dtype([(name, endian + t) for name, t in props])
            arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt, count=n)
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1).astype(np.float32)
    names = arr.dtype.names if hasattr(arr, "dtype") else tuple(arr)
    if "red" in names:
        rgb = np.stack([arr["red"], arr["green"], arr["blue"]], 1).astype(np.uint8)
    else:
        rgb = np.full((len(xyz), 3), 200, np.uint8)
    return xyz, rgb


def read_poses(path: str | None):
    """Format RTAB-Map 'raw' (12 liczb = macierz 3x4) albo TUM (stamp x y z qx qy qz qw)."""
    if not path:
        return None
    rows = [l.split() for l in open(path) if l.strip() and not l.startswith("#")]
    if not rows:
        return None
    vals = np.array([[float(v) for v in r] for r in rows])
    if vals.shape[1] == 12:
        return vals[:, [3, 7, 11]]
    if vals.shape[1] >= 8:
        return vals[:, 1:4]
    return None


def fit_floor(xyz, iters=400, tol=0.015, seed=0):
    """RANSAC: plaszczyzna z najwieksza liczba punktow, z normalna mniej wiecej 'do gory'.

    Odrzucamy plaszczyzny odchylone od osi z o >60 st., bo sciana z duza liczba punktow
    potrafi wygrac z podloga.
    """
    rng = np.random.default_rng(seed)
    sub = xyz[rng.choice(len(xyz), min(len(xyz), 60000), replace=False)]
    best, best_n = None, -1
    for _ in range(iters):
        p = sub[rng.choice(len(sub), 3, replace=False)]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n /= norm
        if abs(n[2]) < 0.5:
            continue
        cnt = int((np.abs((sub - p[0]) @ n) < tol).sum())
        if cnt > best_n:
            best, best_n = (n, p[0]), cnt
    n, p0 = best
    # dopracowanie: SVD na inlierach
    inl = sub[np.abs((sub - p0) @ n) < tol]
    c = inl.mean(0)
    n = np.linalg.svd(inl - c)[2][-1]
    if n[2] < 0:
        n = -n
    return n, c


def level_to_floor(xyz, poses):
    n, c = fit_floor(xyz)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(n, z)
    s, cth = np.linalg.norm(v), float(n @ z)
    if s < 1e-9:
        R = np.eye(3)
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx * ((1 - cth) / s ** 2)  # Rodrigues: n -> z
    xyz = xyz @ R.T
    floor_z = float((R @ c)[2])
    cam_h = float(-floor_z)  # kamera w 1. klatce jest w (0,0,0)
    if poses is not None:
        poses = poses @ R.T
    return xyz, poses, floor_z, cam_h


def splat(u, v, col, depth, W, H):
    """Rysuje punkty z z-buforem (depth mniejsze = blizej widza)."""
    img = np.full((H, W, 3), 245, np.uint8)
    ok = (u >= 0) & (u < W) & (v >= 0) & (v < H)
    u, v, col, depth = u[ok], v[ok], col[ok], depth[ok]
    order = np.argsort(-depth)  # najdalsze najpierw, najblizsze nadpisuja
    img[v[order], u[order]] = col[order][:, ::-1]  # RGB -> BGR
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ply")
    ap.add_argument("poses", nargs="?")
    ap.add_argument("-o", "--out", default="map_preview.png")
    ap.add_argument("--px", type=int, default=1100, help="szerokosc kazdego widoku")
    ap.add_argument("--title", default="")
    a = ap.parse_args()

    xyz, rgb = read_ply(a.ply)
    poses = read_poses(a.poses)
    lo, hi = np.percentile(xyz, 1, 0), np.percentile(xyz, 99, 0)
    keep = np.all((xyz >= lo - 0.2) & (xyz <= hi + 0.2), 1)  # odrzuc pojedyncze odlatujace punkty
    xyz, rgb = xyz[keep], rgb[keep]
    print("punkty: %d  zakres x %.2f..%.2f  y %.2f..%.2f  z %.2f..%.2f m" % (
        len(xyz), *np.ravel(np.stack([xyz.min(0), xyz.max(0)], 1))))

    # --- podloga: RANSAC, potem obrot tak, zeby byla pozioma ---
    # RTAB-Map bierze za "poziom" orientacje kamery w PIERWSZEJ klatce; jak kamera byla
    # pochylona, cala mapa jest przechylona i podloga nie lezy w z = const
    xyz, poses, floor_z, cam_h = level_to_floor(xyz, poses)
    print("podloga po wypoziomowaniu: z=%.3f m; kamera w 1. klatce %.3f m nad podloga" % (floor_z, cam_h))
    above = xyz[:, 2] - floor_z
    obst = above > 0.05
    print("podloga z=%.3f m, punkty ponad podloga: %.0f%%" % (floor_z, 100 * obst.mean()))
    hcol = cv2.applyColorMap(np.clip(above / 1.2 * 255, 0, 255).astype(np.uint8).reshape(-1, 1),
                             cv2.COLORMAP_TURBO).reshape(-1, 3)[:, ::-1]  # BGR -> RGB
    top_rgb = np.where(obst[:, None], hcol, np.array([[205, 205, 205]], np.uint8))

    # --- widok z gory (x w prawo, y do gory obrazka) ---
    W = a.px
    span = max(np.ptp(xyz[:, 0]), np.ptp(xyz[:, 1])) + 0.2
    s = (W - 40) / span
    cx, cy = xyz[:, 0].mean(), xyz[:, 1].mean()
    H = int(np.ptp(xyz[:, 1]) * s) + 80
    H = max(H, 300)
    u = ((xyz[:, 0] - cx) * s + W / 2).astype(int)
    v = (H / 2 - (xyz[:, 1] - cy) * s).astype(int)
    top = splat(u, v, top_rgb, -xyz[:, 2], W, H)  # najwyzsze punkty na wierzchu
    if poses is not None and len(poses):
        pu = ((poses[:, 0] - cx) * s + W / 2).astype(int)
        pv = (H / 2 - (poses[:, 1] - cy) * s).astype(int)
        cv2.polylines(top, [np.stack([pu, pv], 1).reshape(-1, 1, 2)], False, (0, 0, 220), 2,
                      cv2.LINE_AA)
        cv2.circle(top, (int(pu[0]), int(pv[0])), 7, (0, 170, 0), -1)
        cv2.circle(top, (int(pu[-1]), int(pv[-1])), 7, (0, 0, 220), -1)
    # podzialka 1 m
    cv2.line(top, (20, H - 20), (20 + int(s), H - 20), (0, 0, 0), 3)
    cv2.putText(top, "1 m", (20, H - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.putText(top, "widok z gory" + (" - " + a.title if a.title else ""), (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(top, "szare = podloga, kolor = wysokosc nad podloga (niebieski nisko, czerwony ~1.2 m)",
                (20, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)

    # --- widok z ukosa (obrot 35 st. wokol z, pochylenie 55 st.) ---
    P = xyz - xyz.mean(0)
    yaw, pitch = np.radians(-35), np.radians(55)
    Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]])
    Q = P @ Rz.T @ Rx.T
    span2 = max(np.ptp(Q[:, 0]), np.ptp(Q[:, 1])) + 0.2
    s2 = (W - 40) / span2
    H2 = max(int(np.ptp(Q[:, 1]) * s2) + 80, 300)
    u2 = (Q[:, 0] * s2 + W / 2).astype(int)
    v2 = (H2 / 2 - Q[:, 1] * s2).astype(int)
    iso = splat(u2, v2, rgb, Q[:, 2] * -1, W, H2)
    cv2.putText(iso, "widok z ukosa", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    out = np.vstack([top, np.full((6, W, 3), 180, np.uint8), iso])
    cv2.imwrite(a.out, out)
    print("zapisano", a.out, out.shape)
    return 0


if __name__ == "__main__":
    sys.exit(main())

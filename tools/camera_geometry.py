"""
Kalkulator do budowy masztu kamery: gdzie ustawic D415, zeby miejsce chwytu bylo w kadrze
i poza martwa strefa glebi, i w ktorym wierszu obrazu wyladuje szyszka dla kazdego chwytu.

Ta sama geometria co w pinecone_bot/sim.py (SimWorld.project): kamera na wysokosci h nad ziemia,
cam_forward_m przed srodkiem osi kol (ujemne = za osia), pochylona o pitch w dol.

Przyklady:
  python tools/camera_geometry.py                         # tabela wysokosc x kat dla chwytow z configu
  python tools/camera_geometry.py --height 0.45 --pitch 38  # szczegoly jednego montazu
  python tools/camera_geometry.py --grasp-forward 0.30,0.35,0.40 --cam-forward -0.10
  python tools/camera_geometry.py --fx 462 --fy 617       # ogniskowe z RealSenseCamera.intrinsics na Pi

Odleglosci 'do przodu' liczone sa od srodka osi kol (tak jak forward_m w configu). Punkt chwytu
mierzysz miarka: srodek szczek chwytaka przy nagranym chwycie wzgledem osi kol.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pinecone_bot.config import Config  # noqa: E402

# D415, strumien koloru 640x480: HFOV ok. 69 st, VFOV ok. 42 st -> fx ~ 462 px, fy ~ 617 px.
# Na Pi odczytaj prawdziwe z RealSenseCamera(cfg).intrinsics i podaj --fx/--fy.
D415_FX_640 = 462.0
D415_FY_480 = 617.0
# martwa strefa glebi D415 (min-Z) zalezy od rozdzielczosci strumienia GLEBI
MIN_Z_DEPTH = {"424x240": 0.16, "640x480": 0.31, "848x480": 0.31, "1280x720": 0.45}


def project(dx: float, dy: float, h: float, pitch_deg: float, cam_forward: float,
            fx: float, fy: float, w: int, hgt: int):
    """Punkt na ziemi (dx do przodu, dy w lewo, od osi kol) -> (px, py, z_cam) albo None za kamera."""
    p = math.radians(pitch_deg)
    dxc = dx - cam_forward
    z_c = dxc * math.cos(p) + h * math.sin(p)
    if z_c <= 0.05:
        return None
    y_c = -dxc * math.sin(p) + h * math.cos(p)
    x_c = -dy
    return w / 2 + fx * x_c / z_c, hgt / 2 + fy * y_c / z_c, z_c


def ground_distance_at_row(py: float, h: float, pitch_deg: float, cam_forward: float,
                           fy: float, hgt: int) -> float | None:
    """Odwrotnosc project() dla dy=0: ktora odleglosc do przodu lezy w wierszu py. None = nad horyzontem."""
    p = math.radians(pitch_deg)
    yn = (py - hgt / 2) / fy
    denom = yn * math.cos(p) + math.sin(p)
    if denom <= 1e-9:
        return None  # promien nie trafia w ziemie (patrzy w horyzont albo wyzej)
    dxc = h * (math.cos(p) - yn * math.sin(p)) / denom
    return dxc + cam_forward


def analyze(h: float, pitch_deg: float, cam_forward: float, fx: float, fy: float, w: int, hgt: int,
            grasp_forward: list[float], depth_mode: str = "424x240", margin_px: float = 20.0) -> dict:
    far = ground_distance_at_row(0, h, pitch_deg, cam_forward, fy, hgt)
    near = ground_distance_at_row(hgt, h, pitch_deg, cam_forward, fy, hgt)
    min_z = MIN_Z_DEPTH.get(depth_mode, 0.31)
    grasps = []
    ok_all = True
    for g in grasp_forward:
        pr = project(g, 0.0, h, pitch_deg, cam_forward, fx, fy, w, hgt)
        if pr is None:
            grasps.append({"forward_m": g, "row": None, "z_cam": None, "in_frame": False, "depth_ok": False})
            ok_all = False
            continue
        px, py, z = pr
        in_frame = margin_px <= py <= hgt - margin_px
        depth_ok = z >= min_z
        half_width = z * (w / 2) / fx
        grasps.append({"forward_m": g, "row": py, "z_cam": z, "in_frame": in_frame, "depth_ok": depth_ok,
                       "half_width_m": half_width})
        ok_all = ok_all and in_frame and depth_ok
    # rozdzielczosc pionowa przy punkcie chwytu: ile cm na piksel (blad target_row -> blad pozycji)
    cm_per_px = None
    if grasps and grasps[0]["row"] is not None:
        r = grasps[0]["row"]
        d1 = ground_distance_at_row(r, h, pitch_deg, cam_forward, fy, hgt)
        d2 = ground_distance_at_row(r - 1, h, pitch_deg, cam_forward, fy, hgt)
        if d1 is not None and d2 is not None:
            cm_per_px = abs(d2 - d1) * 100
    return {"height": h, "pitch": pitch_deg, "near_m": near, "far_m": far, "min_z": min_z,
            "grasps": grasps, "ok": ok_all, "cm_per_px": cm_per_px}


def fmt_m(v) -> str:
    if v is None:
        return "  brak"
    if v > 9:
        return "   >9m"
    return f"{v:6.2f}"


def print_table(cam_forward, fx, fy, w, hgt, grasp_forward, depth_mode, heights, pitches):
    print(f"Kamera {cam_forward:+.2f} m od osi kol, obraz {w}x{hgt}, fx={fx:.0f} fy={fy:.0f}, "
          f"glebia {depth_mode} (min-Z {MIN_Z_DEPTH.get(depth_mode, 0.31):.2f} m)")
    print(f"Punkty chwytu (do przodu od osi kol): {', '.join(f'{g:.2f}' for g in grasp_forward)} m")
    print("Komorka: OK = wszystkie chwyty w kadrze (margines 20 px) i dalej niz min-Z; "
          "'kadr' = poza kadrem; 'glebia' = za blisko dla glebi; liczba = zasieg widocznej ziemi [m]")
    print()
    print("wys\\kat " + "".join(f"{p:>14.0f}" for p in pitches))
    for h in heights:
        row = f"{h:5.2f} m "
        for p in pitches:
            a = analyze(h, p, cam_forward, fx, fy, w, hgt, grasp_forward, depth_mode)
            if a["ok"]:
                tag = "OK"
            elif any(not g["in_frame"] for g in a["grasps"]):
                tag = "kadr"
            else:
                tag = "glebia"
            near = a["near_m"]
            far = a["far_m"]
            rng = f"{near:.2f}-{far:.2f}" if (near is not None and far is not None) else (f"{near:.2f}-inf" if near is not None else "?")
            row += f"{tag:>6s} {rng:>7s}"
        print(row)
    print()
    print("Wybierz komorke OK z najwiekszym zasiegiem, ale nie patrzacym w horyzont (far = inf oznacza,"
          " ze gorny rzad obrazu jest nad ziemia: strata pikseli na niebo).")


def print_detail(a: dict, hgt: int):
    print(f"Wysokosc {a['height']:.2f} m, pochylenie {a['pitch']:.0f} st w dol")
    print(f"  widoczna ziemia: od {fmt_m(a['near_m']).strip()} m (dol kadru) do {fmt_m(a['far_m']).strip()} m (gora kadru)")
    print(f"  martwa strefa glebi: {a['min_z']:.2f} m od obiektywu")
    if a["cm_per_px"] is not None:
        print(f"  przy punkcie chwytu 1 piksel w pionie = {a['cm_per_px']:.2f} cm "
              f"(tolerancja tol_y_px=8 -> ok. {8 * a['cm_per_px']:.1f} cm)")
    for g in a["grasps"]:
        if g["row"] is None:
            print(f"  chwyt {g['forward_m']:.2f} m: ZA KAMERA / poza kadrem")
            continue
        flag = "OK" if (g["in_frame"] and g["depth_ok"]) else ("POZA KADREM" if not g["in_frame"] else "ZA BLISKO DLA GLEBI")
        print(f"  chwyt {g['forward_m']:.2f} m: wiersz {g['row']:.0f} (z {hgt}), odleglosc od obiektywu "
              f"{g['z_cam']:.2f} m, szerokosc kadru tam +-{g['half_width_m']:.2f} m  -> {flag}")
    print("  " + ("MONTAZ OK" if a["ok"] else "ZMIEN wysokosc lub kat"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=None)
    p.add_argument("--height", type=float, default=None, help="wysokosc obiektywu nad ziemia [m]; bez -> tabela")
    p.add_argument("--pitch", type=float, default=None, help="pochylenie w dol [st]; bez -> tabela")
    p.add_argument("--cam-forward", type=float, default=None, help="kamera przed (+) / za (-) osia kol [m]")
    p.add_argument("--grasp-forward", default=None, help="odleglosci punktow chwytu od osi kol, np. 0.30,0.35,0.40")
    p.add_argument("--fx", type=float, default=D415_FX_640)
    p.add_argument("--fy", type=float, default=D415_FY_480)
    p.add_argument("--depth-mode", default="424x240", choices=sorted(MIN_Z_DEPTH))
    p.add_argument("--heights", default="0.30,0.35,0.40,0.45,0.50,0.55,0.60")
    p.add_argument("--pitches", default="25,30,35,40,45,50,55")
    args = p.parse_args(argv)

    cfg = Config.load(args.config) if args.config else Config.load()
    w, hgt = cfg.image_w, cfg.image_h
    cam_forward = cfg.sim.cam_forward_m if args.cam_forward is None else args.cam_forward
    if args.grasp_forward:
        grasp_forward = [float(x) for x in args.grasp_forward.split(",")]
    else:
        grasp_forward = [g.forward_m for g in cfg.grasps if g.forward_m > 0] or [0.30, 0.35, 0.40]
    if args.height is not None and args.pitch is not None:
        a = analyze(args.height, args.pitch, cam_forward, args.fx, args.fy, w, hgt, grasp_forward, args.depth_mode)
        print_detail(a, hgt)
        return 0 if a["ok"] else 1
    heights = [float(x) for x in args.heights.split(",")]
    pitches = [float(x) for x in args.pitches.split(",")]
    print_table(cam_forward, args.fx, args.fy, w, hgt, grasp_forward, args.depth_mode, heights, pitches)
    return 0


if __name__ == "__main__":
    sys.exit(main())

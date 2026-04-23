#!/usr/bin/env python3
"""
Genera avatares 49–79 al estilo de 1–48: círculo de color + motivos simples
(figuras, símbolos, sin caras de retrato).
"""
from __future__ import annotations

import math
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "static", "avatars")

BGS = [
    "#3b82f6", "#ec4899", "#f97316", "#22c55e", "#8b5cf6", "#14b8a6",
    "#e11d48", "#0ea5e9", "#a855f7", "#d97706", "#4f46e5", "#059669",
    "#db2777", "#2563eb", "#65a30d", "#7c3aed", "#0d9488", "#c026d3",
    "#ca8a04", "#dc2626", "#1d4ed8", "#15803d", "#be185d", "#0369a1",
    "#6d28d9", "#b45309", "#0f766e", "#9333ea", "#1e40af", "#9f1239", "#0e7490",
]
WHITE = "#ffffff"


def _star(cx: float, cy: float, r: float, n: int, rot: float) -> str:
    pts = []
    for k in range(n * 2):
        ang = rot + (k * math.pi / n) - math.pi / 2
        rad = r if k % 2 == 0 else r * 0.45
        pts.append(f"{cx + rad * math.cos(ang):.2f},{cy + rad * math.sin(ang):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{WHITE}"/>'


def build(n: int) -> str:
    i = n - 49
    bg = BGS[i % len(BGS)]
    kind = i % 31
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    base = f'<circle cx="50" cy="50" r="50" fill="{bg}"/>'
    w = WHITE

    if kind == 0:
        body = _star(50, 48, 28, 5, 0.2) + f'<circle cx="50" cy="52" r="7" fill="{bg}"/>'
    elif kind == 1:
        body = f'<path d="M50 18 L80 50 L50 85 L20 50 Z" fill="{w}"/>'
    elif kind == 2:
        body = f'<rect x="22" y="22" width="56" height="56" rx="10" fill="{w}"/>'
        body += f'<rect x="35" y="35" width="30" height="30" rx="4" fill="{bg}"/>'
    elif kind == 3:
        body = f'<path d="M20 60 Q50 20 80 60 L80 80 L20 80 Z" fill="{w}"/>'
    elif kind == 4:
        body = f'<rect x="18" y="40" width="20" height="12" rx="3" fill="{w}"/>'
        body += f'<rect x="40" y="40" width="20" height="12" rx="3" fill="{w}"/>'
        body += f'<rect x="62" y="40" width="20" height="12" rx="3" fill="{w}"/>'
    elif kind == 5:
        body = f'<rect x="28" y="28" width="44" height="44" fill="none" stroke="{w}" stroke-width="4"/>'
        body += f'<line x1="28" y1="50" x2="72" y2="50" stroke="{w}" stroke-width="3"/>'
    elif kind == 6:
        body = f'<path d="M25 70 L50 25 L75 70 Z" fill="{w}"/>'
        body += f'<rect x="44" y="42" width="12" height="28" fill="{bg}"/>'
    elif kind == 7:
        body = f'<path d="M32 50 L45 32 L55 32 L68 50 L50 75 Z" fill="{w}"/>'
    elif kind == 8:
        body = f'<rect x="26" y="36" width="48" height="36" rx="4" fill="{w}"/>'
        body += f'<polygon points="40,32 50,20 60,32" fill="{w}"/>'
    elif kind == 9:
        body = f'<ellipse cx="50" cy="50" rx="34" ry="18" fill="{w}"/>'
        body += f'<line x1="18" y1="50" x2="82" y2="50" stroke="{bg}" stroke-width="3"/>'
    elif kind == 10:
        body = f'<path d="M20 50 Q50 10 80 50 Q50 90 20 50" fill="{w}"/>'
    elif kind == 11:
        body = _star(50, 45, 20, 6, 0) + f'<circle cx="50" cy="50" r="5" fill="{bg}"/>'
    elif kind == 12:
        body = f'<path d="M22 32 L60 20 L75 50 L48 80 L18 55 Z" fill="{w}"/>'
    elif kind == 13:
        body = f'<circle cx="50" cy="42" r="20" fill="none" stroke="{w}" stroke-width="5"/>'
        body += f'<rect x="40" y="60" width="20" height="12" rx="2" fill="{w}"/>'
    elif kind == 14:
        body = ""
        for j in range(3):
            body += f'<rect x="{24 + j * 25}" y="40" width="12" height="24" rx="2" fill="{w}"/>'
    elif kind == 15:
        body = f'<path d="M25 25 H75 V48 H25 Z" fill="{w}"/>'
        body += f'<path d="M25 52 H75 V75 H25 Z" fill="{w}" opacity="0.7"/>'
    elif kind == 16:
        body = f'<polygon points="50,20 80,50 50,80 20,50" fill="{w}"/>'
    elif kind == 17:
        body = f'<circle cx="50" cy="50" r="3" fill="{w}"/>'
        body += f'<line x1="50" y1="50" x2="50" y2="22" stroke="{w}" stroke-width="3"/>'
        body += f'<line x1="50" y1="50" x2="70" y2="56" stroke="{w}" stroke-width="2.5"/>'
        body += f'<line x1="50" y1="50" x2="32" y2="68" stroke="{w}" stroke-width="2.5"/>'
    elif kind == 18:
        body = f'<rect x="30" y="28" width="40" height="48" fill="{w}"/>'
        body += f'<line x1="30" y1="45" x2="70" y2="45" stroke="{bg}" stroke-width="2.5"/>'
    elif kind == 19:
        body = f'<path d="M50 12 L64 50 L50 40 L36 50 Z" fill="{w}"/>'
        body += f'<rect x="32" y="50" width="36" height="36" fill="{w}"/>'
    elif kind == 20:
        body = f'<ellipse cx="50" cy="40" rx="32" ry="12" fill="{w}"/>'
        body += f'<rect x="45" y="48" width="10" height="32" fill="{w}"/>'
    elif kind == 21:
        body = f'<path d="M18 78 L32 25 L50 50 L68 25 L82 78 Z" fill="{w}"/>'
    elif kind == 22:
        body = f'<circle cx="50" cy="32" r="7" fill="{w}"/>'
        body += f'<line x1="50" y1="40" x2="50" y2="78" stroke="{w}" stroke-width="4"/>'
        body += f'<line x1="28" y1="56" x2="72" y2="56" stroke="{w}" stroke-width="3"/>'
    elif kind == 23:
        body = f'<path d="M25 50 A25 25 0 0 1 75 50" fill="none" stroke="{w}" stroke-width="6"/>'
        body += f'<line x1="50" y1="25" x2="50" y2="58" stroke="{w}" stroke-width="4"/>'
    elif kind == 24:
        body = f'<rect x="20" y="20" width="24" height="24" fill="{w}"/>'
        body += f'<rect x="56" y="20" width="24" height="24" fill="{w}" opacity="0.6"/>'
        body += f'<rect x="38" y="56" width="24" height="24" fill="{w}"/>'
    elif kind == 25:
        body = f'<rect x="28" y="28" width="44" height="44" fill="none" stroke="{w}" stroke-width="5"/>'
        body += f'<line x1="36" y1="50" x2="64" y2="50" stroke="{w}" stroke-width="3"/>'
        body += f'<line x1="50" y1="36" x2="50" y2="64" stroke="{w}" stroke-width="3"/>'
    elif kind == 26:
        body = f'<polygon points="50,16 90,50 50,84 10,50" fill="{w}"/>'
        body += f'<circle cx="50" cy="50" r="10" fill="{bg}"/>'
    elif kind == 27:
        body = ""
        for a in (0, 60, 120, 180, 240, 300):
            body += f'<rect x="48" y="18" width="4" height="16" fill="{w}" transform="rotate({a} 50 50)"/>'
    elif kind == 28:
        body = f'<path d="M22 42 Q50 12 78 42 L78 78 L22 78 Z" fill="{w}"/>'
    elif kind == 29:
        body = f'<path d="M30 50 H70 M50 30 V70" stroke="{w}" stroke-width="6" stroke-linecap="round"/>'
        body += f'<circle cx="50" cy="50" r="4" fill="{w}"/>'
    else:
        body = f'<rect x="24" y="24" width="52" height="52" fill="none" stroke="{w}" stroke-width="4" rx="8"/>'
        body += f'<path d="M34 50 L45 60 L65 38" fill="none" stroke="{w}" stroke-width="4"/>'

    return head + base + body + "</svg>\n"


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for n in range(49, 80):
        path = os.path.join(OUT, f"{n}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build(n))
        print("wrote", path)


if __name__ == "__main__":
    main()

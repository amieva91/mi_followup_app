#!/usr/bin/env python3
"""Genera avatares SVG 49-79: retratos estilizados (tonos piel, pelo, ojos)."""
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "static", "avatars")
# Paletas: piel, pelo, ojos, accento
SKIN = [
    ("#e8b89a", "#c97b63", "#2d1f1a"), ("#d4a574", "#a67c52", "#1a1a1a"), ("#b8836f", "#8a5a44", "#0f0f0f"),
    ("#f0c8a8", "#d4a08c", "#3d2914"), ("#9c6b4a", "#6b4423", "#0d0d0d"), ("#c6866b", "#8f5e4a", "#1f1410"),
    ("#e5b99a", "#b87d66", "#252018"), ("#8d5524", "#5a3518", "#0a0a0a"), ("#d9a48c", "#a87058", "#221a16"),
    ("#7d4c32", "#4a2a1a", "#050505"), ("#f2c4a8", "#d9a88a", "#3a2a22"), ("#6b3e2c", "#3d2418", "#000"),
]
HAIR = [
    ("#1a0f0a", "M8 12 Q20 4 50 6 Q80 4 92 12 L100 0 L0 0 Z"),
    ("#2c1810", "M0 8 Q30 0 50 2 Q70 0 100 8 L100 0 L0 0 Z"),
    ("#0f172a", "M2 10 Q25 2 50 4 Q75 2 98 10 L100 0 L0 0 Z"),
    ("#3f2e1a", "M0 6 Q50 -2 100 6 L100 0 L0 0 Z"),
    ("#1e1b1a", "M0 5 Q20 0 50 0 Q80 0 100 5 L100 0 L0 0 Z"),
    ("#4a3728", "M5 12 Q30 1 50 2 Q70 1 95 12 L100 0 L0 0 Z"),
    ("#0d1117", "M0 4 Q25 -1 50 0 Q75 -1 100 4 L100 0 L0 0 Z"),
    ("#2d1f14", "M0 7 Q25 0 50 0 Q75 0 100 7 L100 0 L0 0 Z"),
    ("#1c1917", "M0 3 Q15 0 50 0 Q85 0 100 3 L100 0 L0 0 Z"),
    ("#422006", "M0 9 Q20 0 50 0 Q80 0 100 9 L100 0 L0 0 Z"),
    ("#0c0a09", "M0 5 Q20 -2 50 0 Q80 -2 100 5 L100 0 L0 0 Z"),
    ("#292524", "M0 4 Q20 0 50 0 Q80 0 100 4 L100 0 L0 0 Z"),
    ("#1e1b4b", "M0 6 Q20 0 50 0 Q80 0 100 6 L100 0 L0 0 Z"),
    ("#1c1917", "M0 2 Q20 -3 50 -2 Q80 -3 100 2 L100 0 L0 0 Z"),
    ("#1a1a1a", "M0 8 Q20 0 50 0 Q80 0 100 8 L100 0 L0 0 Z"),
    ("#3f1d0c", "M0 5 Q20 0 50 0 Q80 0 100 5 L100 0 L0 0 Z"),
    ("#18181b", "M0 3 Q20 0 50 0 Q80 0 100 3 L100 0 L0 0 Z"),
    ("#1e293b", "M0 4 Q20 0 50 0 Q80 0 100 4 L100 0 L0 0 Z"),
    ("#292524", "M0 6 Q20 0 50 0 Q80 0 100 6 L100 0 L0 0 Z"),
    ("#1c1008", "M0 4 Q20 -1 50 0 Q80 -1 100 4 L100 0 L0 0 Z"),
    ("#1c1917", "M0 2 Q20 0 50 0 Q80 0 100 2 L100 0 L0 0 Z"),
    ("#0a0a0a", "M0 3 Q20 0 50 0 Q80 0 100 3 L100 0 L0 0 Z"),
    ("#27272a", "M0 3 Q20 0 50 0 Q80 0 100 3 L100 0 L0 0 Z"),
    ("#422006", "M0 5 Q20 0 50 0 Q80 0 100 5 L100 0 L0 0 Z"),
    ("#1a1a1a", "M0 2 Q20 0 50 0 Q80 0 100 2 L100 0 L0 0 Z"),
    ("#2d1b0c", "M0 4 Q20 0 50 0 Q80 0 100 4 L100 0 L0 0 Z"),
    ("#18181b", "M0 1 Q20 0 50 0 Q80 0 100 1 L100 0 L0 0 Z"),
    ("#1e1b1a", "M0 3 Q20 0 50 0 Q80 0 100 3 L100 0 L0 0 Z"),
    ("#0c0a09", "M0 2 Q20 0 50 0 Q80 0 100 2 L100 0 L0 0 Z"),
    ("#3f1d0c", "M0 4 Q20 0 50 0 Q80 0 100 4 L100 0 L0 0 Z"),
    ("#0f172a", "M0 2 Q20 0 50 0 Q80 0 100 2 L100 0 L0 0 Z"),
]

def make_svg(n: int) -> str:
    si = n % len(SKIN)
    hi = n % len(HAIR)
    face_fill, face_shadow, eye_col = SKIN[si]
    hair_fill, hair_path = HAIR[hi]
    # variación ojos
    ex1, ex2 = 36 + (n % 5), 64 - (n % 4)
    eye_r = 4 + (n % 2)
    mouth_y = 68 + (n % 3)
    smile = f"M32 {mouth_y} Q50 {mouth_y+10} 68 {mouth_y}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<defs>
  <radialGradient id="g{n}" cx="50%" cy="40%" r="60%">
    <stop offset="0%" stop-color="{face_fill}"/>
    <stop offset="100%" stop-color="{face_shadow}"/>
  </radialGradient>
</defs>
<circle cx="50" cy="50" r="50" fill="#0f172a"/>
<path d="{hair_path}" fill="{hair_fill}" transform="translate(0,2)"/>
<ellipse cx="50" cy="54" rx="32" ry="36" fill="url(#g{n})"/>
<ellipse cx="{ex1}" cy="48" rx="{eye_r}" ry="{5}" fill="#ffffff" opacity="0.95"/>
<ellipse cx="{ex2}" cy="48" rx="{eye_r}" ry="{5}" fill="#ffffff" opacity="0.95"/>
<circle cx="{ex1-1}" cy="48" r="{2}" fill="{eye_col}"/>
<circle cx="{ex2+1}" cy="48" r="{2}" fill="{eye_col}"/>
<path d="{smile}" stroke="#5c4033" stroke-width="2.2" fill="none" stroke-linecap="round" opacity="0.85"/>
<ellipse cx="50" cy="60" rx="10" ry="4" fill="#b91c1c" opacity="0.12"/>
</svg>'''


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in range(49, 80):
        path = os.path.join(OUT, f"{n}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(make_svg(n))
        print("wrote", path)


if __name__ == "__main__":
    main()

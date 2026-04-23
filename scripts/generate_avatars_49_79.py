#!/usr/bin/env python3
"""Genera avatares abstractos 49–79 (sin retratos): formas geométricas, paleta teal/slate."""
from __future__ import annotations

import os

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "static", "avatars")

PALETTES: list[tuple[str, str, str]] = [
    ("#0d9488", "#0f172a", "#5eead4"),
    ("#3f5f73", "#1e293b", "#94a3b8"),
    ("#0e7490", "#0c4a6e", "#22d3ee"),
    ("#4f46e5", "#1e1b4b", "#a5b4fc"),
    ("#0f766e", "#134e4a", "#2dd4bf"),
    ("#475569", "#0f172a", "#cbd5e1"),
    ("#155e75", "#164e63", "#a5f3fc"),
    ("#0f766e", "#1c1917", "#34d399"),
    ("#0369a1", "#0c4a6e", "#7dd3fc"),
    ("#4c1d95", "#312e81", "#c4b5fd"),
    ("#115e59", "#0f172a", "#5eead4"),
    ("#1e3a5f", "#0f172a", "#93c5fd"),
]


def _rng(i: int) -> int:
    s = (i * 1103515245 + 12345) & 0x7FFFFFFF
    return s


def _pick(i: int, mod: int) -> int:
    return _rng(i) % mod


def build_svg(n: int) -> str:
    c1, c2, c3 = PALETTES[(n - 49) % len(PALETTES)]
    r = n * 7 + 13
    a1 = n * 19 % 360
    a2 = n * 23 % 360
    s1 = 0.6 + (n % 7) * 0.05
    pat = n % 7

    head = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<defs>
  <linearGradient id="bg{n}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{c1}"/>
    <stop offset="100%" stop-color="{c2}"/>
  </linearGradient>
  <linearGradient id="ac{n}" x1="0" y1="1" x2="1" y2="0">
    <stop offset="0%" stop-color="{c3}" stop-opacity="0.85"/>
    <stop offset="100%" stop-color="{c1}" stop-opacity="0.25"/>
  </linearGradient>
</defs>
<rect width="100" height="100" rx="20" fill="url(#bg{n})"/>"""

    if pat == 0:
        body = f"""
<circle cx="50" cy="50" r="38" fill="none" stroke="url(#ac{n})" stroke-width="3" stroke-dasharray="6 8" transform="rotate({a1} 50 50)"/>
<circle cx="50" cy="50" r="24" fill="none" stroke="{c3}" stroke-width="2.5" opacity="0.5" transform="rotate({-a2} 50 50)"/>
<circle cx="50" cy="50" r="8" fill="url(#ac{n})" opacity="0.9"/>
"""
    elif pat == 1:
        body = f"""
<polygon points="50,8 92,75 8,75" fill="url(#ac{n})" opacity="0.4" transform="rotate({a1} 50 50)"/>
<polygon points="50,20 80,80 20,80" fill="{c3}" opacity="0.35" transform="rotate({-a2} 50 50) scale(0.85) translate(0,2)"/>
<rect x="32" y="32" width="36" height="36" rx="6" fill="none" stroke="{c3}" stroke-width="2" transform="rotate({a1} 50 50)"/>
"""
    elif pat == 2:
        d = 10 + _pick(n, 15)
        body = f"""
<path d="M0,{50+d/2} Q25,{20+d%5} 50,{50} T100,{50-d/2} L100,100 L0,100 Z" fill="url(#ac{n})" opacity="0.5"/>
<path d="M0,78 Q{30+r%20},{60+_pick(n,10)} 100,72 L100,100 L0,100 Z" fill="{c2}" opacity="0.45"/>
<circle cx="70" cy="32" r="{6+n%4}" fill="{c3}" opacity="0.5"/>
<circle cx="28" cy="40" r="{5+n%3}" fill="{c3}" opacity="0.35"/>
"""
    elif pat == 3:
        body = f"""
<g transform="translate(50 50) rotate({a1})">
  <rect x="-35" y="-18" width="70" height="10" rx="3" fill="url(#ac{n})" opacity="0.8"/>
  <rect x="-28" y="-2" width="56" height="8" rx="2" fill="{c3}" opacity="0.45" transform="rotate(45)"/>
  <rect x="-20" y="14" width="40" height="7" rx="2" fill="{c3}" opacity="0.35" transform="rotate(-25)"/>
</g>"""
    elif pat == 4:
        body = f"""
<path d="M12 50 L32 20 L50 50 L68 20 L88 50 L75 90 L25 90 Z" fill="url(#ac{n})" opacity="0.5"/>
<circle cx="50" cy="38" r="4" fill="{c3}"/>
<rect x="38" y="55" width="24" height="18" rx="3" fill="{c2}" opacity="0.4"/>
"""
    elif pat == 5:
        w = 12 + n % 8
        body = f"""
<g opacity="0.7">
  <line x1="15" y1="20" x2="85" y2="20" stroke="url(#ac{n})" stroke-width="{w%5+2}" stroke-linecap="round"/>
  <line x1="20" y1="45" x2="90" y2="50" stroke="{c3}" stroke-width="3" stroke-linecap="round" transform="rotate({a1%30-15} 50 45)"/>
  <line x1="10" y1="70" x2="80" y2="75" stroke="url(#ac{n})" stroke-width="2" stroke-linecap="round"/>
</g>
<circle cx="50" cy="50" r="3" fill="{c3}"/>
"""
    else:
        x0, y0 = 20 + _pick(n, 20), 18 + _pick(n, 15)
        body = f"""
<rect x="18" y="22" width="64" height="58" rx="4" fill="none" stroke="url(#ac{n})" stroke-width="2.5" transform="rotate({a1%24-12} 50 50)"/>
<circle cx="{x0}" cy="{y0}" r="6" fill="{c3}"/>
<circle cx="{100-x0-8}" cy="{y0+5}" r="5" fill="{c3}" opacity="0.6"/>
<path d="M30 80 Q50 65 70 80" stroke="url(#ac{n})" stroke-width="3" fill="none" stroke-linecap="round"/>
"""
    tail = "</svg>\n"
    return head + body + tail


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for n in range(49, 80):
        path = os.path.join(OUT, f"{n}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_svg(n))
        print("wrote", path)


if __name__ == "__main__":
    main()

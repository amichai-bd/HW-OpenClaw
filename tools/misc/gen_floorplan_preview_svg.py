#!/usr/bin/env python3
"""Generate a human-visible SVG preview from a DEF floorplan (die + cells + IO pins).

Pins and labels use sizes scaled to the die (DBU / DEF distance units), so markers
stay visible on large designs.

**Important:** Early floorplan DEFs often list every cell as ``UNPLACED`` - the preview
then shows only the die and IO pins. Pass a *placed* or *routed* DEF (for example
``*_placed.def``) to see standard-cell placement density.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


def def_to_svg(def_path: Path, out_path: Path, title: str) -> tuple[int, int]:
    text = def_path.read_text(encoding="utf-8")
    m = re.search(
        r"DIEAREA\s*\(\s*(\d+)\s+(\d+)\s*\)\s*\(\s*(\d+)\s+(\d+)\s*\)\s*;",
        text,
    )
    if not m:
        out_path.write_text(
            "<?xml version='1.0' encoding='UTF-8'?>\n"
            f"<!-- no DIEAREA in {def_path} -->\n",
            encoding="utf-8",
        )
        return (0, 0)

    x0, y0, x1, y1 = (int(m.group(i)) for i in range(1, 5))
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    mmin = min(w, h)

    # Sizes in the same coordinate system as DEF (microns / DBU) - must be large
    # relative to the die or nothing shows up at 900px viewport scale.
    stroke = max(200, mmin // 400)
    r_pin = max(int(mmin * 0.012), 800)
    fs_title = max(int(mmin * 0.045), 2000)
    fs_pin = max(int(mmin * 0.022), 1200)
    title_text = html.escape(title, quote=False)

    pins: list[tuple[str, int, int, str]] = []
    for block in re.finditer(
        r"-\s+(\S+)\s+\+\s+NET\s+\S+.*?\+\s+PLACED\s*\(\s*(\d+)\s+(\d+)\s*\)\s+(\S+)\s*;",
        text,
        flags=re.DOTALL,
    ):
        pins.append(
            (
                block.group(1),
                int(block.group(2)),
                int(block.group(3)),
                block.group(4),
            )
        )

    # Standard-cell / macro instances (COMPONENTS to END COMPONENTS), only + PLACED / + FIXED.
    cells: list[tuple[int, int]] = []
    comp = re.search(
        r"COMPONENTS\s+\d+\s*;(.*?)^END\s+COMPONENTS\s*;?\s*$",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    if comp:
        body = comp.group(1)
        for m in re.finditer(
            r"\+ (?:PLACED|FIXED)\s*\(\s*(\d+)\s+(\d+)\s*\)\s+\S+\s*;",
            body,
        ):
            cells.append((int(m.group(1)), int(m.group(2))))

    def sy(y: int) -> int:
        return y1 - (y - y0)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {w} {h}" width="900" height="900">',
        f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#f5f5f5" stroke="#222" stroke-width="{stroke}"/>',
        f'<text x="{x0 + w // 2}" y="{y0 + fs_title + stroke * 2}" text-anchor="middle" '
        f'font-size="{fs_title}" fill="#111">{title_text} - {len(cells)} placed cells, {len(pins)} pins '
        f"(DEF units)</text>",
    ]

    r_cell = max(int(mmin * 0.0035), 120)
    sw_cell = max(40, stroke // 4)
    for cx, py in cells:
        cy = sy(py)
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_cell}" fill="#bdbdbd" stroke="#616161" '
            f'stroke-width="{sw_cell}"/>'
        )

    for name, px, py, _ori in pins:
        cy = sy(py)
        name_text = html.escape(name, quote=False)
        lines.append(
            f'<circle cx="{px}" cy="{cy}" r="{r_pin}" fill="#1565c0" stroke="#0d47a1" '
            f'stroke-width="{max(100, stroke // 2)}"/>'
        )
        lines.append(
            f'<text x="{px + r_pin * 2}" y="{cy}" dominant-baseline="middle" '
            f'font-size="{fs_pin}" fill="#000">{name_text}</text>'
        )
    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return (len(pins), len(cells))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("def_file", type=Path)
    p.add_argument("out_svg", type=Path)
    p.add_argument("title", nargs="?", default="floorplan")
    args = p.parse_args()
    pins_n, cells_n = def_to_svg(args.def_file, args.out_svg, args.title)
    print(
        f"wrote {args.out_svg} ({pins_n} pins, {cells_n} placed cells)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

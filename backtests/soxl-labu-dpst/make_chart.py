"""Draw the README chart: growth of $1 on SOXL over the 5-year test, buy & hold vs the three dip rules.

Input:  data/soxl-labu-dpst/results_5y.json (run analyze.py first)
Output: docs/images/soxl-growth-5y.svg
Run from the repo root:  python3 backtests/soxl-labu-dpst/make_chart.py
Uses only the Python standard library.
"""
import json
import math
import pathlib
from xml.sax.saxutils import escape

SRC = pathlib.Path("data/soxl-labu-dpst/results_5y.json")
OUT = pathlib.Path("docs/images/soxl-growth-5y.svg")
SERIES = [  # (results key, label, color)
    ("Buy & hold", "Buy & hold", "#8b9198"),
    ("RSI(2)<10 -> exit above 5-day avg or day 10", "RSI(2) dip", "#2a78d6"),
    ("Close below lower Bollinger -> exit above 20-day avg", "Bollinger dip", "#eb6834"),
    ("3 down days -> exit first up day", "3 down days", "#1baf7a"),
]
W, H = 760, 400
L, R, T, B = 56, 150, 44, 34
INK, MUTED, GRID = "#1f2a33", "#5f6b75", "#e2e6e9"


def main(src=SRC, out_path=OUT):
    bt = json.loads(src.read_text())["funds"]["SOXL"]["backtests"]
    dates = [d for d, _ in bt[SERIES[0][0]]["curve"]]
    lines = [(label, color, [v for _, v in bt[key]["curve"]]) for key, label, color in SERIES]
    lo = math.log(min(min(v) for _, _, v in lines) * 0.9)
    hi = math.log(max(max(v) for _, _, v in lines) * 1.1)
    x = lambda i: L + (W - L - R) * i / (len(dates) - 1)
    y = lambda v: T + (H - T - B) * (1 - (math.log(v) - lo) / (hi - lo))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="-apple-system, Segoe UI, Helvetica, Arial, sans-serif" role="img" '
           f'aria-label="Growth of 1 dollar on SOXL, Oct 2021 to Oct 2026: buy and hold versus three dip-buying rules, log scale">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="{L}" y="22" font-size="15" font-weight="700" fill="{INK}">SOXL: growth of $1, Oct 7, 2021 to Oct 6, 2026</text>',
           f'<text x="{L}" y="37" font-size="11.5" fill="{MUTED}">log scale · after 0.05% cost per side · trades at the close</text>']
    for v in [0.1, 0.2, 0.5, 1, 2, 5, 10]:
        if math.exp(lo) <= v <= math.exp(hi):
            out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{"#b9c1c7" if v == 1 else GRID}" stroke-width="1"/>')
            out.append(f'<text x="{L - 8}" y="{y(v) + 4:.1f}" font-size="11" fill="{MUTED}" text-anchor="end">${v:g}</text>')
    for yr in range(2022, 2027):
        i = next((k for k, d in enumerate(dates) if d >= f"{yr}-10-07"), None)
        if i is not None:
            out.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{T}" y2="{H - B}" stroke="{GRID}" stroke-width="1"/>')
            out.append(f'<text x="{x(i):.1f}" y="{H - 12}" font-size="11" fill="{MUTED}" text-anchor="middle">Oct {yr}</text>')
    out.append(f'<text x="{L}" y="{H - 12}" font-size="11" fill="{MUTED}">Oct 2021</text>')
    for label, color, vals in lines:
        d = "".join(("M" if i == 0 else "L") + f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    # end labels, nudged apart and joined to their line ends
    ends = sorted(((y(vals[-1]), label, color, vals[-1]) for label, color, vals in lines))
    placed = []
    for ye, label, color, v in ends:
        ly = max(ye, placed[-1][0] + 16) if placed else ye
        placed.append((ly, ye, label, color, v))
    xe = x(len(dates) - 1)
    for ly, ye, label, color, v in placed:
        out.append(f'<path d="M{xe + 5:.1f},{ye:.1f}L{xe + 13:.1f},{ly:.1f}" stroke="#b9c1c7" fill="none"/>')
        out.append(f'<circle cx="{xe:.1f}" cy="{ye:.1f}" r="4" fill="{color}" stroke="#ffffff" stroke-width="2"/>')
        out.append(f'<text x="{xe + 16:.1f}" y="{ly + 4:.1f}" font-size="12" fill="{INK}">{escape(label)} ${v:.2f}</text>')
    out.append("</svg>")
    out_path.write_text("\n".join(out) + "\n")
    print("saved", out_path)


if __name__ == "__main__":
    main()

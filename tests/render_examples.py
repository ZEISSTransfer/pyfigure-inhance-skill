"""Create isolated synthetic visual fixtures; never reads competition data."""
import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
from figure_style import PALETTES, CMAPS, paper_style, palette_colors, palette_cmap, save_figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    root = parser.parse_args().output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    records = []

    def save(fig, name, layout="tight"):
        result = save_figure(fig, name, project_root=root, extra_formats=("svg",), layout=layout)
        records.append({"name": name, "paths": [str(p) for p in result.paths],
                        "warnings": result.warnings})

    # Explicitly synthetic data, identical across the before/after example.
    x, y = [1, 2, 3, 4, 5], [8, 12, 10, 17, 15]
    with paper_style(project_root=root):
        fig, ax = plt.subplots()
        ax.plot(x, y, marker="o", label="Series A")
        ax.plot(x, [6, 8, 11, 12, 14], marker="s", linestyle="--", label="Series B")
        ax.set(xlabel="Time / day", ylabel="Output / unit")
        ax.legend()
        save(fig, "01_line.pdf")
        for candidate in PALETTES:
            for line, legend_line, color in zip(ax.lines, ax.get_legend().get_lines(), palette_colors(candidate)):
                line.set_color(color)
                legend_line.set_color(color)
            save(fig, f"01_line__palette-{candidate}.pdf", layout="preserve")
        plt.close(fig)

        fig, ax = plt.subplots()
        ax.barh(["Baseline", "Candidate A", "Candidate B"], [12, 18, 15])
        ax.set(xlabel="Output / unit")
        save(fig, "02_bar.pdf")
        plt.close(fig)

        fig, ax = plt.subplots()
        ax.plot(x, y, marker="o")
        ax.set(xlabel="Time / day", ylabel="Output / unit")
        label = fig.text(0.96, 0.20, "Source: saved simulation results")
        save(fig, "03_clipped.pdf")
        label.set_position((0.6, 0.20))
        label.set_ha("center")
        save(fig, "04_repaired.pdf")
        plt.close(fig)

    labels = "时间 偏差 系列甲 Time day Output unit Series 2026 −1"
    try:
        with paper_style(project_root=root, required_text=labels) as font:
            fig, ax = plt.subplots()
            ax.plot(x, [-3, -1, 0, 2, 1], marker="o", label="系列甲 Series A")
            ax.set(xlabel="时间 Time / day", ylabel="偏差 Output / unit")
            ax.legend()
            save(fig, "05_chinese.pdf")
            records[-1]["font"] = font
            plt.close(fig)
    except RuntimeError as exc:
        records.append({"name": "05_chinese.pdf", "not_rendered": str(exc)})
    with paper_style(project_root=root):
        for kind, candidates in CMAPS.items():
            fig, ax = plt.subplots()
            values = [[0, 2, 5], [1, 3, 4]] if kind == "sequential" else [[-3, 0, 5], [-2, 1, 4]]
            norm = matplotlib.colors.Normalize(0, 5) if kind == "sequential" else matplotlib.colors.TwoSlopeNorm(0, -3, 5)
            mesh = ax.pcolormesh(values, cmap=palette_cmap(kind, project_root=root), norm=norm)
            ax.set(xlabel="Sample", ylabel="Condition", xticks=[0.5, 1.5, 2.5],
                   xticklabels=["A", "B", "C"], yticks=[0.5, 1.5], yticklabels=["I", "II"])
            colorbar = fig.colorbar(mesh, ax=ax, label="Output / unit")
            for index, candidate in enumerate(candidates):
                mesh.set_cmap(palette_cmap(kind, candidate, project_root=root))
                # Changing the cmap rebuilds colorbar solids; set this afterwards.
                colorbar.solids.set_rasterized(False)
                colorbar.solids.set_edgecolor("face")
                save(fig, f"06_{kind}__palette-{candidate}.pdf", layout="tight" if index == 0 else "preserve")
            plt.close(fig)
    (root / "manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

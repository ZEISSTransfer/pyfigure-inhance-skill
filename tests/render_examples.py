"""Create isolated synthetic visual fixtures; never reads competition data."""
import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
from figure_style import paper_style, save_figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    root = parser.parse_args().output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    records = []

    def save(fig, name):
        result = save_figure(fig, name, project_root=root, extra_formats=("svg",))
        records.append({"name": name, "paths": [str(p) for p in result.paths],
                        "warnings": result.warnings})

    # Explicitly synthetic data, identical across the before/after example.
    x, y = [1, 2, 3, 4, 5], [8, 12, 10, 17, 15]
    with paper_style():
        fig, ax = plt.subplots()
        ax.plot(x, y, marker="o", label="Series A")
        ax.plot(x, [6, 8, 11, 12, 14], marker="s", linestyle="--", label="Series B")
        ax.set(title="Synthetic example: time trend", xlabel="Time / day", ylabel="Output / unit")
        ax.legend()
        save(fig, "01_line.pdf")
        plt.close(fig)

        fig, ax = plt.subplots()
        ax.barh(["Baseline", "Candidate A", "Candidate B"], [12, 18, 15])
        ax.set(title="Synthetic example: category comparison", xlabel="Output / unit")
        save(fig, "02_bar.pdf")
        plt.close(fig)

        fig, ax = plt.subplots()
        ax.plot(x, y, marker="o")
        ax.set(xlabel="Time / day", ylabel="Output / unit")
        label = fig.text(0.96, 0.96, "Synthetic example: clipped heading")
        save(fig, "03_clipped.pdf")
        label.set_position((0.5, 0.96))
        label.set_ha("center")
        save(fig, "04_repaired.pdf")
        plt.close(fig)

    labels = "合成示例：中文与负号 时间天 偏差单位 系列甲"
    try:
        with paper_style(required_text=labels) as font:
            fig, ax = plt.subplots()
            ax.plot(x, [-3, -1, 0, 2, 1], marker="o", label="系列甲")
            ax.set(title="合成示例：中文与负号", xlabel="时间 / 天", ylabel="偏差 / 单位")
            ax.legend()
            save(fig, "05_chinese.pdf")
            records[-1]["font"] = font
            plt.close(fig)
    except RuntimeError as exc:
        records.append({"name": "05_chinese.pdf", "not_rendered": str(exc)})
    (root / "manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

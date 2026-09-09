"""Maintainer integration samples, NOT a blind Agent/model first-plot test.

Provide the saved Q2 grid CSV, Q3 Monte Carlo CSV and baseline summary explicitly.
Only reads inputs. Output directory must be new. The third chart is synthetic.
No old figure or renderer is imported; no fitting or analysis file is written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
from figure_style import (paper_style, palette_cmap, palette_colors, role_style,
                          annotation_color, add_right_colorbar, outside_legend,
                          prepare_figure, save_figure)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--q2-csv", type=Path, required=True)
    parser.add_argument("--q3-csv", type=Path, required=True)
    parser.add_argument("--q3-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [p.resolve(strict=True) for p in (args.q2_csv, args.q3_csv, args.q3_summary)]
    hashes = {str(p): digest(p) for p in inputs}
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    records = []

    def export(fig, ax, name, notes, cb=None, legend=None):
        bars, legends = (() if cb is None else (cb,)), (() if legend is None else (legend,))
        if cb is not None:
            cb.solids.set_rasterized(False)
            cb.solids.set_edgecolor("face")  # these test bars are opaque, with no extend caps
        notes += prepare_figure(fig, data_axes=(ax,), colorbars=bars)
        result = save_figure(fig, name + ".pdf", project_root=root, extra_formats=("svg",),
                             preview_dpi=180, layout="preserve", data_axes=(ax,),
                             colorbars=bars, outside_legends=legends)
        records.append({"name": name, "notes": notes, "warnings": result.warnings,
                        "paths": [str(p) for p in result.paths],
                        "main_size_in": [ax.get_position().width * fig.get_figwidth(),
                                         ax.get_position().height * fig.get_figheight()]})
        plt.close(fig)

    data = pd.read_csv(inputs[0])
    grid = data.pivot(index="week", columns="bmi", values="probability").sort_index().sort_index(axis=1)
    x, y, z = grid.columns.to_numpy(float), grid.index.to_numpy(float), grid.to_numpy(float)
    if not np.isfinite(z).all() or not ((z >= 0) & (z <= 1)).all():
        raise ValueError("Invalid probability matrix.")
    with paper_style(project_root=root):
        fig, ax = plt.subplots(figsize=(8.2, 4.9))
        cmap = palette_cmap("sequential", project_root=root, purpose="magnitude")
        mesh = ax.pcolormesh(x, y, z, shading="nearest", cmap=cmap, vmin=0, vmax=1)
        levels = [.90, .95, .975]  # existing Q2 probability thresholds, not new inference
        contours = ax.contour(x, y, z, levels=levels,
                              colors=[annotation_color(cmap(v)) for v in levels],
                              linestyles=["solid", "dashed", "dotted"],
                              linewidths=role_style("reference_line")["linewidth"])
        # One visual repair: auto placement clipped 97.5% against the left axis.
        # Anchor labels to existing contour vertices, without changing the curves.
        anchors = [path.vertices[len(path.vertices) // 2] for path in contours.get_paths()
                   if len(path.vertices)]
        ax.clabel(contours, fmt={.9: "90%", .95: "95%", .975: "97.5%"},
                  fontsize=role_style("annotation")["fontsize"], manual=anchors)
        ax.set(xlim=(x.min(), x.max()), ylim=(y.min(), y.max()),
               xlabel="BMI（kg/m²）", ylabel="孕周（周）")
        ax.set_xticks(np.arange(20, 50, 5))
        ax.set_yticks(np.arange(10, 26, 3))
        notes = prepare_figure(fig, data_axes=(ax,), horizontal_ylabels=(ax,))
        fig.tight_layout(rect=(0, 0, .76, 1))
        cb = add_right_colorbar(ax, mesh, label="达标概率", ticks=np.linspace(0, 1, 6), format=PercentFormatter(1))
        np.testing.assert_array_equal(mesh.get_array(), z)
        export(fig, ax, "q2_probability", notes, cb)

    data, summary = pd.read_csv(inputs[1]), pd.read_csv(inputs[2])
    if data.duplicated(["iteration", "group"]).any() or summary["group"].duplicated().any():
        raise ValueError("Duplicate records.")
    groups, weeks = sorted(data.group.unique()), np.arange(10, 26)
    if groups != list(range(1, 9)) or sorted(summary.group.tolist()) != groups:
        raise ValueError("The fixture requires baseline groups G1-G8.")
    frequencies = np.zeros((len(weeks), len(groups)))
    baseline = summary.set_index("group").loc[groups, "baseline_integer_week"].to_numpy()
    for column, group in enumerate(groups):
        # Preserve established denominator: converged AND reachable records per group.
        selected = data.loc[(data.group == group) & (data.converged == True) & (data.reachable == True),
                            "recommended_integer_week"].to_numpy()
        if not len(selected) or not np.isin(selected, weeks).all():
            raise ValueError("Invalid or empty reachable recommendations.")
        frequencies[:, column] = [(selected == week).sum() / len(selected) for week in weeks]
    np.testing.assert_allclose(frequencies.sum(axis=0), 1)
    with paper_style(project_root=root):
        fig, ax = plt.subplots(figsize=(8.8, 6.2))
        cmap = palette_cmap("sequential", project_root=root, purpose="magnitude")
        mesh = ax.pcolormesh(np.arange(.5, 9), np.arange(9.5, 26), frequencies,
                             cmap=cmap, vmin=0, vmax=1, edgecolors=role_style("grid")["color"],
                             linewidth=role_style("grid")["linewidth"])
        accent = palette_colors(project_root=root)[0]  # explicit warm accent on the blue matrix
        for col, group in enumerate(groups):
            for row, week in enumerate(weeks):
                value = frequencies[row, col]
                if value > 0:
                    label = "<1" if value < .01 else f"{value * 100:.0f}"
                    ax.text(group, week, label, ha="center", va="center",
                            color=annotation_color(cmap(mesh.norm(value))), **role_style("annotation"))
            ax.add_patch(Rectangle((group-.45, baseline[col]-.43), .9, .86, fill=False,
                                   edgecolor=accent, **role_style("reference_line")))
        handle = Rectangle((0, 0), 1, 1, fill=False, edgecolor=accent, **role_style("reference_line"))
        legend = outside_legend(ax, [handle], ["未加扰动时的基准推荐"])
        ax.set(xticks=groups, xticklabels=[f"G{g}" for g in groups], yticks=weeks,
               xlabel="BMI 分组", ylabel="推荐整数孕周\n（周）")
        notes = prepare_figure(fig, data_axes=(ax,), horizontal_ylabels=(ax,))
        fig.tight_layout(rect=(0, 0, .76, 1))
        cb = add_right_colorbar(ax, mesh, label="组内频率", ticks=np.linspace(0, 1, 6), format=PercentFormatter(1))
        np.testing.assert_array_equal(mesh.get_array(), frequencies)
        export(fig, ax, "q3_frequency", notes, cb, legend)

    with paper_style(project_root=root):
        fig, ax = plt.subplots(figsize=(6.4, 4.2))
        x, values = [1, 2, 3, 4, 5], [[3, 5, 4, 7, 8], [2, 3, 5, 5, 7]]
        colors = palette_colors(project_root=root)
        lines = [ax.plot(x, v, color=colors[i], marker=marker, **role_style("data_line"))[0]
                 for i, (v, marker) in enumerate(zip(values, ("o", "s")))]
        ax.grid(axis="y", **role_style("grid"))
        ax.set_axisbelow(True)
        ax.set(xlabel="阶段", ylabel="示例指标", xticks=x)
        legend = outside_legend(ax, lines, ["示例方案 A", "示例方案 B"], ncols=2)
        notes = prepare_figure(fig, data_axes=(ax,), horizontal_ylabels=(ax,))
        fig.tight_layout()
        for line, value in zip(lines, values):
            np.testing.assert_array_equal(line.get_ydata(), value)
        export(fig, ax, "synthetic_lines", notes, legend=legend)

    assert hashes == {str(p): digest(p) for p in inputs}, "An input changed during the test."
    report = {"test_kind": "maintainer integration, not independent model evaluation",
              "matplotlib": matplotlib.__version__, "input_hashes_unchanged": hashes,
              "q3_denominator": "converged and reachable records per group",
              "human_approved": False, "figures": records}
    (root / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

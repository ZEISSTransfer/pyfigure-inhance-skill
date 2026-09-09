"""Isolated behavior tests for visual helpers, not model aesthetic evaluation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
import figure_style as style


class VisualDesignTests(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def test_roles_are_fresh_bold_and_do_not_choose_data_colors(self):
        role = style.role_style("annotation")
        self.assertEqual(role["fontweight"], "bold")
        role["fontfamily"].append("wrong")
        self.assertNotIn("wrong", style.role_style("annotation")["fontfamily"])
        self.assertLess(style.role_style("grid")["linewidth"], style.role_style("data_line")["linewidth"])
        self.assertNotIn("color", style.role_style("reference_line"))
        for size in (7, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                style.role_style("tick", base_size=size)
        with self.assertRaises(ValueError):
            style.role_style("unknown")

    def test_contrast_linearizes_and_composites_rgba(self):
        self.assertEqual(style.annotation_color("white"), "#000000")
        self.assertEqual(style.annotation_color("black"), "#FFFFFF")
        self.assertEqual(style.annotation_color("#777777"), "#000000")
        self.assertEqual(style.annotation_color((0, 0, 0, .1)), "#000000")
        self.assertEqual(style.annotation_color((1, 1, 1, .1), canvas_color="black"), "#FFFFFF")
        with self.assertRaises(ValueError):
            style.annotation_color("white", canvas_color=(1, 1, 1, .5))

    def test_magnitude_fallback_respects_profile_and_trial(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(style.palette_cmap("sequential", project_root=root).name, "viridis")
            self.assertEqual(style.palette_cmap("sequential", project_root=root, purpose="magnitude").name, "Blues")
            self.assertFalse((root / ".figure-style.json").exists())
            profile = root / ".figure-style.json"
            profile.write_text(json.dumps({"version": 1, "palettes": {"sequential": "cividis"}}))
            before = profile.read_bytes()
            self.assertEqual(style.palette_cmap("sequential", project_root=root, purpose="magnitude").name, "cividis")
            self.assertEqual(style.palette_cmap("sequential", "viridis", project_root=root, purpose="magnitude").name, "viridis")
            self.assertEqual(profile.read_bytes(), before)
        with self.assertRaises(ValueError):
            style.palette_cmap("diverging", purpose="magnitude")

    def test_linked_colorbar_follows_position_size_dpi_without_changing_data(self):
        with style.paper_style():
            fig = plt.figure(figsize=(8, 5))
            ax = fig.add_axes([.2, .18, .45, .65])
            mesh = ax.pcolormesh([[0, .3], [.7, 1]], vmin=0, vmax=1)
            before = mesh.get_array().copy(), mesh.norm, mesh.cmap, ax.get_xlim(), ax.get_ylim()
            original_position = ax.get_position().bounds
            cb = style.add_right_colorbar(ax, mesh, label="频率", width_pt=10, gap_pt=14)
            self.assertEqual(ax.get_position().bounds, original_position)
            for dpi, size, position in ((100, (8, 5), [.2,.18,.45,.65]),
                                       (180, (9, 6), [.22,.2,.42,.6])):
                fig.set_dpi(dpi)
                fig.set_size_inches(*size)
                ax.set_position(position)
                fig.canvas.draw()
                main, bar = ax.get_window_extent(), cb.ax.get_window_extent()
                self.assertAlmostEqual(main.y0, bar.y0, places=5)
                self.assertAlmostEqual(main.y1, bar.y1, places=5)
                self.assertAlmostEqual((bar.x0 - main.x1) * 72 / dpi, 14, places=5)
                self.assertAlmostEqual(bar.width * 72 / dpi, 10, places=5)
            np.testing.assert_array_equal(mesh.get_array(), before[0])
            self.assertIs(mesh.norm, before[1])
            self.assertIs(mesh.cmap, before[2])
            self.assertEqual((ax.get_xlim(), ax.get_ylim()), before[3:])

    def test_linked_bar_rejects_duplicate_foreign_and_invalid_without_new_axes(self):
        fig, (ax, other) = plt.subplots(1, 2)
        mesh = ax.pcolormesh([[0, 1]])
        for kwargs in ({"gap_pt": 0}, {"width_pt": float("nan")}, {"label": ""}):
            args = {"label": "frequency", **kwargs}
            with self.assertRaises(ValueError):
                style.add_right_colorbar(ax, mesh, **args)
            self.assertEqual(len(fig.axes), 2)
        with self.assertRaises(ValueError):
            style.add_right_colorbar(other, mesh, label="frequency")
        style.add_right_colorbar(ax, mesh, label="frequency")
        with self.assertRaises(ValueError):
            style.add_right_colorbar(ax, mesh, label="frequency")
        self.assertEqual(len(fig.axes), 3)

    def test_outside_legend_preserves_order_and_follows_axes(self):
        with style.paper_style():
            fig, ax = plt.subplots(figsize=(7, 4.5))
            a, = ax.plot([0, 1], [2, 3])
            b, = ax.plot([0, 1], [3, 4])
            legend = style.outside_legend(ax, [b, a], ["乙", "甲"], ncols=2)
            style.prepare_figure(fig, data_axes=[ax])
            fig.tight_layout()
            fig.canvas.draw()
            self.assertEqual([t.get_text() for t in legend.get_texts()], ["乙", "甲"])
            gap = (legend.get_window_extent().y0 - ax.get_window_extent().y1) * 72 / fig.dpi
            self.assertAlmostEqual(gap, 8, places=5)
            self.assertEqual(style.check_visual_balance(fig, data_axes=[ax], outside_legends=[legend]), ())
            with self.assertRaises(ValueError):
                style.outside_legend(ax, [a], ["甲"])

    def test_visual_diagnostics_are_read_only_and_reach_export(self):
        with tempfile.TemporaryDirectory() as folder, style.paper_style():
            fig = plt.figure(figsize=(6, 4))
            ax = fig.add_axes([.2, .2, .25, .3])
            line, = ax.plot([0, 1], [0, 1], label="sample")
            ax.grid(linewidth=1.5)
            mesh = ax.pcolormesh([[0, 1], [1, 0]], vmin=0, vmax=1)
            cax = fig.add_axes([.7, .3, .02, .5])
            cb = fig.colorbar(mesh, cax=cax)
            legend = ax.legend(handles=[line], loc="center")
            style.prepare_figure(fig, data_axes=[ax], colorbars=[cb])
            positions = [a.get_position().bounds for a in fig.axes]
            result = style.save_figure(fig, "diagnostic.svg", project_root=folder, layout="preserve",
                                       data_axes=[ax], colorbars=[cb], outside_legends=[legend])
            joined = " | ".join(result.warnings)
            for token in ("main panel", "major grid", "do not align", "overlaps a selected"):
                self.assertIn(token, joined)
            self.assertEqual([a.get_position().bounds for a in fig.axes], positions)
            np.testing.assert_array_equal(line.get_ydata(), [0, 1])

    def test_foreign_legend_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as folder:
            fig, ax = plt.subplots()
            other, bx = plt.subplots()
            line, = bx.plot([1, 2], label="foreign")
            legend = bx.legend(handles=[line])
            with self.assertRaises(ValueError):
                style.save_figure(fig, "wrong.svg", project_root=folder, outside_legends=[legend])
            self.assertFalse(list(Path(folder).iterdir()))


if __name__ == "__main__":
    unittest.main()

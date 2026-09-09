"""Typography and spacing checks using only isolated synthetic data."""
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "assets"))
import figure_style as style


class LayoutHelperTests(unittest.TestCase):
    def tearDown(self):
        plt.close("all")

    def sample(self):
        fig = plt.figure(figsize=(8.5, 4.5))
        ax = fig.add_axes([.27, .18, .40, .75])
        mesh = ax.pcolormesh([[0, .4], [.8, 1]], vmin=0, vmax=1)
        ax.set(xlabel="BMI 分组", ylabel="推荐孕周（周）")
        cax = fig.add_axes([.72, .18, .025, .75])
        cb = fig.colorbar(mesh, cax=cax)
        cb.set_label("组内频率", labelpad=1)
        cb.ax.yaxis.set_label_position("left")
        return fig, ax, mesh, cb

    def test_repair_old_labels_and_preserve_values_and_grid(self):
        with style.paper_style():
            fig, ax, mesh, cb = self.sample()
            ax.grid(color="#dddddd", linewidth=.4)
            grid = [(line.get_color(), line.get_linewidth()) for line in ax.get_xgridlines()]
            data, norm, cmap = mesh.get_array().copy(), mesh.norm, mesh.get_cmap()
            lims = ax.get_xlim(), ax.get_ylim()
            for spine in ax.spines.values():
                spine.set_visible(False)
            messages = style.prepare_figure(fig, data_axes=[ax], colorbars=[cb], horizontal_ylabels=[ax])
            self.assertEqual(messages, ())
            self.assertEqual(cb.ax.yaxis.get_label_position(), "right")
            self.assertEqual(cb.ax.yaxis.label.get_rotation(), 0)
            self.assertEqual(ax.yaxis.label.get_rotation(), 0)
            self.assertTrue(ax.spines["left"].get_visible())
            self.assertEqual(ax.spines["left"].get_edgecolor(), (0, 0, 0, 1))
            self.assertEqual(grid, [(line.get_color(), line.get_linewidth()) for line in ax.get_xgridlines()])
            self.assertEqual(lims, (ax.get_xlim(), ax.get_ylim()))
            np.testing.assert_array_equal(data, mesh.get_array())
            self.assertIs(mesh.norm, norm)
            self.assertIs(mesh.get_cmap(), cmap)
            fig.canvas.draw()
            self.assertEqual(style.check_label_spacing(fig, data_axes=[ax], colorbars=[cb]), ())

    def test_left_colorbar_label_detected_even_inside_canvas(self):
        with style.paper_style():
            fig, ax, _, cb = self.sample()
            fig.canvas.draw()
            box = cb.ax.yaxis.label.get_window_extent(fig.canvas.get_renderer())
            self.assertGreater(box.x0, 0)
            self.assertLess(box.x1, fig.bbox.x1)
            messages = style.check_label_spacing(fig, data_axes=[ax], colorbars=[cb])
            self.assertTrue(any("outside right ticks" in msg for msg in messages))

    def test_stroke_idempotent_same_color_and_existing_effects_preserved(self):
        with style.paper_style():
            fig, ax, _, cb = self.sample()
            label = ax.text(.5, .5, "中文 English", color="#176535", transform=ax.transAxes)
            special = ax.text(.2, .8, "保留", transform=ax.transAxes)
            effect = matplotlib.patheffects.withStroke(linewidth=1, foreground="white")
            special.set_path_effects([effect])
            for _ in range(2):
                messages = style.prepare_figure(fig, data_axes=[ax], colorbars=[cb])
                self.assertTrue(any("Existing text effects" in m for m in messages))
            self.assertEqual(len(label.get_path_effects()), 1)
            self.assertEqual(label.get_fontweight(), "bold")
            self.assertEqual(label.get_color(), "#176535")
            self.assertEqual(special.get_path_effects(), [effect])
            with tempfile.TemporaryDirectory() as root:
                result = style.save_figure(fig, "stroke.svg", project_root=root, layout="preserve")
                svg = result.paths[0].read_text(encoding="utf-8")
                self.assertIn("stroke: #176535", svg)
                self.assertIn("stroke-width: 0.25", svg)

    def test_export_reports_insufficient_gap_without_moving_axes(self):
        with style.paper_style():
            fig, ax, _, cb = self.sample()
            cb.ax.set_position([.672, .18, .025, .75])
            style.prepare_figure(fig, data_axes=[ax], colorbars=[cb])
            position = ax.get_position().bounds
            with tempfile.TemporaryDirectory() as root:
                result = style.save_figure(fig, "gap.pdf", project_root=root, layout="preserve",
                                           data_axes=[ax], colorbars=[cb])
            self.assertTrue(any("main plot / colorbar" in m for m in result.warnings))
            self.assertEqual(position, ax.get_position().bounds)

    def test_foreign_axes_and_invalid_settings_fail_before_mutation(self):
        with style.paper_style():
            fig, ax, _, cb = self.sample()
            other, foreign = plt.subplots()
            before = cb.ax.yaxis.get_label_position()
            for kwargs in ({"data_axes": [foreign]}, {"cjk_stroke": 0}, {"labelpad": 0}):
                with self.assertRaises(ValueError):
                    style.prepare_figure(fig, colorbars=[cb], **kwargs)
            self.assertEqual(cb.ax.yaxis.get_label_position(), before)

    def test_schematic_axis_off_remains_off(self):
        with style.paper_style():
            fig, ax = plt.subplots()
            ax.axis("off")
            style.prepare_figure(fig, data_axes=[ax])
            self.assertFalse(ax.axison)

    def test_side_by_side_colorbars_check_their_own_data_axes(self):
        with style.paper_style():
            fig = plt.figure(figsize=(12, 4))
            axes, bars = [], []
            for start in (.08, .56):
                ax = fig.add_axes([start, .18, .22, .72])
                mesh = ax.imshow([[0, 1]], aspect="auto")
                cax = fig.add_axes([start + .25, .18, .015, .72])
                cb = fig.colorbar(mesh, cax=cax, ticks=[0, 1], label="率")
                axes.append(ax)
                bars.append(cb)
            style.prepare_figure(fig, data_axes=axes, colorbars=bars)
            fig.canvas.draw()
            self.assertEqual(style.check_label_spacing(fig, data_axes=axes, colorbars=bars), ())


if __name__ == "__main__":
    unittest.main()

"""Runtime tests in isolated projects; no competition data is accessed."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "assets"))
import figure_style as style


class FigureStyleTests(unittest.TestCase):
    def test_bold_and_black_axes_cannot_be_weakened(self):
        for overrides in ({"font.weight": "normal"}, {"axes.labelweight": "normal"},
                          {"axes.edgecolor": "gray"}, {"xtick.color": "#777777"},
                          {"axes.linewidth": 0.5}, {"ytick.major.width": 0.5}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                with style.paper_style(overrides=overrides):
                    pass
        with style.paper_style():
            fig, ax = plt.subplots()
            self.assertEqual(ax.spines["left"].get_edgecolor(), (0, 0, 0, 1))
            self.assertGreaterEqual(ax.spines["left"].get_linewidth(), 1)
            self.assertEqual(ax.xaxis.label.get_fontweight(), "bold")
            plt.close(fig)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pyfigure-test-")
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()

    def tearDown(self):
        plt.close("all")
        self.temp.cleanup()

    def figure(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1, 2], [1, 3, 2], label="Observed")
        ax.set(xlabel="Time / d", ylabel="Output / unit")
        ax.legend()
        return fig, ax

    def test_local_style_restored_after_exception(self):
        original = mpl.rcParams.copy()
        with self.assertRaisesRegex(RuntimeError, "example"):
            with style.paper_style(overrides={"font.size": 17}):
                self.assertEqual(mpl.rcParams["font.size"], 17)
                raise RuntimeError("example")
        self.assertEqual(mpl.rcParams["font.size"], original["font.size"])
        self.assertEqual(mpl.rcParams["axes.prop_cycle"], original["axes.prop_cycle"])

    def test_nested_styles_restore(self):
        with style.paper_style(overrides={"font.size": 12}):
            with style.paper_style(overrides={"font.size": 8}):
                self.assertEqual(mpl.rcParams["font.size"], 8)
            self.assertEqual(mpl.rcParams["font.size"], 12)

    def test_backend_override_rejected(self):
        with self.assertRaises(ValueError):
            with style.paper_style(overrides={"backend": "svg"}):
                pass

    def test_unavailable_font_fails(self):
        with patch.object(style.font_manager, "findfont", side_effect=ValueError("missing")):
            with self.assertRaisesRegex(RuntimeError, "Required font unavailable"):
                with style.paper_style(required_text="结果"):
                    pass
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fixed_fonts_cannot_be_replaced(self):
        for key, value in (("font.family", "DejaVu Sans"), ("mathtext.fontset", "stix"),
                           ("text.usetex", True), ("pdf.use14corefonts", True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                with style.paper_style(overrides={key: value}):
                    pass
        with self.assertRaisesRegex(RuntimeError, "do not cover"):
            with style.paper_style(required_text="\U0010ffff"):
                pass

    def test_unicode_minus_uses_selected_font_support(self):
        with patch.object(style, "_fonts", return_value=False):
            with style.paper_style():
                self.assertFalse(mpl.rcParams["axes.unicode_minus"])

    def test_pdf_preview_and_data_unchanged(self):
        with style.paper_style():
            fig, ax = self.figure()
            before = ax.lines[0].get_xydata().copy()
            original_canvas = fig.canvas
            counts = (len(ax.lines), len(ax.collections), len(ax.patches))
            result = style.save_figure(fig, "figures/trend", project_root=self.root)
            self.assertEqual(result.warnings, ())
            self.assertEqual([p.suffix for p in result.paths], [".pdf", ".png"])
            self.assertTrue(result.paths[0].read_bytes().startswith(b"%PDF"))
            self.assertTrue(result.paths[1].read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            np.testing.assert_array_equal(before, ax.lines[0].get_xydata())
            self.assertEqual(counts, (len(ax.lines), len(ax.collections), len(ax.patches)))
            self.assertIs(fig.canvas, original_canvas)

    def test_svg_is_vector_for_plain_plot(self):
        with style.paper_style():
            fig, _ = self.figure()
            result = style.save_figure(fig, "figures/trend.svg", project_root=self.root,
                                       preview=False, extra_formats=("pdf",))
        tree = ET.fromstring(result.paths[0].read_bytes())
        self.assertTrue(tree.tag.endswith("svg"))
        self.assertEqual(len(tree.findall(".//{http://www.w3.org/2000/svg}image")), 0)
        self.assertEqual([p.suffix for p in result.paths], [".svg", ".pdf"])

    def test_export_detects_labels_omitted_from_font_preflight(self):
        with style.paper_style():
            fig, ax = self.figure()
            ax.set_xlabel("Unsupported \U0010ffff")
            with self.assertRaisesRegex(RuntimeError, "Missing glyphs"):
                style.save_figure(fig, "figures/bad.pdf", project_root=self.root)
        self.assertFalse((self.root / "figures").exists())

    def test_rejects_traversal_and_sibling_prefix(self):
        fig, _ = self.figure()
        for dest in ("../outside/bad.pdf", self.root.with_name("project-other") / "bad.pdf"):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                style.save_figure(fig, dest, project_root=self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_rejects_skill_and_git_outputs(self):
        fig, _ = self.figure()
        for dest in (".agents/skills/demo/x.pdf", ".git/x.pdf"):
            with self.subTest(dest=dest), self.assertRaises(ValueError):
                style.save_figure(fig, dest, project_root=self.root)

    def test_rejects_external_parent_link(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        link = self.root / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Host does not allow directory symlinks: {exc}")
        fig, _ = self.figure()
        with self.assertRaises(ValueError):
            style.save_figure(fig, "linked/bad.pdf", project_root=self.root)
        self.assertEqual(list(outside.iterdir()), [])

    def test_preview_collision_blocks_entire_export(self):
        existing = self.root / "plot.png"
        existing.write_bytes(b"original preview")
        fig, _ = self.figure()
        with self.assertRaises(FileExistsError):
            style.save_figure(fig, "plot.pdf", project_root=self.root)
        self.assertEqual(existing.read_bytes(), b"original preview")
        self.assertFalse((self.root / "plot.pdf").exists())

    def test_explicit_overwrite_leaves_backup_and_unrelated_files(self):
        old = self.root / "plot.pdf"
        old.write_bytes(b"old figure")
        backup = self.root / "before.pdf"
        shutil.copy2(old, backup)
        protected = self.root / "results.csv"
        protected.write_text("x,y\n1,2\n", encoding="utf-8")
        with style.paper_style():
            fig, _ = self.figure()
            style.save_figure(fig, old, project_root=self.root, overwrite=True)
        self.assertEqual(backup.read_bytes(), b"old figure")
        self.assertEqual(protected.read_text(encoding="utf-8"), "x,y\n1,2\n")
        self.assertTrue(old.read_bytes().startswith(b"%PDF"))

    def test_clipped_text_is_reported_then_one_targeted_repair(self):
        with style.paper_style():
            fig, ax = self.figure()
            original_data = ax.lines[0].get_xydata().copy()
            note = fig.text(0.95, 0.20, "Source: saved simulation results")
            first = style.save_figure(fig, "before.pdf", project_root=self.root)
            self.assertTrue(any("outside" in message for message in first.warnings))
            note.set_position((0.6, 0.20))
            note.set_ha("center")
            second = style.save_figure(fig, "after.pdf", project_root=self.root)
            self.assertFalse(any("outside" in message for message in second.warnings))
            np.testing.assert_array_equal(original_data, ax.lines[0].get_xydata())

    def test_layout_preserve_does_not_replace_constrained(self):
        with style.paper_style():
            fig, ax = plt.subplots(layout="constrained")
            ax.plot([1, 2], [3, 4])
            engine = fig.get_layout_engine()
            with self.assertRaises(ValueError):
                style.save_figure(fig, "wrong.pdf", project_root=self.root)
            style.save_figure(fig, "right.pdf", project_root=self.root, layout="preserve")
            self.assertIs(fig.get_layout_engine(), engine)

    def test_inherited_tight_crop_cannot_hide_overflow(self):
        with style.paper_style(overrides={"savefig.bbox": "tight"}):
            fig, _ = self.figure()
            fig.text(1.1, 0.95, "Outside")
            result = style.save_figure(fig, "sized.svg", project_root=self.root)
            tree = ET.fromstring(result.paths[0].read_bytes())
            _, _, width, height = map(float, tree.attrib["viewBox"].split())
            self.assertAlmostEqual(width, fig.get_figwidth() * 72, places=3)
            self.assertAlmostEqual(height, fig.get_figheight() * 72, places=3)

    def test_raster_layer_is_disclosed(self):
        with style.paper_style():
            fig, ax = plt.subplots()
            ax.imshow([[1, 2], [3, 4]])
            result = style.save_figure(fig, "mixed.pdf", project_root=self.root)
        self.assertTrue(any("Raster content" in message for message in result.warnings))

    def test_same_category_values_survive_chart_type_change(self):
        values = np.array([12., 18., 15.])
        with style.paper_style():
            original, old_ax = plt.subplots()
            old_ax.plot([0, 1, 2], values)
            revised, ax = plt.subplots()
            bars = ax.barh(["Baseline", "A", "B"], values)
            style.save_figure(revised, "categories.pdf", project_root=self.root)
            np.testing.assert_array_equal([bar.get_width() for bar in bars],
                                          old_ax.lines[0].get_ydata())
            np.testing.assert_array_equal(values, [12., 18., 15.])

    def test_batch_export_preserves_non_targets(self):
        protected = {"results.csv": b"x,y\n0,4\n1,7\n", "other.png": b"existing image",
                     "model.py": b"# unrelated model source\n"}
        for name, data in protected.items():
            (self.root / name).write_bytes(data)
        with style.paper_style():
            for name in ("first", "second"):
                fig, _ = self.figure()
                style.save_figure(fig, "figures/" + name, project_root=self.root)
                plt.close(fig)
        for name, data in protected.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual(len(list((self.root / "figures").iterdir())), 4)

    def test_invalid_options_write_nothing(self):
        fig, _ = self.figure()
        options = ({"preview_dpi": 0}, {"preview_dpi": float("nan")},
                   {"extra_formats": ("exe",)}, {"layout": "automatic"})
        for kwargs in options:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                style.save_figure(fig, "bad.pdf", project_root=self.root, **kwargs)
        with self.assertRaises(ValueError):
            style.save_figure(fig, "bad.png", project_root=self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_titles_rejected_without_silent_removal(self):
        for location in ("left", "center", "right", "suptitle"):
            with self.subTest(location=location), style.paper_style():
                fig, ax = self.figure()
                text = fig.suptitle("Heading") if location == "suptitle" else ax.set_title("Heading", loc=location)
                with self.assertRaisesRegex(ValueError, "No in-figure titles"):
                    style.save_figure(fig, "bad.pdf", project_root=self.root)
                self.assertEqual(text.get_text(), "Heading")
                plt.close(fig)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bilingual_svg_uses_exact_glyph_families(self):
        with style.paper_style(required_text="时间 Time 2026 −1"):
            fig, ax = self.figure()
            ax.set_xlabel("时间 Time 2026 −1")
            self.assertEqual(ax.xaxis.label.get_fontfamily(), list(style.FONT_FAMILIES))
            result = style.save_figure(fig, "mixed.svg", project_root=self.root, preview=False)
        svg = result.paths[0].read_text(encoding="utf-8")
        for family, char in (("SimSun", "时"), ("Times New Roman", "T")):
            font = style.FT2Font(style.font_manager.findfont(
                style.font_manager.FontProperties(family=family, weight="bold"), fallback_to_default=False))
            # Matplotlib 3.11 identifies paths by glyph index; older versions
            # used Unicode. Verify the rendered path/use, not just rcParams.
            ids = (f"{font.postscript_name}-{font.get_char_index(ord(char)):x}",
                   f"{font.postscript_name}-{ord(char):x}")
            self.assertTrue(any(f'xlink:href="#{glyph}"' in svg for glyph in ids),
                            f"Expected {family} glyph for {char}")
        self.assertNotIn("DejaVu", svg)

    def test_math_missing_glyph_fails_without_dummy_output(self):
        import logging
        logger = logging.getLogger("matplotlib")
        before = list(logger.handlers)
        with self.assertRaisesRegex(RuntimeError, "Missing mathematical glyph"):
            with style.paper_style():
                fig, ax = self.figure()
                ax.set_xlabel(r"$\oiint$")
                style.save_figure(fig, "bad.pdf", project_root=self.root)
        self.assertEqual(logger.handlers, before)
        self.assertFalse((self.root / "bad.pdf").exists())

    def test_project_palette_persists_and_trials_do_not_write(self):
        profile = self.root / ".figure-style.json"
        profile.write_text(json.dumps({"version": 1, "palettes": {"categorical": "nejm",
            "sequential": "cividis", "diverging": "BrBG"}}), encoding="utf-8")
        before = profile.read_bytes()
        with style.paper_style(project_root=self.root):
            self.assertEqual(mpl.rcParams["axes.prop_cycle"].by_key()["color"], list(style.PALETTES["nejm"]))
            self.assertEqual(mpl.rcParams["image.cmap"], "cividis")
        for candidate in style.PALETTES:
            with style.paper_style(project_root=self.root, palette=candidate):
                self.assertEqual(mpl.rcParams["axes.prop_cycle"].by_key()["color"], list(style.PALETTES[candidate]))
        self.assertEqual(style.palette_colors(project_root=self.root), style.PALETTES["nejm"])
        self.assertEqual(style.palette_cmap("diverging", project_root=self.root).name, "BrBG")
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_partial_confirmation_does_not_confirm_other_types(self):
        profile = self.root / ".figure-style.json"
        profile.write_text('{"version":1,"palettes":{"categorical":"aaas"}}', encoding="utf-8")
        before = profile.read_bytes()
        self.assertEqual(style.palette_cmap("sequential", project_root=self.root).name, "viridis")
        self.assertEqual(profile.read_bytes(), before)

    def test_missing_profile_uses_provisional_defaults_without_writing(self):
        self.assertEqual(style.palette_colors(project_root=self.root), style.PALETTES["npg"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_profile_or_palette_does_not_reset(self):
        profile = self.root / ".figure-style.json"
        for content in ('broken', '[]', '{"version":2,"palettes":{}}',
                        '{"version":1,"palettes":{"sequential":"nejm"}}',
                        '{"version":1,"palettes":{"unknown":"viridis"}}'):
            profile.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(ValueError):
                style.palette_colors(project_root=self.root)
            self.assertEqual(profile.read_text(encoding="utf-8"), content)
        for kind, candidate in (("categorical", "viridis"), ("sequential", "npg"), ("diverging", "Blues")):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                style.palette_cmap(kind, candidate)
        with self.assertRaises(ValueError):
            style.palette_colors("npg", count=11)

    def test_color_only_variants_preserve_all_noncolor_state(self):
        with style.paper_style(project_root=self.root):
            fig, ax = self.figure()
            style.save_figure(fig, "initial.pdf", project_root=self.root)
            line = ax.lines[0]
            def snapshot():
                return (line.get_xydata().tolist(), line.get_linewidth(), line.get_linestyle(),
                        line.get_marker(), ax.get_position().bounds, ax.get_xlim(), ax.get_ylim(),
                        ax.xaxis.label.get_fontsize(), ax.xaxis.label.get_fontweight(),
                        tuple(fig.get_size_inches()))
            before = snapshot()
            for candidate in style.PALETTES:
                color = style.palette_colors(candidate, count=1)[0]
                line.set_color(color)
                ax.get_legend().get_lines()[0].set_color(color)
                style.save_figure(fig, f"variant-{candidate}.pdf", project_root=self.root, layout="preserve")
                self.assertEqual(snapshot(), before)
                self.assertEqual(line.get_color(), color)
            self.assertFalse((self.root / ".figure-style.json").exists())

    def test_continuous_recolor_preserves_values_norm_and_limits(self):
        with style.paper_style():
            fig, ax = plt.subplots()
            norm = mpl.colors.TwoSlopeNorm(vmin=-3, vcenter=0, vmax=5)
            mesh = ax.pcolormesh([[-3, 0], [2, 5]], norm=norm,
                                 cmap=style.palette_cmap("diverging"))
            colorbar = fig.colorbar(mesh, ax=ax)
            original = mesh.get_array().copy()
            for candidate in style.CMAPS["diverging"]:
                mesh.set_cmap(style.palette_cmap("diverging", candidate))
                colorbar.solids.set_rasterized(False)
                colorbar.solids.set_edgecolor("face")
                result = style.save_figure(fig, candidate + ".svg", project_root=self.root)
                tree = ET.fromstring(result.paths[0].read_bytes())
                self.assertEqual(len(tree.findall(".//{http://www.w3.org/2000/svg}image")), 0)
                self.assertIs(mesh.norm, norm)
                self.assertEqual(mesh.get_clim(), (-3, 5))
                np.testing.assert_array_equal(mesh.get_array(), original)

    def test_project_copy_runs_without_skill(self):
        code = self.root / "code"
        code.mkdir()
        installed = self.root / ".agents" / "skills" / "pyfigure-inhance-skill" / "assets"
        installed.mkdir(parents=True)
        shutil.copy2(SKILL / "assets" / "figure_style.py", installed / "figure_style.py")
        shutil.copy2(installed / "figure_style.py", code / "_figure_style.py")
        (self.root / ".figure-style.json").write_text(
            '{"version":1,"palettes":{"categorical":"lancet"}}', encoding="utf-8")
        installed.parent.rename(installed.parent.with_name("disabled-skill"))
        # This fixture has no sys.path entry for the skill and imports only its
        # project's copy. The command runs from a separate working directory.
        entry = code / "plot.py"
        entry.write_text(
            "from pathlib import Path\nimport matplotlib as m\nm.use('Agg')\n"
            "before = m.rcParams.copy()\nfrom _figure_style import paper_style, save_figure\n"
            "assert before['font.size'] == m.rcParams['font.size']\n"
            "assert before['backend'] == m.rcParams['backend']\n"
            "import matplotlib.pyplot as p\n"
            "with paper_style(project_root=Path(__file__).resolve().parents[1]):\n "
            "assert m.rcParams['axes.prop_cycle'].by_key()['color'][0] == '#00468B'; "
            "f,a=p.subplots(); a.plot([1,2],[3,4]); "
            "save_figure(f,'figures/copied.pdf',project_root=Path(__file__).resolve().parents[1])\n",
            encoding="utf-8",
        )
        result = subprocess.run([sys.executable, str(entry)], cwd=self.temp.name,
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "figures/copied.pdf").exists())


class PackageTests(unittest.TestCase):
    def test_runtime_links_are_local_and_present(self):
        import re
        files = [SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")]
        for doc in files:
            for href in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
                if href.startswith("https://"):
                    continue
                target = (doc.parent / href).resolve()
                with self.subTest(doc=doc.name, href=href):
                    self.assertTrue(target.is_file())
                    self.assertTrue(target.is_relative_to(SKILL.resolve()))
                    self.assertNotIn("stage1-materials", target.parts)
                    self.assertNotIn("tests", target.parts)


if __name__ == "__main__":
    unittest.main()

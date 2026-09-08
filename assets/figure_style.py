"""Project-local Matplotlib style/export template; no data or model operations.

Copy to code/_figure_style.py. Importing this module never chooses a backend.
The caller determines project_root, supplies the Figure, and owns visual review.
Python 3.10+. Matplotlib is the only direct third-party dependency.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import json
import logging
import warnings

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.ft2font import FT2Font
from matplotlib.image import AxesImage, FigureImage


# Fixed categorical HEX facts, in original order; journal-inspired, not mandates.
# Source: https://github.com/nanxstats/ggsci/blob/v5.2.0/R/palettes.R
PALETTES = {
    "npg": ("#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F",
            "#8491B4", "#91D1C2", "#DC0000", "#7E6148", "#B09C85"),
    "aaas": ("#3B4992", "#EE0000", "#008B45", "#631879", "#008280",
             "#BB0021", "#5F559B", "#A20056", "#808180", "#1B1919"),
    "nejm": ("#BC3C29", "#0072B5", "#E18727", "#20854E", "#7876B1",
             "#6F99AD", "#FFDC91", "#EE4C97"),
    "lancet": ("#00468B", "#ED0000", "#42B540", "#0099B4", "#925E9F",
               "#FDAF91", "#AD002A", "#ADB6B6", "#1B1919"),
}
# Continuous maps use Matplotlib's published definitions, not categorical LUTs.
CMAPS = {"sequential": ("viridis", "cividis", "Blues"),
         "diverging": ("RdBu_r", "BrBG", "PuOr")}
DEFAULT_PALETTES = {"categorical": "npg", "sequential": "viridis", "diverging": "RdBu_r"}
FONT_FAMILIES = ("Times New Roman", "SimSun")


class _MathGlyphGuard(logging.Handler):
    """Mathtext logs missing glyphs rather than issuing Python warnings."""

    def emit(self, record):
        if "dummy symbol" in record.getMessage():
            raise RuntimeError("Missing mathematical glyph in fixed fonts; no substitute permitted. "
                               + record.getMessage())


def _palette_id(kind, palette, project_root):
    if kind not in DEFAULT_PALETTES:
        raise ValueError(f"Unknown palette kind: {kind}")
    choices = DEFAULT_PALETTES.copy()
    if project_root is not None:
        root = Path(project_root).resolve(strict=True)
        if not root.is_dir() or root == Path(root.anchor):
            raise ValueError("project_root must be an explicit project directory.")
        profile = _inside(root, root / ".figure-style.json")
        if profile.exists():
            saved = json.loads(profile.read_text(encoding="utf-8-sig"))
            if (not isinstance(saved, dict) or saved.get("version") != 1
                    or set(saved) != {"version", "palettes"}
                    or not isinstance(saved["palettes"], dict)):
                raise ValueError("Invalid .figure-style.json schema; do not silently reset it.")
            for key, value in saved["palettes"].items():
                available = PALETTES if key == "categorical" else CMAPS.get(key, ())
                if not isinstance(value, str) or value not in available:
                    raise ValueError(f"Invalid saved palette: {key}={value!r}")
                choices[key] = value
    selected = choices[kind] if palette is None else palette
    available = PALETTES if kind == "categorical" else CMAPS[kind]
    if not isinstance(selected, str) or selected not in available:
        raise ValueError(f"Invalid {kind} palette: {selected!r}")
    return selected


def palette_colors(palette=None, *, project_root=None, count=None):
    """Read project defaults or trial an ID. Never writes a project profile.

    count prevents accidental cycling when the known series count is too large.
    Callers keep their semantic series-to-index mapping stable across figures.
    """
    colors = PALETTES[_palette_id("categorical", palette, project_root)]
    if count is None:
        return colors
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= len(colors):
        raise ValueError("Series count exceeds this palette or is invalid; do not silently recycle colors.")
    return colors[:count]


def palette_cmap(kind, palette=None, *, project_root=None):
    """Return a continuous colormap; normalization stays under caller control."""
    if kind not in CMAPS:
        raise ValueError("Use sequential or diverging for a continuous color scale.")
    return mpl.colormaps[_palette_id(kind, palette, project_root)].copy()


@dataclass(frozen=True)
class ExportResult:
    """Written files and diagnostics, NOT a scientific/visual approval."""

    paths: tuple[Path, ...]
    warnings: tuple[str, ...]


def _fonts(required_text: str):
    required = {ord(char) for char in required_text if not char.isspace()}
    covered = set()
    for family in FONT_FAMILIES:
        try:
            path = font_manager.findfont(
                font_manager.FontProperties(family=[family]), fallback_to_default=False
            )
            covered.update(FT2Font(path).get_charmap())
        except (ValueError, OSError, RuntimeError) as exc:
            raise RuntimeError(f"Required font unavailable: {family}; no substitute permitted.") from exc
    if not required.issubset(covered):
        raise RuntimeError("Required fonts do not cover required_text; report unsupported glyphs.")
    return 0x2212 in covered


@contextmanager
def paper_style(*, required_text: str = "", project_root=None, palette=None,
                overrides: dict | None = None):
    """Use fixed bilingual fonts and a project/default or explicit trial palette.

    required_text should include actual ordinary labels (not TeX source).
    Both required fonts must be installed. Overrides may tune size/weight/layout,
    not replace fonts or bypass palette selection. Yield the fixed family tuple.
    This context never persists palette choices; human confirmation is separate.
    """
    unicode_minus = _fonts(required_text)
    params = {
        "font.family": list(FONT_FAMILIES),
        "font.size": 12, "font.weight": "bold", "axes.labelsize": 13,
        "axes.labelweight": "bold",
        "xtick.labelsize": 11, "ytick.labelsize": 11, "legend.fontsize": 11,
        "axes.unicode_minus": unicode_minus,
        "axes.prop_cycle": mpl.cycler(color=palette_colors(palette, project_root=project_root)),
        "image.cmap": _palette_id("sequential", None, project_root),
        "mathtext.fontset": "custom", "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman:italic", "mathtext.bf": "Times New Roman:bold",
        "mathtext.bfit": "Times New Roman:italic:bold", "mathtext.cal": "Times New Roman",
        "mathtext.sf": "Times New Roman", "mathtext.tt": "Times New Roman",
        "mathtext.fallback": None, "text.usetex": False,
        "figure.figsize": (6.4, 4.0), "figure.dpi": 100,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "savefig.transparent": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 1.2, "axes.grid": False,
        "lines.linewidth": 1.8, "lines.markersize": 5,
        "xtick.major.width": 1.1, "ytick.major.width": 1.1,
        "xtick.direction": "out", "ytick.direction": "out",
        "legend.frameon": False,
        "figure.autolayout": False, "figure.constrained_layout.use": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "path",
        "pdf.use14corefonts": False, "ps.useafm": False,
    }
    if overrides:
        fixed = {"backend", "font.family", "font.serif", "font.sans-serif", "font.monospace",
                 "font.cursive", "font.fantasy", "text.usetex", "axes.prop_cycle", "image.cmap",
                 "pdf.use14corefonts", "ps.useafm"}
        if any(key in fixed or key.startswith("mathtext.") for key in overrides):
            raise ValueError("Overrides cannot replace fixed fonts, palette selection, or backend.")
        params.update(overrides)
    logger = logging.getLogger("matplotlib")
    guard = _MathGlyphGuard()
    logger.addHandler(guard)
    try:
        with mpl.rc_context(params):
            yield FONT_FAMILIES
    finally:
        logger.removeHandler(guard)


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Output leaves project_root: {path}") from exc
    # Check lexical components too, so an in-project link under .agents cannot
    # disguise writing through the installation folder.
    parts = {part.casefold() for part in (*path.parts, *relative.parts)}
    if parts.intersection({".agents", ".git"}):
        raise ValueError("Do not write generated figures into skill/git directories.")
    return resolved


def _paths(path, project_root, preview, extra_formats):
    root = Path(project_root).resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise ValueError("project_root must be an explicit project directory, not a drive root.")
    requested = Path(path)
    if not requested.is_absolute():
        requested = root / requested
    suffix = requested.suffix.lower()
    if not suffix:
        requested = requested.with_suffix(".pdf")
        suffix = ".pdf"
    if suffix not in {".pdf", ".svg"}:
        raise ValueError("The primary figure must be .pdf or .svg (or have no suffix).")
    formats = [suffix[1:]]
    if isinstance(extra_formats, str):
        raise TypeError("extra_formats must be a sequence, e.g. ('svg',), not a string.")
    for fmt in extra_formats:
        if fmt not in {"pdf", "svg", "png"}:
            raise ValueError(f"Unsupported extra format: {fmt}")
        if fmt not in formats:
            formats.append(fmt)
    if preview and "png" not in formats:
        formats.append("png")
    return root, tuple(_inside(root, requested.with_suffix('.' + fmt)) for fmt in formats)


def save_figure(fig, path, *, project_root, preview: bool = True,
                preview_dpi: float = 160, extra_formats=(),
                layout: str = "tight", overwrite: bool = False) -> ExportResult:
    """Export the same Figure to PDF/SVG and, by default, a PNG preview.

    Relative paths are relative to the caller-supplied project_root.
    Existing destinations are refused unless overwrite=True AFTER caller backup.
    All formats are rendered in memory before writing; an IO failure while
    writing may leave partial outputs, which must be reported by the caller.
    This function does not back up sources, rerun code, retry, or certify data.
    """
    # Do not silently erase titles: fix the source, preserving semantic labels.
    for container in (fig, *fig.findobj(match=lambda obj: type(obj).__name__ == "SubFigure")):
        heading = getattr(container, "_suptitle", None)
        if heading is not None and heading.get_text().strip():
            raise ValueError("No in-figure titles: remove suptitle in the source; paper captions are external.")
    if any(ax.get_title(loc=loc).strip() for ax in fig.axes for loc in ("left", "center", "right")):
        raise ValueError("No in-figure titles: remove axes titles in the source.")
    if layout not in {"tight", "preserve"}:
        raise ValueError("layout must be 'tight' or 'preserve'.")
    if not 0 < preview_dpi < float("inf"):
        raise ValueError("preview_dpi must be finite and positive.")
    root, targets = _paths(path, project_root, preview, extra_formats)
    for target in targets:
        if target.exists() and (not overwrite or not target.is_file()):
            raise FileExistsError(f"Refusing to replace {target}; back up before overwrite=True.")
    engine = fig.get_layout_engine()
    if layout == "tight" and engine is not None and "Constrained" in type(engine).__name__:
        raise ValueError("Figure already uses constrained layout; use layout='preserve' intentionally.")

    messages = []
    buffers = []
    original_canvas = fig.canvas
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            canvas = FigureCanvasAgg(fig)
            if layout == "tight":
                fig.tight_layout()
            canvas.draw()
            bbox = fig.get_tightbbox(canvas.get_renderer())
            width, height = fig.get_size_inches()
            tolerance = 1 / 72  # one point; coarse bounds, not overlap detection
            if bbox is not None and (
                bbox.x0 < -tolerance or bbox.y0 < -tolerance
                or bbox.x1 > width + tolerance or bbox.y1 > height + tolerance
            ):
                messages.append("Content extends outside the fixed canvas; inspect clipping.")
            if any(isinstance(artist, (AxesImage, FigureImage)) or artist.get_rasterized()
                   for artist in fig.findobj()):
                messages.append("Raster content exists inside the vector file; review its resolution.")
            for target in targets:
                buffer = BytesIO()
                # An explicit rc context disables inherited bbox='tight', which
                # would hide clipping by changing the requested physical size.
                with mpl.rc_context({"savefig.bbox": None}):
                    fig.savefig(buffer, format=target.suffix[1:], dpi=preview_dpi,
                                bbox_inches=None)
                buffers.append(buffer.getvalue())
            messages.extend(str(item.message) for item in captured)
        if any("Glyph" in msg and "missing" in msg for msg in messages):
            raise RuntimeError("Missing glyphs during rendering; no output written. "
                               + " | ".join(dict.fromkeys(messages)))
    finally:
        fig.set_canvas(original_canvas)

    for target, data in zip(targets, buffers):
        _inside(root, target)  # recheck existing parent links immediately before write
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb" if overwrite else "xb") as output:
            output.write(data)
    return ExportResult(targets, tuple(dict.fromkeys(messages)))

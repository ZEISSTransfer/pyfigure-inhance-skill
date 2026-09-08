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
import warnings

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.ft2font import FT2Font
from matplotlib.image import AxesImage, FigureImage


COLORS = ("#28688A", "#B76032", "#397E65", "#8064A2")
FONT_CANDIDATES = (
    "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC",
    "PingFang SC", "WenQuanYi Micro Hei", "DejaVu Sans",
)


@dataclass(frozen=True)
class ExportResult:
    """Written files and diagnostics, NOT a scientific/visual approval."""

    paths: tuple[Path, ...]
    warnings: tuple[str, ...]


def _font(required_text: str, family: str | None):
    required = {ord(char) for char in required_text if not char.isspace()}
    candidates = (family,) if family else FONT_CANDIDATES
    if not family and all(code < 256 for code in required):
        candidates = ("DejaVu Sans",) + FONT_CANDIDATES[:-1]
    for candidate in candidates:
        try:
            path = font_manager.findfont(
                font_manager.FontProperties(family=[candidate]), fallback_to_default=False
            )
            glyphs = FT2Font(path).get_charmap()
        except (ValueError, OSError, RuntimeError):
            continue
        if required.issubset(glyphs):
            return candidate, 0x2212 in glyphs
    raise RuntimeError(
        "No available font covers required_text. Choose an installed font that "
        "covers the actual labels; do not export missing glyphs."
    )


@contextmanager
def paper_style(*, required_text: str = "", font_family: str | None = None,
                overrides: dict | None = None):
    """Use local defaults and yield the chosen font family.

    required_text should include actual ordinary labels (not TeX source).
    Explicitly requested unavailable fonts fail rather than silently falling back.
    Overrides are local; missing glyphs are checked again during export.
    """
    chosen, unicode_minus = _font(required_text, font_family)
    params = {
        "font.family": "sans-serif", "font.sans-serif": [chosen],
        "font.size": 10, "axes.labelsize": 10, "axes.titlesize": 11,
        "xtick.labelsize": 9, "ytick.labelsize": 9, "legend.fontsize": 9,
        "axes.unicode_minus": unicode_minus,
        "axes.prop_cycle": mpl.cycler(color=COLORS),
        "figure.figsize": (6.4, 4.0), "figure.dpi": 100,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "savefig.transparent": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.8, "axes.grid": False,
        "lines.linewidth": 1.6, "lines.markersize": 4.5,
        "xtick.direction": "out", "ytick.direction": "out",
        "legend.frameon": False,
        "figure.autolayout": False, "figure.constrained_layout.use": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "path",
    }
    if overrides:
        if "backend" in overrides:
            raise ValueError("Select a backend in the caller, not in style overrides.")
        params.update(overrides)
    with mpl.rc_context(params):
        yield chosen


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

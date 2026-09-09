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
import math
import warnings

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.ft2font import FT2Font
from matplotlib.image import AxesImage, FigureImage
from matplotlib import patheffects
from matplotlib.text import Text
from matplotlib.transforms import Bbox, ScaledTranslation


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


def _palette_id(kind, palette, project_root, *, fallback=None):
    if kind not in DEFAULT_PALETTES:
        raise ValueError(f"Unknown palette kind: {kind}")
    choices = DEFAULT_PALETTES.copy()
    if fallback is not None:
        choices[kind] = fallback
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


def palette_cmap(kind, palette=None, *, project_root=None, purpose=None):
    """Return a cmap without changing normalization or saved choices.

    purpose='magnitude' offers a light-low/dark-high sequential starting point
    ONLY when neither a saved sequential choice nor an explicit ID exists.
    """
    if kind not in CMAPS:
        raise ValueError("Use sequential or diverging for a continuous color scale.")
    if purpose not in (None, "magnitude") or (purpose is not None and kind != "sequential"):
        raise ValueError("purpose='magnitude' is only for nonnegative sequential quantities.")
    fallback = "Blues" if purpose == "magnitude" else None
    return mpl.colormaps[_palette_id(kind, palette, project_root, fallback=fallback)].copy()


def role_style(role, *, base_size=11):
    """Fresh kwargs for a visual role; not a global override or data transform.

    All text remains bold. Data/reference colors are deliberately omitted:
    callers must preserve project semantic mappings, not auto-pick a new color.
    """
    if not math.isfinite(base_size) or base_size < 8:
        raise ValueError("Use a finite base_size >= 8 pt; do not shrink text to hide crowding.")
    text = {"fontweight": "bold", "fontfamily": list(FONT_FAMILIES)}
    roles = {
        "axis_label": dict(text, fontsize=base_size + 2),
        "tick": dict(text, fontsize=base_size),
        "legend": dict(text, fontsize=base_size),
        "annotation": dict(text, fontsize=max(8, base_size - 1)),
        "data_line": {"linewidth": 1.8, "markersize": 4.5},
        "reference_line": {"linewidth": 1.1},
        "grid": {"color": "#DCE2E8", "linewidth": 0.45, "linestyle": "solid"},
    }
    if role not in roles:
        raise ValueError(f"Unknown visual role: {role!r}")
    return roles[role]


def annotation_color(background, *, canvas_color="#FFFFFF"):
    """Choose opaque black/white text for one known flat sRGB background.

    Composite background alpha onto the opaque canvas, then compare linearized
    relative luminance contrast. Pass cmap(norm(value)), NOT the raw value.
    This does not inspect pixels or certify visibility over gradients/overlays.
    """
    red, green, blue, alpha = mpl.colors.to_rgba(background)
    canvas = mpl.colors.to_rgba(canvas_color)
    if canvas[3] != 1:
        raise ValueError("The compositing canvas must be opaque.")
    rgb = [alpha * channel + (1 - alpha) * back
           for channel, back in zip((red, green, blue), canvas[:3])]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    luminance = sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return "#000000" if (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) else "#FFFFFF"


def add_right_colorbar(ax, mappable, *, label, width_pt=10, gap_pt=14,
                       ticks=None, format=None):
    """Add a rectangular right bar that follows this axes' active position.

    Reserve right-hand space BEFORE calling. Does not shrink the host, change
    figure size, infer norm, or replace an existing bar. Use layout='preserve'
    after explicit margin allocation; shared bars/extend caps need native code.
    """
    fig = ax.figure
    if ax not in fig.axes or ax.name != "rectilinear":
        raise ValueError("Use a top-level rectangular data axes.")
    if getattr(mappable, "axes", None) is not ax:
        raise ValueError("The mappable must belong to the supplied axes.")
    if getattr(mappable, "colorbar", None) is not None:
        raise ValueError("An existing colorbar must be handled explicitly, not duplicated.")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("Supply a meaningful colorbar label.")
    if not math.isfinite(width_pt) or width_pt <= 0 or not math.isfinite(gap_pt) or gap_pt < 6:
        raise ValueError("Use positive width and a gap of at least 6 pt.")
    if getattr(mappable, "extend", "neither") != "neither":
        raise ValueError("Extended colorbars require an explicit native layout.")

    def locate(bar_ax, renderer):
        box = ax.get_position()  # active box honors data aspect constraints
        figure_width = fig.get_figwidth() * 72
        return Bbox.from_bounds(box.x1 + gap_pt / figure_width, box.y0,
                                width_pt / figure_width, box.height)

    cax = fig.add_axes([0, 0, .01, .01], axes_locator=locate)
    try:
        cb = fig.colorbar(mappable, cax=cax, orientation="vertical", ticks=ticks, format=format)
        cb.set_label(label, rotation=0, labelpad=12, ha="left", va="center")
        cb.ax.yaxis.set_label_position("right")
        cb.ax.yaxis.set_ticks_position("right")
    except Exception:
        fig.delaxes(cax)
        raise
    return cb


def outside_legend(ax, handles, labels, *, ncols=1, gap_pt=8, base_size=11):
    """Create an above-plot, left-aligned legend anchored in physical points.

    Explicit handles/labels prevent missing/reordered series. Never replace an
    existing legend, resize the figure, or decide the number of columns for you.
    Call before tight_layout, or reserve top space in a fixed layout.
    """
    handles, labels = tuple(handles), tuple(labels)
    if not handles or len(handles) != len(labels):
        raise ValueError("Supply one label per handle; no implicit truncation.")
    if isinstance(ncols, bool) or not isinstance(ncols, int) or not 1 <= ncols <= len(handles):
        raise ValueError("Invalid legend column count.")
    if not math.isfinite(gap_pt) or gap_pt < 6:
        raise ValueError("Use a legend gap of at least 6 pt.")
    if ax not in ax.figure.axes or ax.get_legend() is not None:
        raise ValueError("Use a top-level axes without an existing legend.")
    typography = role_style("legend", base_size=base_size)
    transform = ax.transAxes + ScaledTranslation(0, gap_pt / 72, ax.figure.dpi_scale_trans)
    return ax.legend(handles, labels, loc="lower left", bbox_to_anchor=(0, 1),
                     bbox_transform=transform, borderaxespad=0, borderpad=0,
                     frameon=False, ncols=ncols, handlelength=2, handletextpad=.6,
                     columnspacing=1.2, labelspacing=.4,
                     prop={"family": typography["fontfamily"], "weight": "bold",
                           "size": typography["fontsize"]})


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
        "axes.edgecolor": "#000000", "axes.labelcolor": "#000000",
        "xtick.color": "#000000", "ytick.color": "#000000",
        "lines.linewidth": 1.8, "lines.markersize": 5,
        "xtick.major.width": 1.1, "ytick.major.width": 1.1,
        "xtick.direction": "out", "ytick.direction": "out",
        "legend.frameon": False,
        "figure.autolayout": False, "figure.constrained_layout.use": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "path",
        "pdf.use14corefonts": False, "ps.useafm": False,
    }
    if overrides:
        for key in ("font.weight", "axes.labelweight"):
            if key in overrides and overrides[key] != "bold":
                raise ValueError("Bold text is required; do not weaken font weight.")
        for key in ("axes.linewidth", "xtick.major.width", "ytick.major.width"):
            if key in overrides and not float(overrides[key]) >= 1.0:
                raise ValueError("Visible axes and major ticks must be at least 1.0 pt.")
        for key in ("axes.edgecolor", "xtick.color", "ytick.color"):
            if key in overrides and mpl.colors.to_hex(overrides[key]) != "#000000":
                raise ValueError("Axes and ticks must be black.")
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


class _CJKStroke(patheffects.withStroke):
    """Same-color typographic thickening; distinguish it for idempotent updates."""

    def __init__(self, width, color):
        self.stroke_width = width
        super().__init__(linewidth=width, foreground=color)


def _has_cjk(text):
    return any('\u3400' <= ch <= '\u9fff' or '\uf900' <= ch <= '\ufaff'
               or '\U00020000' <= ch <= '\U0003134f' for ch in text)


def _check_members(fig, data_axes, colorbars, horizontal_ylabels=()):
    if any(ax not in fig.axes for ax in (*data_axes, *horizontal_ylabels)):
        raise ValueError("Axes must belong to the supplied Figure.")
    if any(cb.ax not in fig.axes or cb.orientation != "vertical" for cb in colorbars):
        raise ValueError("Only vertical colorbars belonging to this Figure are supported.")
    if any(cb.ax in data_axes for cb in colorbars):
        raise ValueError("Keep data_axes and colorbar axes separate.")
    if any(ax not in data_axes for ax in horizontal_ylabels):
        raise ValueError("Horizontal y labels must belong to the selected data_axes.")


def prepare_figure(fig, *, data_axes=(), colorbars=(), horizontal_ylabels=(),
                   labelpad=12, cjk_stroke=0.25):
    """Explicitly apply fixed typography/axes and selected horizontal labels.

    Never changes data, colormaps, normalization, axes limits, grid lines or the
    canvas layout. Call after creating labels/legends/colorbars, before export.
    Existing non-template path effects are retained and reported for review.
    Returns diagnostics, not visual approval. This is NOT called by save_figure.
    """
    data_axes, colorbars, horizontal_ylabels = map(tuple, (data_axes, colorbars, horizontal_ylabels))
    _check_members(fig, data_axes, colorbars, horizontal_ylabels)
    if not 6 <= labelpad < float("inf") or not 0 < cjk_stroke <= 0.5:
        raise ValueError("Use labelpad >= 6 pt and a CJK stroke in (0, 0.5] pt.")
    _fonts("")
    for ax in data_axes:
        if not ax.axison:
            continue  # do not turn schematic/annotation panels into coordinate plots
        for name, spine in ax.spines.items():
            if name in ("left", "bottom"):
                spine.set_visible(True)
            if spine.get_visible():
                spine.set_color("#000000")
                spine.set_linestyle("solid")
                spine.set_linewidth(max(1.2, spine.get_linewidth()))
        ax.tick_params(axis="both", which="major", color="black", labelcolor="black",
                       width=1.1, length=3.5)
    for ax in horizontal_ylabels:
        ax.yaxis.set_label_position("left")
        ax.set_ylabel(ax.get_ylabel(), rotation=0, labelpad=labelpad,
                      ha="right", va="center", multialignment="right")
    for cb in colorbars:
        cb.ax.yaxis.set_ticks_position("right")
        cb.ax.yaxis.set_label_position("right")
        cb.set_label(cb.ax.get_ylabel(), rotation=0, labelpad=labelpad,
                     ha="left", va="center", multialignment="left")
        cb.ax.tick_params(axis="y", which="major", color="black", labelcolor="black", width=1.1)
        cb.outline.set_visible(True)
        cb.outline.set_edgecolor("black")
        cb.outline.set_linestyle("solid")
        cb.outline.set_linewidth(1.0)
    # Materialize current tick labels before styling; this does not render a file.
    for ax in (*data_axes, *(cb.ax for cb in colorbars)):
        ax.get_xticklabels()
        ax.get_yticklabels()
    messages = []
    for text in fig.findobj(match=Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        text.set_fontfamily(list(FONT_FAMILIES))
        text.set_fontweight("bold")
        original = [effect for effect in text.get_path_effects() if not isinstance(effect, _CJKStroke)]
        if _has_cjk(text.get_text()):
            if original:
                messages.append(f"Existing text effects retained; inspect CJK weight: {text.get_text()}")
                text.set_path_effects(original)
            else:
                text.set_path_effects([_CJKStroke(cjk_stroke, text.get_color())])
        else:
            text.set_path_effects(original)
    return tuple(dict.fromkeys(messages))


def _text_box(text, renderer):
    width = max((effect.stroke_width for effect in text.get_path_effects()
                 if isinstance(effect, _CJKStroke)), default=0)
    return text.get_window_extent(renderer).padded(renderer.points_to_pixels(width / 2))


def check_label_spacing(fig, *, data_axes=(), colorbars=(), min_gap_pt=6):
    """Check right vertical colorbar chains and horizontal y-label clearances.

    Read-only after the caller's canvas draw; works with the current renderer.
    This targeted geometry check is not a general-purpose overlap detector.
    """
    data_axes, colorbars = tuple(data_axes), tuple(colorbars)
    _check_members(fig, data_axes, colorbars)
    if not 0 < min_gap_pt < float("inf"):
        raise ValueError("min_gap_pt must be finite and positive.")
    renderer = fig.canvas.get_renderer()
    unit = renderer.points_to_pixels(1)
    messages = []

    def gap(name, value):
        value /= unit
        if value < min_gap_pt:
            messages.append(f"Label spacing: {name} = {value:.1f} pt; require >= {min_gap_pt:g} pt.")

    def canvas_gap(name, box):
        gap(name + " / canvas", min(box.x0 - fig.bbox.x0, box.y0 - fig.bbox.y0,
                                    fig.bbox.x1 - box.x1, fig.bbox.y1 - box.y1))

    for cb in colorbars:
        bar = cb.ax.get_window_extent(renderer)
        host = getattr(cb.mappable, "axes", None)
        hosts = (host,) if host in data_axes else data_axes
        for ax in hosts:
            box = ax.get_window_extent(renderer)
            if min(box.y1, bar.y1) > max(box.y0, bar.y0):
                gap("main plot / colorbar", bar.x0 - box.x1)
        label = cb.ax.yaxis.label
        if not label.get_visible() or not label.get_text().strip():
            continue
        if cb.ax.yaxis.get_label_position() != "right" or label.get_rotation() % 360 != 0:
            messages.append("Label spacing: vertical colorbar name should be horizontal, outside right ticks.")
        box = _text_box(label, renderer)
        ticks = [t for t in cb.ax.get_yticklabels() if t.get_visible() and t.get_text().strip()]
        right_edge = max([bar.x1, *(_text_box(t, renderer).x1 for t in ticks)])
        gap("colorbar ticks / name", box.x0 - right_edge)
        canvas_gap("colorbar name", box)
    for ax in data_axes:
        label = ax.yaxis.label
        if (label.get_visible() and label.get_text().strip() and label.get_rotation() % 360 == 0
                and ax.yaxis.get_label_position() == "left"):
            box = _text_box(label, renderer)
            ticks = [t for t in ax.get_yticklabels() if t.get_visible() and t.get_text().strip()]
            left_edge = min([ax.get_window_extent(renderer).x0,
                             *(_text_box(t, renderer).x0 for t in ticks)])
            gap("y label / ticks", left_edge - box.x1)
            canvas_gap("y label", box)
    return tuple(dict.fromkeys(messages))


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


def check_visual_balance(fig, *, data_axes=(), colorbars=(), outside_legends=(),
                         min_main_size_pt=(144, 108), alignment_tolerance_pt=2):
    """Read-only geometry diagnostics after canvas.draw(), not an aesthetic score.

    Size thresholds are review triggers at exported physical size, not universal
    minima for every panel. Only explicitly supplied outside legends are checked.
    Does not judge emphasis, color harmony, empty-data regions, or all collisions.
    """
    data_axes, colorbars, outside_legends = map(tuple, (data_axes, colorbars, outside_legends))
    _check_members(fig, data_axes, colorbars)
    if any(legend.get_figure() is not fig for legend in outside_legends):
        raise ValueError("Legends must belong to the supplied Figure.")
    if (len(min_main_size_pt) != 2 or any(not math.isfinite(v) or v <= 0 for v in min_main_size_pt)
            or not math.isfinite(alignment_tolerance_pt) or alignment_tolerance_pt < 0):
        raise ValueError("Invalid visual-check thresholds.")
    renderer = fig.canvas.get_renderer()
    unit = renderer.points_to_pixels(1)
    messages = []
    boxes = [(ax, ax.get_window_extent(renderer)) for ax in data_axes if ax.get_visible() and ax.axison]
    for index, (ax, box) in enumerate(boxes, 1):
        if box.width / unit < min_main_size_pt[0] or box.height / unit < min_main_size_pt[1]:
            messages.append(f"Visual review: main panel {index} is only {box.width / unit:.1f} x "
                            f"{box.height / unit:.1f} pt; check final-size legibility, not automatic failure.")
        if any(line.get_visible() and line.get_linewidth() > .8
               for line in (*ax.get_xgridlines(), *ax.get_ygridlines())):
            messages.append(f"Visual review: panel {index} major grid is heavy (>0.8 pt); inspect hierarchy.")
    for cb in colorbars:
        host = getattr(cb.mappable, "axes", None)
        if host not in data_axes:
            continue  # shared/standalone mappings require explicit manual review
        bar = cb.ax.get_window_extent(renderer)
        main = host.get_window_extent(renderer)
        if max(abs(bar.y0 - main.y0), abs(bar.y1 - main.y1)) / unit > alignment_tolerance_pt:
            messages.append("Visual review: colorbar ends do not align with its main plot; "
                            "confirm intentional shortened/extended layout or repair.")
    for legend in outside_legends:
        if not legend.get_visible():
            continue
        box = legend.get_window_extent(renderer)
        if min(box.x0 - fig.bbox.x0, box.y0 - fig.bbox.y0,
               fig.bbox.x1 - box.x1, fig.bbox.y1 - box.y1) / unit < 6:
            messages.append("Visual review: outside legend lacks 6 pt canvas clearance.")
        for ax, main in boxes:
            if box.overlaps(main):
                messages.append("Visual review: outside legend overlaps a selected main plot.")
            elif min(box.x1, main.x1) > max(box.x0, main.x0) and box.y0 >= main.y1:
                if (box.y0 - main.y1) / unit < 6:
                    messages.append("Visual review: outside legend is too close above a main plot (<6 pt).")
        for cb in colorbars:
            if box.overlaps(cb.ax.get_tightbbox(renderer)):
                messages.append("Visual review: outside legend overlaps colorbar content.")
    return tuple(dict.fromkeys(messages))


def save_figure(fig, path, *, project_root, preview: bool = True,
                preview_dpi: float = 160, extra_formats=(),
                layout: str = "tight", overwrite: bool = False,
                data_axes=(), colorbars=(), outside_legends=()) -> ExportResult:
    """Export the same Figure to PDF/SVG and, by default, a PNG preview.

    Relative paths are relative to the caller-supplied project_root.
    Existing destinations are refused unless overwrite=True AFTER caller backup.
    All formats are rendered in memory before writing; an IO failure while
    writing may leave partial outputs, which must be reported by the caller.
    This function does not back up sources, rerun code, retry, or certify data.
    """
    data_axes, colorbars, outside_legends = map(tuple, (data_axes, colorbars, outside_legends))
    _check_members(fig, data_axes, colorbars)
    if any(legend.get_figure() is not fig for legend in outside_legends):
        raise ValueError("Legends must belong to the supplied Figure.")
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
            messages.extend(check_label_spacing(fig, data_axes=data_axes, colorbars=colorbars))
            messages.extend(check_visual_balance(fig, data_axes=data_axes, colorbars=colorbars,
                                                 outside_legends=outside_legends))
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

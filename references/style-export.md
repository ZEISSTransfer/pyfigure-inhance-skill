# 样式、布局与导出

两种模式共用。模板是默认起点，不要求将已正确的项目模块全部替换。

## 固定文字规范与表达

- 图内一律不放标题、总标题或重复图题；图题与编号由论文手在论文中完成。不使用 `set_title`、`suptitle`，也不借 `fig.text` 绕过。旧标题中的必要变量、单位或分组信息应移入轴标签/色标标签/图例，不丢掉语义；不擅改论文引用。已有必要分面识别标签可保留，但不自行增加子图编号或装饰性文字。
- 中文固定宋体（Matplotlib 名称 `SimSun`），英文和数字固定 `Times New Roman`。同一标签混排时英文优先用 Times New Roman，中文回退到 SimSun；这是固定两种字体的字形分工，不是任选替代字体。缺少任一字体就报告，不改成微软雅黑、黑体或 DejaVu。所有轴、刻度、图例、色标和必要注释均检查，不只检查主轴。
- 默认字号/坐标轴比旧模板更大、更粗，但大小、字重、线宽可按实际尺寸调整。宋体文件可能只有常规字重，设置 bold 不保证有真实粗体字形；不能为了加粗换成黑体。缩入论文后仍检查，必要时返工。
- 多系列没有直接标签：配图例；已有清楚标签：不重复。图例不遮挡数据；单系列且含义已清楚时无需凑图例。
- 坐标图标明变量和单位；无量纲明确其含义，不乱加单位；示意图不强凑坐标轴。
- 字体、配色、线型跨目标图保持同一语义。顺序量用顺序色图，正负或围绕有意义中点偏离用发散色图，类别用分类色；缺失值不能默认为零。
- 不使用装饰背景、阴影、渐变柱或 3D 装饰。只调整支持阅读的留白、字重、线宽与必要网格；不自动增加结论标注。
- 坐标截断、双轴、对数尺度须有明确理由和可见说明；保持原结果含义。显示用舍入不回写源数值。

## 共用模块接入

先找现有样式模块；如果适合就复用并限定修改影响。没有时，将 [figure_style.py](../assets/figure_style.py) 复制到当前项目 `code/_figure_style.py`，保留已有同名文件，不能盲目覆盖。目标脚本从项目内模块导入，不使用 `.agents/skills` 路径。

模板只依赖 Python 标准库和 Matplotlib。数据读取仍由项目选择；不要求安装 pandas、seaborn 或额外绘图库。沿用项目环境，不自动全局安装依赖。非交互运行可由调用方在导入 pyplot 前设置 Agg；模板导入不切换 backend。

公共入口：

```python
with paper_style(project_root=PROJECT_ROOT, required_text="实际中英标签 Time 结果", overrides=None):
    # 创建 fig/ax 并使用已有数据绘图
    result = save_figure(fig, "figures/example.pdf", project_root=PROJECT_ROOT)
```

这是接入形态，不是含测试数据的成品脚本。运行前将 `required_text` 换成轴标签、图例等实际普通文字；模板核对两种字体、字形和负号，导出再检查遗漏字形。数学文本采用 Times New Roman，自带字体缺少某些数学符号时应报告并请用户决定，不能静默用另一字体补齐；外部 TeX 默认关闭。普通字形预检不代替公式成图核验。

- `paper_style` 使用局部 rc 上下文，结束后还原配置；`overrides` 可调字号、字重、尺寸、线宽，不能替换固定字体或绕过配色入口。创建及导出均放在上下文中。已有 artist 的显式字体不会被 rc 自动改写，返工须在源码逐项修正并核验。
- 真实项目调用总是传入 `project_root`，才能读取 `.figure-style.json`；不传根仅供隔离演示使用，不作为绕过项目默认的方法。分类色由 `palette_colors` 取得，顺序/发散色由 `palette_cmap` 取得；详见 [palette-guide.md](palette-guide.md)。模板只读配置，不在出图时保存“人工已确认”。
- `save_figure` 默认 PDF；也接受 SVG，默认同时输出同 stem 的 PNG 预览。`extra_formats` 可保留 PDF/SVG/PNG 兼容输出；不支持的旧格式由调用方按相同范围约束处理。
- 根目录必须由调用方明确传入，不让模板自行猜。输出默认拒绝越界、skill/版本控制目录以及覆盖已有文件。返工已经保留 before 证据后，才使用 `overwrite=True`。
- 默认 `layout="tight"`。已确认采用手动或其他布局时用 `layout="preserve"`，说明原因；不要混用布局引擎。模板不会为隐藏裁切而自动扩大输出裁框。
- 返回对象的 `paths` 是输出路径，`warnings` 是运行/布局提示，不是图表通过证明。发现越界文本、布局告警时先看图；缺字形导出失败，不把方块当成完成。
- 导出发现非空 Axes 标题或总标题会拒绝保存，要求修源码；不会悄悄删文字。用普通注释伪装的标题仍须通过源码和视觉审查识别。

## 输出与核验

沿用目标已有目录和命名；没有约定时用 `<PROJECT_ROOT>/figures/`。正式输出默认 PDF，按要求使用 SVG；检查预览由同一个 Figure 导出 PNG，不做像素修图。模板默认不光栅化矢量 artist；若原图含栅格图层则提示，不能把 PDF/SVG 扩展名当作全矢量证明。

新图可直接用矢量对象表达时保留矢量，例如小矩阵用 `pcolormesh`；Matplotlib 的色条可能自动光栅化，在输出规模合理时可对 `colorbar.solids` 设置 `set_rasterized(False)`。不为了全矢量盲目展开巨大矩阵，也不以此改动矩阵值。

连续换色可能重建色条对象，需在 `set_cmap` 后设置色条导出属性。若正式 PDF/SVG 出现色条拼接细缝，白底不透明色条可尝试 `colorbar.solids.set_edgecolor("face")` 后核验；半透明或延伸端帽有副作用，不一律套用。参见 [Figure.colorbar 的渲染说明](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.colorbar.html)。

维持固定物理画布，按最终论文尺寸判断字号、线条和留白。模板 PNG 默认 160 dpi，仅供检查；已有论文依赖 PNG 时按其原质量要求设置 `preview_dpi`（如 300），不能用低清预览替换正式兼容图。矢量文件和 PNG 字体/布局可能因渲染后端稍有差异，正式文件也应检查。

## 技术依据（仅需要核对 API 时访问）

- [Fonts in Matplotlib](https://matplotlib.org/stable/users/explain/text/fonts.html)：多字体逐字形回退支持中英混排；字体嵌入和矢量路径有不同后端行为。
- [Unicode minus](https://matplotlib.org/stable/gallery/text_labels_and_annotations/unicode_minus.html)：负号选项不是中文字体开关。
- [Tight layout guide](https://matplotlib.org/stable/users/explain/axes/tight_layout_guide.html)：自动布局不能覆盖所有情况；本项目仍按用户偏好优先 tight_layout。
- [Choosing Colormaps](https://matplotlib.org/stable/users/explain/colors/colormaps.html)：viridis 是顺序色图，并非单色相渐变；不保证任意打印条件下无失真。
- [Figure.savefig](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html)：导出格式与分辨率分开控制。

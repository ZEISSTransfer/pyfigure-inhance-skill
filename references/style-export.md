# 样式、布局与导出

两种模式共用。模板是默认起点，不要求将已正确的项目模块全部替换。

## 短场景判断

- 论文下方已有完整图题：图内不重复大标题和图号。独立查看：让图自身能说明主题。按项目已有题注约定，不修改论文编号体系。
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
with paper_style(required_text="将实际中文标签合并在此", font_family=None, overrides=None):
    # 创建 fig/ax 并使用已有数据绘图
    result = save_figure(fig, "figures/example.pdf", project_root=PROJECT_ROOT)
```

这是接入形态，不是含测试数据的成品脚本。运行前将 `required_text` 换成实际标题、轴标签及图例中的普通文字；模板探测对应字形和负号，导出再检查遗漏字形。数学公式或外部 TeX 另核验，不声称普通文字检查覆盖公式。

- `paper_style` 使用局部 rc 上下文，结束后还原配置；传入 `overrides` 可做项目统一调整。模板默认尺寸与字号只是起点，按论文实际尺寸验图。
- `save_figure` 默认 PDF；也接受 SVG，默认同时输出同 stem 的 PNG 预览。`extra_formats` 可保留 PDF/SVG/PNG 兼容输出；不支持的旧格式由调用方按相同范围约束处理。
- 根目录必须由调用方明确传入，不让模板自行猜。输出默认拒绝越界、skill/版本控制目录以及覆盖已有文件。返工已经保留 before 证据后，才使用 `overwrite=True`。
- 默认 `layout="tight"`。已确认采用手动或其他布局时用 `layout="preserve"`，说明原因；不要混用布局引擎。模板不会为隐藏裁切而自动扩大输出裁框。
- 返回对象的 `paths` 是输出路径，`warnings` 是运行/布局提示，不是图表通过证明。发现越界文本、布局告警时先看图；缺字形导出失败，不把方块当成完成。

## 输出与核验

沿用目标已有目录和命名；没有约定时用 `<PROJECT_ROOT>/figures/`。正式输出默认 PDF，按要求使用 SVG；检查预览由同一个 Figure 导出 PNG，不做像素修图。模板默认不光栅化矢量 artist；若原图含栅格图层则提示，不能把 PDF/SVG 扩展名当作全矢量证明。

维持固定物理画布，按最终论文尺寸判断字号、线条和留白。模板 PNG 默认 160 dpi，仅供检查；已有论文依赖 PNG 时按其原质量要求设置 `preview_dpi`（如 300），不能用低清预览替换正式兼容图。矢量文件和 PNG 字体/布局可能因渲染后端稍有差异，正式文件也应检查。

## 技术依据（仅需要核对 API 时访问）

- [Unicode minus](https://matplotlib.org/stable/gallery/text_labels_and_annotations/unicode_minus.html)：负号选项不是中文字体开关。
- [Tight layout guide](https://matplotlib.org/stable/users/explain/axes/tight_layout_guide.html)：自动布局不能覆盖所有情况；本项目仍按用户偏好优先 tight_layout。
- [Choosing Colormaps](https://matplotlib.org/stable/users/explain/colors/colormaps.html)：viridis 是顺序色图，并非单色相渐变；不保证任意打印条件下无失真。
- [Figure.savefig](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.savefig.html)：导出格式与分辨率分开控制。

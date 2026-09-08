# pyfigure-inhance-skill

面向 Codex 当前项目的 Python 科学绘图 skill：首次绘图前置约束，以及已有图的审查、源码返工与批修。使用 Matplotlib、矢量正式图和同源检查预览；不改变建模结果。

## 项目本地部署

在目标项目创建 `.agents/skills/pyfigure-inhance-skill/`，只复制以下运行文件并保持相对结构：

- `SKILL.md`
- `references/` 中的六个 Markdown 文件
- `assets/figure_style.py`

无需 README；不需要 `agents/`、`scripts/` 或安装器。已有部署先对比并保留本地修改，不直接覆盖。当前源码仓库本身不是其他项目的自动部署位置。

Codex 可按 description 匹配，也可显式调用 `$pyfigure-inhance-skill`。项目本地路径及元数据要求见 [OpenAI 官方部署说明](https://learn.chatgpt.com/docs/build-skills)。这里仅支持 Codex，不承诺其他客户端兼容。

## 调用示例

- “用 $pyfigure-inhance-skill，根据问题二已保存结果绘图，不重新运行模型。”
- “审查这些图，只指出问题，先不要改文件。”
- “按这份意见修改问题三的两张图源码，重新出图并检查，不动其他图。”
- “批修指定 figures 目录中的图，修正明显问题并统一专业风格。”
- “这张图只换成 NEJM 配色看看，其他都别改，先不设为项目默认。”
- “选这版，今后本项目分类图默认用 NEJM；连续色图的选择不变。”

默认由 Agent 出图并初检，明确错误最多再自动修一轮；人工新意见开启新的有界返工。正式图默认 PDF，可指定 SVG。只有截图缺少数据/源码时只能完成相应范围的审查。

## 模板与复现

首次需要时将 `assets/figure_style.py` 复制到项目 `code/_figure_style.py`（已有合适模块则复用）。色板已内置，不需要复制第二个运行资产；目标绘图脚本不依赖 skill 安装路径。模板使用 Python 3.10+ 语法，建议沿用已验证的 Matplotlib 3.11.1 环境；未验证全部旧版本。必须安装宋体（SimSun）和 Times New Roman，缺少时停止并报告，不替换字体或自动安装依赖。

四套固定分类色板为 NPG、AAAS、NEJM、Lancet（期刊启发方案，非期刊强制标准），另有三套顺序和三套发散色图。色号、来源、试选和确认流程见 [配色参考](references/palette-guide.md)。同一项目以根目录 `.figure-style.json` 保存已确认的各类型选择；出图只读配置，试选不改默认。尚未确认的类型采用明确标注的临时起点。人可反复要求只换颜色；最终确认后才更新后续默认，不自动重绘旧图。

接口与覆盖保护见 `references/style-export.md`。首次使用不覆盖已有输出；返工在保存 before 后显式允许覆盖。模板自动检查只是辅助，不能证明图意、数据真实性或美观。

## 维护测试

在本目录使用已有 Python 环境运行：

```text
python -m unittest discover -s tests -v
```

自动测试使用临时项目与合成数据；视觉样张运行 `python tests/render_examples.py --output <隔离目录>`。输出目录必须不存在，以免覆盖。行为场景及已执行结果见 `tests/acceptance.md`；技能规则的静态走查不等于独立 Agent 行为实测。

维护者另外使用 skill-creator 自带 `quick_validate.py` 校验本目录元数据。日常运行不读取测试，也不在真实比赛项目全量重跑测试。

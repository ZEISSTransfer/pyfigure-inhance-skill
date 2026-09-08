# pyfigure-inhance-skill

面向 Codex 当前项目的 Python 科学绘图 skill：首次绘图前置约束，以及已有图的审查、源码返工与批修。使用 Matplotlib、矢量正式图和同源检查预览；不改变建模结果。课程原材料保留供开发追溯，不在日常调用中读取。

## 项目本地部署

在目标项目创建 `.agents/skills/pyfigure-inhance-skill/`，只复制以下运行文件并保持相对结构：

- `SKILL.md`
- `references/` 中的五个 Markdown 文件
- `assets/figure_style.py`

无需复制课程截图、`stage1-materials/`、`tests/` 或此 README；不需要 `agents/`、`scripts/` 或安装器。已有部署先对比并保留本地修改，不直接覆盖。当前源码仓库本身不是其他项目的自动部署位置。

Codex 可按 description 匹配，也可显式调用 `$pyfigure-inhance-skill`。项目本地路径及元数据要求见 [OpenAI 官方部署说明](https://learn.chatgpt.com/docs/build-skills)。这里仅支持 Codex，不承诺其他客户端兼容。

## 调用示例

- “用 $pyfigure-inhance-skill，根据问题二已保存结果绘图，不重新运行模型。”
- “审查这些图，只指出问题，先不要改文件。”
- “按这份意见修改问题三的两张图源码，重新出图并检查，不动其他图。”
- “批修指定 figures 目录中的图，修正明显问题并统一专业风格。”

默认由 Agent 出图并初检，明确错误最多再自动修一轮；人工新意见开启新的有界返工。正式图默认 PDF，可指定 SVG。只有截图缺少数据/源码时只能完成相应范围的审查。

## 模板与复现

首次需要时将 `assets/figure_style.py` 复制到项目 `code/_figure_style.py`（已有合适模块则复用）。目标绘图脚本依赖项目内模块，不依赖 skill 安装路径。模板语法要求 Python 3.10+，Matplotlib 需提供 layout-engine API；本轮实际验证版本见测试记录。使用中文时还需本机实际可用且覆盖标签的中文字体。不会自动安装依赖。

接口与覆盖保护见 `references/style-export.md`。首次使用不覆盖已有输出；返工在保存 before 后显式允许覆盖。模板自动检查只是辅助，不能证明图意、数据真实性或美观。

## 维护测试

在本目录使用已有 Python 环境运行：

```text
python -m unittest discover -s tests -v
```

自动测试使用临时项目与合成数据；视觉样张运行 `python tests/render_examples.py --output <隔离目录>`。输出目录必须不存在，以免覆盖。行为场景及已执行结果见 `tests/acceptance.md`；技能规则的静态走查不等于独立 Agent 行为实测。

维护者另外使用 skill-creator 自带 `quick_validate.py` 校验本目录元数据。日常运行不读取测试，也不在真实比赛项目全量重跑测试。

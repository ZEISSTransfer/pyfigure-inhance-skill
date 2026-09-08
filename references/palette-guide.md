# 固定配色与人工试选

仅首次选色、试色/换色、确认项目默认时读取。本轮来自论文手需求与联网核对，不追记为课程规则。色号的运行单一来源是 [figure_style.py](../assets/figure_style.py) 中的 `PALETTES`；ID 与顺序固定，不在各脚本复制另一套列表。

## 分类模板

| ID | 来源/数量 | 选型提示（本 skill 的应用建议，不是期刊规定） |
| --- | --- | --- |
| `npg` | Nature Reviews Cancer 启发，10 色 | 暂未确认项目方案时的分类起点；暖色、青色与深蓝并用 |
| `aaas` | Science / AAAS 启发，10 色 | 深色与高饱和红绿；多系列时检查相近深色是否可辨 |
| `nejm` | NEJM 启发，8 色 | 砖红、蓝、橙、绿；浅黄色不宜直接用于细线或小字 |
| `lancet` | Lancet Oncology 启发，9 色 | 深蓝、红、绿、青；检查红绿辨识及浅灰对比度 |

HEX 编号以模板列表从 1 起计，例如 `npg:1 = #E64B35`、`npg:2 = #4DBBD5`。`palette_colors("npg", count=系列数)` 返回对应固定 HEX；超出色数拒绝静默循环。跨图复用项目既有的“语义系列 → 色号索引”，不要按每张图排序重新分配；同义系列缺席也不挤占其色号。不强制每柱不同色，也不为用完模板凑系列。

这四套是 Nan Xiao 的 ggsci 实现整理的**期刊启发色板**，不是上述期刊官方强制规范，也不自动保证色觉无障碍或印刷效果。色号已核对 [ggsci v5.2.0 数据源](https://github.com/nanxstats/ggsci/blob/v5.2.0/R/palettes.R)；来源说明：[NPG](https://nanx.me/ggsci/reference/pal_npg.html)、[AAAS](https://nanx.me/ggsci/reference/pal_aaas.html)、[NEJM](https://nanx.me/ggsci/reference/pal_nejm.html)、[Lancet](https://nanx.me/ggsci/reference/pal_lancet.html)。核对日期 2026-09-08。模板只记录色值，不需要 R 或 ggsci 运行依赖。

## 连续数值模板（与分类分开）

| 类型 | 可选固定 ID | 未确认时起点 | 必须保持 |
| --- | --- | --- | --- |
| 顺序 | `viridis`、`cividis`、`Blues` | `viridis` | 数值有序编码；缺失值、范围和归一化语义 |
| 发散 | `RdBu_r`、`BrBG`、`PuOr` | `RdBu_r` | 既定的有意义中点、两端方向、范围及归一化 |

这里使用 [Matplotlib 官方色图定义与分类](https://matplotlib.org/stable/users/explain/colors/colormaps.html)，不冒称期刊专属方案。连续色图通过名称取得完整色表，不以几个离散 HEX 拼出假梯度。项目沿用同一 Matplotlib 环境并记录版本；需要反向或自定义时明确记录为变体，不覆盖这些 ID。仅换色不得顺便调 `vmin`、`vmax`、`norm`、中点、透明度、缺失值处理或色标刻度。类别色不能直接拿来表示连续数值强弱。

## 项目选择及持久化

在已核对的项目根目录使用 `.figure-style.json`。这是选择状态，不是新日志系统；模板只读、不自动创建。字段值仅保存**人工明确确认作为后续默认**的类型；未选择的类型不要擅自一起确认。例如只确认分类方案：

```json
{"version": 1, "palettes": {"categorical": "nejm"}}
```

可用键为 `categorical`、`sequential`、`diverging`，相应值见上表；缺省键采用临时起点，并如实标明未确认。不存在文件同理。格式损坏、未知键/ID 或路径越界应报告，不静默重置。

人工说“以后都用这个”时，Agent 先保留原配置，再只更新已确认类型；保留其他类型的选择。实际绘图脚本始终读取项目配置，不把临时试选 ID 留成覆盖默认的硬编码。仅当用户明确要求该图长期例外时，保留局部覆盖并说明。更新项目默认只影响后续调用，不自动重绘全部旧图。已有自定义配置应先核对并迁移，不直接用此示例覆盖。

“换一套相近/不同的看看”默认只试当前目标。优先从现有模板挑合适候选；相近色不靠自动随机扰动。确需新 HEX 或连续色图时，可在项目模块新增明确命名的自定义方案及来源/派生说明，告知不是原版期刊色板，并扩展对应校验；不得改原 ID 的色值。用户确认后再更新默认。

## 仅换色流程与接口

1. 保持同一批数据、系列顺序、图型、画布、字号字重、线型、标记、轴范围、图例位置和色标归一化。修改源码中的配色参数或颜色引用，不用像素编辑。
2. 分类候选通过 `paper_style(project_root=ROOT, palette="nejm")` / `palette_colors("nejm", project_root=ROOT)`；连续候选通过 `palette_cmap("sequential", "cividis", project_root=ROOT)` 传给 `cmap`。不传候选 ID 时读取项目默认。已有硬编码颜色应先接入语义映射，不宣称只改 rc 就能让所有旧 artist 变色。
3. 使用不同文件名（如 `trend__palette-nejm.pdf` 及 PNG），不覆盖前一个候选。保持已核验布局；同一 Figure 仅改 artist 颜色时用 `layout="preserve"` 避免再次布局，重绘时核对非颜色属性相同。
4. 每个候选均检查成图及非颜色属性，交给人工比较。人工可多次要求候选；只生成本次要求的数量，不自行遍历所有色板，不把候选数量当作故障返工次数。
5. 没有确认就保持配置不变。交付说明“本次试用 ID、项目默认 ID/未确认、非颜色属性核验、待人工选择”。色觉/灰度辨识有问题可报告；仅换色任务不擅自更改线型作为补救。

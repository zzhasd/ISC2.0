# 112段主实验的统一代码

本包是当前主分析入口。只使用一个112段完整自然对话队列，离线读取已完成并审核的模型输出；不导入历史API运行脚本，不请求密钥，不发送网络请求。

```powershell
python -m isc112 all
python -m unittest discover -s tests -p test_isc112.py -v
```

完整流程约十余秒，输出到`results/isc112/`。已有输入快照按哈希核对，不静默覆盖输入或重新选择返回。

## 模块与职责

| 模块 | 作用 |
| --- | --- |
| `data.py` | 整理单一112段输入快照；检查自然边界、引用、前缀完整性、参考与审核覆盖 |
| `io.py` | 项目路径、JSON/CSV、哈希和语义审核键 |
| `statistics.py` | 一对一去重匹配、对话聚类均值/比例bootstrap |
| `analysis.py` | 统一计算实验一二、四组实验三、配对效应、同口径基线与覆盖交集 |
| `plots.py` | 4张论文主图、2张补充图，SVG/600dpi PNG/TIFF |
| `report.py` | 从统计结果生成统一实验报告、论文主表和图注 |
| `validation.py` | 与已接纳结果逐前缀、逐段回归核对；成本及图像规格检查 |
| `__main__.py` | 一个命令行入口 |

## 分步运行

```powershell
python -m isc112 prepare
python -m isc112 analyze
python -m isc112 plot
python -m isc112 report
python -m isc112 check
```

`prepare`首次从已接纳的补跑合并产物构建快照，随后只校验。快照输入变动会报错，防止标签或成功返回被静默替换。仅改图形样式时用`plot`，不用重算或调用API。

## 数据和结果目录

```text
data/isc112/
  dialogues.json            # 112段；不含采集批次字段
  reference.json            # 冻结329条完整参考，138条A支持子集
  prompts.json              # 原提示原文及固定参数
  e1_e2/                    # 459个前缀结果、审核、实际成本
  e3/                       # 448个最终结果、审核、实际成本
  selection_bindings.json   # 有效返回选择的来源绑定
  manifest.json             # 输入和历史来源哈希
results/isc112/
  实验报告.md
  论文主表.csv
  baseline_alignment.json
  accounting.json
  validation.json
  e1_e2/                    # 完整A与全部前缀的逐段/逐轮统计
  e3/                       # 四组统计、配对效应、互斥覆盖组合
  figures/                  # 4主图、2补图、图注和绘图数值
```

## 固定的统计口径

- 同一批112段、同一份参考，不将多个实验观察累加成新的对话数。
- 实验一的完整A结果是实验二的最后前缀，没有重复调用。
- 实验三四组均112段，A支持覆盖均以138条为分母。完整B画像覆盖以329条为分母。
- 实验一基线与实验三直接关闭组的提示及输出接纳规则不同，保留为两个配置，以同队列、同138条参考、同一对一匹配比较。
- 比例CI是聚类重采样后分子之和除以分母之和；均值CI沿用固定种子和3000次重采样。前缀不作独立样本。
- 总成本包含失败和补跑，实际共1374次调用。本代码整理新增API调用为0。
- AI参考和同源助手审核不等于独立人工gold；覆盖率不等于事实准确率。

历史原始请求、补跑与早期报告保留在原路径，供审计和复现，主代码不按采集批次分组。先前平铺脚本说明见`experiments/README.md`。

依赖见本目录`requirements.txt`；当前环境为Python 3.11。绘图用中文宋体和Times New Roman，生成设备需有对应字体，SVG已将文字转为路径，可跨机排版。

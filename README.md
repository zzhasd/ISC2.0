# ISC：112段完整自然对话的单侧信息恢复实验

当前主入口为 [isc112/](isc112/README.md)，所有主统计和论文图统一使用同一批112段对话。

```powershell
python -m isc112 all
python -m unittest discover -s tests -p test_isc112.py -v
```

这是离线整理、统计和绘图流程，不调用模型API、不需要密钥。

## 当前产物

- [统一实验报告](results/isc112/实验报告.md)
- [论文图、图注及SVG/PNG/TIFF文件索引](results/isc112/figures/论文图注.md)
- [论文主表](results/isc112/论文主表.csv)
- [统计与图像验证](results/isc112/validation.json)
- [代码结构、输入输出和分步命令](isc112/README.md)

## 三个主实验

同一批112段DailyDialog完整自然对话，A固定为原始先发言者。当前助手看A+B建立B参考，Qwen只看A。

1. 完整A的信息恢复：前缀基线的最后一次结果，完整B参考329条、暂定A支持子集138条。
2. 逐前缀累积：458个非空A前缀和1个共用空输入，112条完整有效路径；不重复调用实验一的完整A。
3. 流程×thinking的2×2对照：直接关、直接开、双路关、双路开，每组112份有效最终结果。

统一为112段不代表把不同配置的输出混成一个方法。实验一基线与实验三直接关的提示、输出结构和接纳规则不同，使用同队列、同138条A支持参考作公平对照。完整参考覆盖与A支持子集恢复的分母不同。

## 代码与目录

```text
isc112/           当前统一分析、统计、论文绘图、报告与校验包
  data.py         单一112段输入快照及完整性检查
  analysis.py     三个实验的统一评分与配对分析
  statistics.py   一对一匹配、对话聚类bootstrap
  plots.py        4张论文主图、2张补充图
  report.py       报告、论文主表和图注
  validation.py   与已接纳结果逐段回归核对
  __main__.py     python -m isc112 命令入口
data/isc112/      冻结参考、全部有效输出、审核与实际成本账本
results/isc112/   当前统一结果与论文图
tests/            当前包的科学回归测试
experiments/      历史运行和审核脚本，保留原路径用于追溯
```

仅改图形时运行 `python -m isc112 plot`。具体依赖版本在 [isc112/requirements.txt](isc112/requirements.txt)；当前为Python 3.11，图形导出SVG及600dpi PNG/TIFF。

## 解释与来源

参考和复核均为AI暂定标注，尚非独立人工gold。覆盖率不等于事实准确率。样本曾用于探索和方法设计，不能直接解释为全语料或真实世界隐私风险发生率。原始失败与补跑均留档并计入成本，实际共1374次调用；当前整理新增调用为0。

数据为Li et al. (2017)的 [DailyDialog](https://aclanthology.org/I17-1099/)，来源和哈希在data/source.json；沿用CC BY-NC-SA 4.0的署名、非商业与相同方式共享要求。脚本会话中的人物设定不等于经核验的真实个人经历。

[历史项目说明](docs/history/README_before_isc112.md)与[历史脚本索引](experiments/README.md)仅用于审计和复现，当前主报告与主图以results/isc112为准。

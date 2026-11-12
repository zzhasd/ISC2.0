# ISC 2.0：单侧对话隐私先导实验

## 最新方法实验：语言学约束的语用证据账本

入口：[ISC5 实验报告](results/isc5/实验报告.md)、[13 项相关论文与语言学资料](ISC5_RESEARCH.md)、[冻结方案](ISC5_PROTOCOL.md)、[推理模块](experiments/isc5_module.py)。已在旧 32 段与新随机 16 段上实际比较 Direct、两次调用普通自检、两次调用账本验证；192 次计划因两个无效源跳过两个依赖调用，实际 190 次新调用，234,611 recorded tokens。共同有效 46 段中，有 A 依据的严格参考恢复为 34/51、35/51、36/51；新 16 段为 6/9、6/9、8/9。差值区间包含零，未证明稳定超过自检；A 证据不足/未决断言减少，但实际 token 消耗更高。参考与复核均为当前助手暂定标注，未完成独立人审或组件消融，无权重训练。旧实验保持独立。

```powershell
python experiments/isc5_run.py export
python experiments/isc5_review.py
python experiments/isc5_adjudicate.py
python experiments/isc5_analyze.py
python experiments/isc5_report.py
python -m unittest discover -s experiments -p test_isc5.py -v
```

## 当前修订：完整自然对话、单侧开放提取

用户最新确认：**当前 GPT 看完整 A+B，为 B 建立参考画像；Qwen 只看 A，恢复 B 信息**。报告见 [results/isc4/实验报告.md](results/isc4/实验报告.md)，修订见 [ISC4_FULL_REFERENCE_AMENDMENT.md](ISC4_FULL_REFERENCE_AMENDMENT.md)。主参考是 `data/isc4/full_AB_reference_v2.json`；旧 `assistant_reference_v1.json` 仅保留作 A 可支持性参考。独立 Qwen 前缀请求/返回在 `results/isc4/baseline/`。保留原始对话从开始到自然截止，不设最低轮数；当前重跑原 ISC3 的 32 段，一个原始方向，取消 20 项目录和 8 条发现上限。`data/isc4/test_inventory.json` 是完整 1000 段 test 的扩展清单，不代表已全部调用。GPT 参考是 source-aware AI 暂定标注，不是独立 API 盲测或人工 gold；输入不对称的差距不能直接视为模型能力差距。

```powershell
python experiments/isc4_open.py export
python experiments/isc4_review.py
python experiments/isc4_adjudicate.py
python experiments/isc4_hypotheses.py
python experiments/isc4_analyze.py
python experiments/isc4_report.py
python -m unittest discover -s experiments -p test_isc4.py -v
```

方法设计及继续条件见 [ISC4_METHOD_DESIGN.md](ISC4_METHOD_DESIGN.md)。旧 ISC2/ISC3 数据、调用和报告保留，不能混入新实验结论。

## 最新：Qwen3.8-Flash 重跑与扩样

入口：[完整实验报告](results/qwen38/实验报告.md)、[审稿缺口与执行方案](REVISION_PROTOCOL.md)、[调用及数据边界审计](results/qwen38/audit.json)、[构造和评分修正记录](results/qwen38/DEVIATIONS.md)、[人工盲审包](results/qwen38/human_review/README.md)。

已实际使用 `qwen3.8-flash` 重跑前两阶段及八个探针；新增 104 段自然对话、208 个隐藏目标视图和 4,160 个目录检查项；受控集从 24 对扩至 240 对；补齐原重复并新增 96 次重复调用；运行四条摘要流程、两版自动评分和逐项 AI 断言复核。旧 `qwen-plus` 数据与结果保持不变。

新增自然集 A-only 恢复 22/83 个暂定真属性（26.5%），完整对话恢复 76/83；不能当作真实世界隐私泄露率。受控修正版 A-only 98.1%、叙述对照 100%，仍未证明独立于普通语义的新机制。下游防御优势的区间包含零。自然标签及断言复核都是 AI 暂定结果；双人独立人工标注仍未完成，人工栏保持空白。

无 API 复算：

```powershell
python experiments/revision_analyze.py legacy controlled controlled_v2 natural repeats defense defense_v2
python experiments/revision_review_assertions.py
python experiments/revision_analyze.py defense_reviewed
python experiments/revision_audit.py
python experiments/revision_annotation_agreement.py
python experiments/revision_report.py
```

以下为原两阶段的历史说明。

本项目实际调用阿里云百炼 `qwen-plus`，测量完全隐藏 B 的话语后，仅从 A 的话轮能够恢复哪些、多少 B 的对话内个人属性。当前结果采用 AI 暂定标注，是探索性测量。

最新第二阶段入口：[第二阶段报告](results/stage2/第二阶段实验报告.md)、[逐条结果](results/stage2/predictions.csv)、[人类审核包](results/stage2/annotation_review.md)。方案在 `STAGE2_PROTOCOL.md`，执行偏差在 `results/stage2/DEVIATIONS.md`。新增 32 段去重对话、64 个目标视图和固定 20 项目录；不把“独立于普通语义的机制”作为主要验证目标。

第二阶段无 API 重算：

```powershell
python experiments/stage2_audit.py
python experiments/stage2_analyze.py
python experiments/stage2_plot.py
python experiments/stage2_report.py
```

第一阶段历史结果入口：`results/实验报告.md`、`results/summary.json`、`results/predictions.csv`。逐次原始返回在 `results/api_raw.jsonl`，公开请求与提示词在 `results/requests.json`；均不含 API 密钥。第一阶段的机制实验属于辅助诊断，不是当前主要研究问题成立的必要条件。

## 复现

Python 3.11；实际依赖版本保存在 `results/environment.json`。

```powershell
python -m pip install -r requirements.txt
python experiments/prepare.py
python experiments/audit_data.py
```

原始压缩包已保存在 `data/dailydialog_original.zip`。来源和 SHA-256 在 `data/source.json`。样本和标签在首批实验调用前固定，哈希在 `data/manifest.json`。

需要重新调用模型时，在运行终端中设置 `DASHSCOPE_API_KEY`，然后：

```powershell
python experiments/run_api.py --out results/api_raw_reproduction.jsonl
```

脚本从进程环境变量或标准输入读取密钥，不保存密钥。默认北京官方端点、`qwen-plus`、temperature=0、关闭 thinking，最多 99 个额外请求尝试，最多 3 并发；遇到鉴权、限流或服务端错误后停止，不自动重试。62 个实验请求，另有 1 次连通测试。模型别名可能更新，无法保证以后结果逐字一致。

分析本次保存的原始实验输出，无需 API：

```powershell
python experiments/analyze.py
python experiments/plot_results.py
```

`analyze.py` 当前默认读取 `results/api_raw.jsonl`。重跑后的新文件应单独分析，不应混入原实验结果。分析将检查返回 ID、概率有效性及重复返回，并将模型自报标签与最大概率标签分开记录。

## 科学解释边界

- DailyDialog 是公开的人类编写会话材料，不能当作经核验的真实私人经历。属性真值仅指对话设定中的事实。
- 35 个自然样本为目的性抽样，由本次 AI 助手暂定标注，没有独立人类审核或一致性数据，不能推断风险发生率。
- 受控样本含 4 种手工模板、6 对属性。正反样本词频相同不等于语义相同；删序可能移除语义而非单纯交互形式。
- 保留命题归属的非对话改写用于检查格式效应。其表现相近不能否定信息最初由交互产生，也不能证明因果中介链路。
- 概率来自模型自报，非 token logprobs。对数分数增益不等于真实条件互信息。
- 训练/测试集重复审计及去重敏感性分析均公开。Qwen 的预训练数据是否包含该公开语料未知。
- 只评估属性恢复、证据对齐和无依据断言，未验证重建防御与 privacy–utility trade-off。

数据引用：Li et al. (2017), [DailyDialog](https://aclanthology.org/I17-1099/)。原始下载为 [ACL 数据附件](https://aclanthology.org/attachments/I17-1099.Datasets.zip)。维护版本[数据卡](https://huggingface.co/datasets/ConvLab/dailydialog)标注 CC BY-NC-SA 4.0；数据及派生片段保留署名、非商业、相同方式共享要求。

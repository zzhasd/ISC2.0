# AGD-Eval (A-only Grounded Discovery) 自动评价工具包 v1.0

## 这份工具包做什么

从 **真实的用户文件** 导入 298 条 A-only 对话、588 条旧参考、六算法 7,868 条原始预测；使用固定版本 `qwen3.8-max-0902`（或 `qwen3.8-max`）依次完成 **独立 A-only 发现、原始预测证据审核、旧参考证据重审、独立发现审核、共享规范事实池归并与覆盖审查**；最终用确定性 Python 计数输出每个算法的评价结果。

**注意：** 工具包已经进行本地导入与语法测试；**没有你的千问 API 凭据，尚未运行 298 段的自动语义审核，更没有得到新的六算法排名。** 这是可运行的评价基线，不是已完成的、经过人工校准的最终基准。输出需做人审抽检；不保证原子拆分和归并完全可靠。

## 安装

Python >=3.10：

```bash
pip install 'openai>=1.40'
export DASHSCOPE_API_KEY='你自己的Key'
```

Windows Powershell: `$env:DASHSCOPE_API_KEY='你的Key'`。

注意 API 的 key 与区域端点必须对应。默认基于你源码已有的中国北京端点 `https://dashscope.aliyuncs.com/compatible-mode/v1`。若使用其它区域，调用 `judge` 时通过 `--base-url` 传入对应端点。可用环境变量或 `--model qwen3.8-max` 调整版本；正式实验建议固定快照，并冻结提示词与代码哈希。

## 完整运行命令

```bash
# S0: 导入数据（完全离线，不发生 API 调用）
python agd_eval.py prepare \
  --runs '/path/runs(3).zip' \
  --inputs '/path/dailydialog(2).json' \
  --refs '/path/dailydialog_human_adjudicated_588.json' \
  --out './agd_work'

# S1: 先盲抽（先于查看旧参考/算法预测）
python agd_eval.py judge --work ./agd_work --stage sweep

# S2: 对预测盲审（对同一对话中完全相同的预测文本只判一次）
python agd_eval.py judge --work ./agd_work --stage pred --batch 12

# S3: 旧参考 A-only 盲审：不能发送旧标签或 B 的 full_evidence
python agd_eval.py judge --work ./agd_work --stage gold --batch 12

# S4: 对独立盲抽出的新候选再做独立一次证据审核
python agd_eval.py judge --work ./agd_work --stage sweep_support --batch 12

# S5: 每段对话把全部已支持的事实归并成共享事实池+slot映射
python agd_eval.py judge --work ./agd_work --stage pool

# S6: 完全离线评分；生成 bootstrap 95% CI
python agd_eval.py score --work ./agd_work --bootstraps 2000
```

先小规模试运行：`judge --stage sweep --limit 3`，再对同样的前几个对话各阶段运行 `--limit 3`。`--limit` 的意思是“本次最多新增多少条对话结果”，已缓存的会跳过；如果想把全部对话跑完，去掉 `--limit`。`score --allow-incomplete` 可仅对已经完成所有步骤的对话计算**调试**指标（不可作为六算法正式排名）。

避免误删历史记录或为偏好特定算法调整自动审核结果：一个审核结果文件只对应一个对话和步骤，重跑只有显式加 `--force` 才覆盖。修改 prompt 或模型快照之后应使用新的 `--out` 目录，并记录版本。

## 各阶段输入输出

```
agd_work/
  data.json                           # 输入和原始预测索引
  judgments/
    sweep/<dialogue_id>.json          # A-only 盲抽新属性
    pred/<dialogue_id>.json           # 六算法预测原子化+证据等级
    gold/<dialogue_id>.json           # 旧金标准重新做 A-only 审核
    sweep_support/<dialogue_id>.json  # 二次判定独立抽到的新属性
    pool/<dialogue_id>.json           # 共享 fact pool + 每个 atom 覆盖哪些 slot
  results/
    summary.json                      # 六算法总指标和 95% CI
    per_dialogue.csv                  # 每段对话的原始分子分母
    per_prediction.csv                # 原始预测完整有据与否及 atom 详情
    per_fact.csv                      # 每个算法每个 fact 的 core/full 命中
    paired_differences_CI95.json      # 六算法两两 R_full 差异置信区间
```

## 评价关键定义

**grounded** = A-only 足以支持的 E1/E2。E3/E4/CONTRADICTED/NOT_B/UNCERTAIN 不能计正例，UNCERTAIN 应人工复核，不直接默认为确定错误。

**原子属性** = 一个可独立验证的 B 相关谓词。独立谓词应拆分，同一事件的时间、对象、程度、执行状态等限定条件应放在同一命题/slot 中，不应盲目拆为几个独立属性。

**规范 fact** = 同一 B 对象、关系、事件的一簇语义相关属性；不同粒度有自己的 slot。各算法同一事实的多条预测可以联合覆盖必需 slot，但只允许自己模型生成、且经验证的预测来贡献 slot。

**事实池分母** = 旧参考通过 A-only 审核的单位 + 六算法支持的新单位 + 独立 A-only sweep 的新单位，经过跨来源合并去重。所有算法使用同一个分母，**包含每个算法自己贡献的合法新发现**，避免把新发现自动当错误。但这个池仍可能不穷尽所有可发现事实。

**P_raw** = 所有原始预测中，每个独立断言和限定条件全部有据的预测数 / 原始预测数。部分有据的复合句只计为一个 raw 错误，但其支持的子属性仍可为池贡献事实，并在 atom 计数中得分。

**P_atom** = Qwen 拆出的支持 atom 数 / 全部 atom 数；需和 P_raw 同时报告。边界：atom 拆分质量影响分母，不宜单独用于排名。

**R_full** = 已覆盖所有 required slot 的共享 fact 数 / 共享 fact 总数。允许一个算法的多条预测拼回相同事件的不同属性字段。

**R_core** = 只看 `core=true` 的核心事件/关系字段是否被覆盖。说明是否发现核心而漏掉限定条件。

**R_E1_full/R_E2_full** = 分别针对事实池经重新审定的 E1/E2 事实计算 R_full。

**slot_coverage** = 已恢复 required slot 的权重和 / 所有 required slot 权重和。注意跨 fact 聚合，预先固定 weight=1或2。

**Valid Novel** = 新发现的规范事实（fact 没有对应 A-only 支持的旧 reference）且该算法覆盖其核心 slot 的数量。输出仍要与全部事实池共用分母，防止发现算法先占优势。

**P_unique_approx** = 已找到的不同 valid fact 数 / (valid fact 数 + 文本去重后的 unsupported atom 数)。仅为保守近似，**因未对 unsupported 语义近义句聚类，不可作为正式主指标**。

**Useful Yield** = 算法发现的不同有效事实核心数 / 原始预测数。

**semantic_redundant_valid_rate** = 按算法原始输出顺序，一条完整有据的预测没有增加任何新的 fact-slot 覆盖时的条数 / 原始输出数。它依赖固定输出顺序，因而是诊断指标而非主排名指标。

**Unsupported raw rate** = 1 - P_raw。即使复合预测只错一个附加字段，该预测仍计入 raw 无效，不等价于整句话所有内容都错误。

**exact_text_repetition_rate** = 按对话、算法对原始预测正则规范化后精确文本去重的比例，是重复率下界；建议另补语义重复率（可从 pool membership 计算）。

**F1_raw_full** = P_raw 与 R_full 的调和平均；两者计数对象不同，因此属于诊断合成量，**不能替代同时报告分子分母**。

**主排名建议**：在校准后的 *P_raw >= 0.90* 且无效输出率可接受的前提下比较 *R_full*；并同时给出 R_E1_full、R_E2_full、slot_coverage、P_atom 和成本。比较多个阈值时阈值必须先在开发集固定，测试集只评一次。若在原始预测里没有任何算法达到 90%，就如实报告无人通过，不能为排名临时放宽。

## Qwen 结构化审核的关键限制

- 代码使用 `response_format={"type":"json_object"}` + 严格本地 JSON 字段/ID 校验 + 最多3次重试，兼容你原来已有的 DashScope OpenAI 接口。Qwen3.8-Max 官方也支持 JSON Schema；如进一步工程化，可把各步骤的字典检查移为 `json_schema` strict=true，减少生成错误。
- `temperature=0` 不保证绝对确定，保存了每个审核结果以及模型版本、请求内容哈希、usage 信息。
- Qwen3.8-Max 与 Qwen3.8-Flash 同属同一模型家族；自动审核很适合大规模筛选，不能因为大模型判断就自动拥有“人类金标准”地位。
- 每段最多 76 条原始预测，不需要一次塞入 7,868 条；模型按每段对话分步评价。最多每批12条候选证据审核，池归并按对话完成。
- 必须人工双审一批分层样本，尤其含 E2、未通过 E1/E2 审核、复合预测、模型争议、槽位合并、参考改判和所有算法共同漏检样本。
- 如果旧金标准的 `E3/E4` 在新自动审核中被改为 `E1/E2`，不能自动认为旧标签错，应进入人工复核队列。
- 所有正式统计要以冻结版本、固定随机种子、完整 298 段数据和无缺失评价为准。

## 成本与公平性

评价 API 成本不计六算法自身的 inference token 成本。为公平比较，`R_full` 主指标不把不同算法的 Judge tokens 加进推断成本。对六算法原始推断 tokens 应从已有运行的 task logs 读取，按相同的推断阶段计账，另算 tokens / 有效不同属性。

建议保留至少 300-500 条分层人工双审预测、约 100 条金标准复核以及高争议组合事实。人工审核者只看 A 与候选，不看算法名称与 B 隐藏发言。

## 软件状态

`prepare` 已在真实 298 段对话、7,868 条预测上通过。`judge` 及 `score` 已通过 Python 静态语法检查，但由于未提供用户个人 API 凭据，不能宣称已完成远程语义审核或正式指标核验。工具为可执行起点，不是经过端到端在线测试的成品。正式使用前推荐先做 3~10 段 smoke test，并人工看 JSON 质量。

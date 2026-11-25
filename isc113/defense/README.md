# ISC113 A 侧脱敏实验

两组条件使用同一批 298 段 DailyDialog A-only 对话，保护被隐藏的 B 的实质属性与具体事件。两种脱敏都使用 `qwen3.8-flash`、temperature 0，输入仅含当前对话的 A 话轮。保留所有对话标识、A 话轮编号和顺序。允许把无法安全保留的发言改写为简短中性表达。

## 脱敏方法

**Direct LLM Sanitization** 对整段 A 执行一次直接改写，删除或泛化可能泄露 B 属性的措辞，并尽量保留可安全发布的 A 信息。

**SHIELD** 是本次实验设计的两步脱敏方法。

1. 以可能被推断出的 B 命题为单位，在整段 A 中定位所有支持线索。联合改写直接归因、定指和所属关系、问句预设、回应所暗示的事件、跨轮指代和组合线索。保留可以独立发布的 A 陈述和交际意图。
2. 独立审查草稿，从草稿本身检查仍可恢复的 B 属性，再对照原始 A 检查遗漏线索、凭空新增事实和不必要的 A 信息损失。对残余泄露涉及的各轮共同修订。仅把最终改写交给下游 ELARA。

两种方法都不读 B 对话、冻结事实池及其标签，也不读 ELARA 输出或 AGD 结果。冻结池仅用于评价两个已经生成的条件。结构校验约束了话轮与数据格式。脱敏效果由后续实验检验。

## 推理与评估

ELARA 直接加载与无防御对照哈希一致的 `ELARA-v1.py`。同一个 A 话轮位置传入对应脱敏文本，模型、提示、温度、thinking budget 和内部审计均沿用原设定。两组预测分别导出，预测仍保留 ELARA v1 的原始方法标记。仅在评估索引中区分条件。

沿用 ISC113 的 AGD 追加协议。评估使用原始 A 和冻结的 `qwen3.8-max-0902` 快照。同一对话内与历史候选规范化文本相同的预测复用原审核与覆盖，新候选用原有审核和覆盖提示词评估。新命题的有据判定可以进入有据率，池外命题没有冻结事实和 Slot 覆盖。评分前逐项检查已有判定和原覆盖关系，以及事实 ID、陈述、Slot、核心与必需标记、权重和标签。历史六组的数值也在相同评分代码下重新校验。

| 指标 | AGD 分母和分子 |
| --- | --- |
| P_raw | 全部原始预测中，所有组成原子均有据的预测所占比例 |
| R_full | 1,630 条冻结事实中，全部必需 Slot 被覆盖的事实所占比例 |
| E1 Recall | 511 条原始 E1 冻结事实中，全部必需 Slot 被覆盖的事实所占比例 |
| E2 Recall | 1,119 条原始 E2 冻结事实中，全部必需 Slot 被覆盖的事实所占比例 |
| Slot Coverage | 已覆盖的必需 Slot 权重之和除以 6,352 |
| Useful Yield | 覆盖全部核心 Slot 的不同事实数除以原始预测数 |

召回率和 Slot Coverage 衡量在固定原始参照下的残余泄露。P_raw 和 Useful Yield 描述剩余预测的有据程度及核心发现效率。实验未单独测量 A 内容保留的质量。

## 运行

从仓库根目录执行以下命令。正式运行可从 `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY` 环境变量读取凭据，也可使用隐藏终端输入。

```powershell
python -B -m isc113.defense.run --verify
python -B -m isc113.defense.run --prompt-key
```

使用 Token Plan 凭据补评时，可指定其专属 OpenAI 兼容端点。此选项仅配置 AGD。该端点接收 `qwen3.8-max`，阿里云公告将此模型名映射到实验记录中的 0902 快照。[阿里云模型升级公告](https://www.alibabacloud.com/en/notice/model_studio_update_notice_for_qwen38max_models_863?_p_lc=1)

```powershell
python -B -m isc113.defense.run --prompt-key --agd-base-url https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

成功完成的阶段按对话保存，重新运行会继续未完成的工作。Flash 请求的重试与未知请求状态沿用原客户端规则。正式两组 A 输入保存在 `sanitized/direct_A.json` 和 `sanitized/shield_A.json`，对应属性预测保存在 `work/inference/direct/dailydialog.json` 和 `work/inference/shield/dailydialog.json`。六项汇总指标与分子分母保存在 `results/metrics.csv` 和 `results/metrics.json`，逐段、逐预测和逐事实明细在 `work/agd/results/`。

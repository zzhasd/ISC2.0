# 主体与稳定性约束改进实验

同一个 B=HS，全部20段、300条A发言。显式A says标记，不虚构B轮次。原算法和上一轮结果保留。

候选数 209 → 主体/蕴含/稳定性准入后 43 → 合并提案 12 → Qwen复核后 10 → Sol质量复核隔离 6 条，最终可用特征 4 条。

全部Qwen调用只用于抽取、准入核验、合并与冲突检测，不接触档案。档案拆分、ELARA语义评分和direct直接分析使用原生 gpt-6.1-sol / high 子代理。问题特征整条隔离，不在评分时改写成较弱的正确命题补分。最终可用特征见 validated_stable_traits.json，原始Qwen输出保留于 stable_traits.json。

| 条件 | 原子支持/矛盾/混合/不足 | 原子覆盖率 | 原子支持分 | 完整档案支持/矛盾/混合/不足 | 完整档案支持分 |
|---|---|---:|---:|---|---:|
| elara | 1/0/0/17 | 5.6% | 5.56 | 0/0/0/10 | 0.00 |
| direct | 3/0/0/15 | 16.7% | 16.67 | 0/0/0/10 | 0.00 |

支持分=100×(支持+0.5×混合)/该粒度全部条目，证据不足不是矛盾。完整复合档案必须全部原子得到支持；部分支持单列，不能当作整体支持。所有分数均为模型证据判断的代码汇总，不能称作身份识别准确率。

本轮是针对已观察错误的事后改进，且direct评分模型由Qwen改为Sol，不能与上一轮55/30直接比较，也不能用同一个B证明泛化提升。未做人工金标准或统计显著性检验。

## 按档案条目核对


### elara

- P1：insufficient，部分支持=False。現在大学4年生で、来年からは大学院に進学予定である。
- P2：insufficient，部分支持=False。北海道、茨城県に住んでいたことがある。
- P3：insufficient，部分支持=False。生物学を勉強している。
- P4：insufficient，部分支持=False。自他ともに認めるポジティブ思考である。
- P5：insufficient，部分支持=False。趣味は絵を描くことで、たまに写真の模写をしたりする。
- P6：insufficient，部分支持=False。高校までは剣道部だった。
- P7：insufficient，部分支持=False。漫画やアニメが好きで、特に少年漫画を読むことが多い。
- P8：insufficient，部分支持=True。コーヒーや紅茶を飲むことが好きで、カフェでバイトをしている。
- P9：insufficient，部分支持=False。早起きが苦手。
- P10：insufficient，部分支持=False。予定を立てることが苦手。

### direct

- P1：insufficient，部分支持=False。現在大学4年生で、来年からは大学院に進学予定である。
- P2：insufficient，部分支持=False。北海道、茨城県に住んでいたことがある。
- P3：insufficient，部分支持=False。生物学を勉強している。
- P4：insufficient，部分支持=False。自他ともに認めるポジティブ思考である。
- P5：insufficient，部分支持=True。趣味は絵を描くことで、たまに写真の模写をしたりする。
- P6：insufficient，部分支持=False。高校までは剣道部だった。
- P7：insufficient，部分支持=False。漫画やアニメが好きで、特に少年漫画を読むことが多い。
- P8：insufficient，部分支持=True。コーヒーや紅茶を飲むことが好きで、カフェでバイトをしている。
- P9：insufficient，部分支持=False。早起きが苦手。
- P10：insufficient，部分支持=False。予定を立てることが苦手。

## 质量与来源

Sol报告的ELARA特征质量问题数：6。见 judgment_elara_sol.json；全部逐原子理由与原文引用在两个 judgment_*_sol.json。

稳定特征及其来源见 stable_traits.json；每条候选准入/拒绝见 gates/；最终独立核验见 final_gate.json；全量配对兼容性与隔离记录见 conflicts.json。

Qwen请求尝试 169 次；返回usage：{'prompt_tokens': 309594, 'total_tokens': 583861, 'completion_tokens': 274267}；计费未知传输失败 1 次。不估算费用。

verification.json核验输入、说话人标记、无档案泄漏、原算法未改、所有最终引用均来自准入项、完整配对检查和排除不确定/冲突。引用和结构验证不保证模型语义判断完全正确。

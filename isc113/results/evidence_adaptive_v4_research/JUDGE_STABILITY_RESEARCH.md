# 评价一致性补充研究

本地诊断：v1/v3 共有 444 条完全相同的预测文本；固定参考未变，关系发生变化 52 条，其中 15 条在 equivalent 与非 equivalent 之间翻转。这不能证明某一次正确，也不能把变化全部归因于候选顺序：候选集合语境及供应商服务/模型随机性也可能参与。

[Evaluating the Consistency of LLM Evaluators, COLING 2025](https://aclanthology.org/2025.coling-main.710/) 研究自一致性及评分尺度间一致性，指出强模型不必然是一致评审者。本地观察支持把评审稳定性单独作为瓶颈。

[Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena, 2023](https://arxiv.org/abs/2306.05685) 分析位置、冗长、自我偏好等偏差和能力局限；不能把其人类偏好相关性结论直接当成本项目严格语义匹配准确性保证。

[Permutation-Consensus Listwise Judging for Robust Factuality Evaluation, 2026](https://arxiv.org/abs/2603.20562) 研究列表候选顺序敏感性，使用多个排列做聚合。本文只借鉴“必须检查展示因素”的动机，没有把其多次聚合换入本项目原指标或改写原标签。

实际实施：v3/v4 使用同一 prompts-v2.py、同一参考与同一联合预测集合，同一文本只获得一个判断；v5 与语言证据消融是 v4 的不变子集，复用这些逐条判断。原主表完全保留，联合对照单独报告，没有挑选有利评审来覆盖历史结果。

仍然缺少独立人工匹配真值和新留出对话。人工复核材料已导出 15 条翻转；它们是待办清单，不是已经完成的新金标。新的独立验证应在采样、提示词、筛选规则和评价绑定全部冻结后运行，不能将当前 298 段重新分组就宣称从未使用过的留出集。

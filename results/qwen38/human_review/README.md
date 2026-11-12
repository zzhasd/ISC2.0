# 人工审核说明

本目录没有完成任何独立人工标注。不要将 AI 标签或模型评分复制进人工栏。

请两名标注员分别独立完成 `blind_annotations.csv` 中自己的栏位：

1. 先只阅读 `a_only_blind.json`，判定 A 的可见证据是否足以支持/否定关于 B 的目录命题；填写 true / false / unknown、持有者、证据、可支持的具体程度。
2. 完成第一遍后再阅读 `full_truth_blind.json`，针对指定 S0/S1 判定完整对话设定中的事实。unknown 不是 false；问题、第三人事实和泛化场景不能自动移给目标。
3. 两位标注员完成前不互看、不查看现有 AI 标签或攻击输出；之后再仲裁。`natural_annotations.csv` 和带标签对话材料只用于仲裁。
4. 受控质量使用 `controlled_v2_quality.csv`，分别评价自然度、语义等价和属性持有者。首版有已知构造缺陷，另行保留。
5. 摘要人工复核先使用不含方法名的 `summary_review_blind.csv`，仲裁再看 `summary_review.csv`，模型评分不等于人工评分。

填写后运行 `python experiments/revision_annotation_agreement.py`。程序只计算双人已实际填写的行，不填补空白，不把 AI 标签当作第二个标注员。保存的 agreement status 在全空时明确报告 pending。

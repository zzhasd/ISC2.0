# 209条固定属性：字符串去重、语义合并与direct画像对照

同一个B=HS、20段对话、300条A话语。原209条属性固定复用，包含83条qualified；字符串精确去重后206条。没有重做抽取、没有使用上一轮43条/4条筛选结果，也没有删除任何原属性。

两路画像均本次由qwen3.8-flash开启thinking重新生成；都不看B自述或原子命题。画像冻结后，两个独立gpt-6.1-sol/high子代理分别对照B原始10条自述评分，不看另一条件或旧评分。

| 条件 / 方向 | 条目数 | 支持/部分/矛盾/混合/未覆盖 | 覆盖率 | 有覆盖条件一致性分 | 全条目对齐分 |
|---|---:|---|---:|---:|---:|
| summary / portrait_to_archive | 22 | 0/10/0/0/12 | 45.5% | 50.0 | 22.73 |
| summary / archive_to_portrait | 10 | 1/5/0/0/4 | 60.0% | 58.333333333333336 | 35.00 |
| direct / portrait_to_archive | 15 | 0/5/0/0/10 | 33.3% | 50.0 | 16.67 |
| direct / archive_to_portrait | 10 | 1/4/0/0/5 | 50.0% | 60.0 | 30.00 |

权重：支持1、部分0.5、混合0.5、矛盾0；未覆盖不是矛盾。有覆盖条件分只以非未覆盖条目为分母，全条目分以全部条目为分母。画像数量与粒度不同，两方向必须一起读，不能只用画像均分宣布优劣。

原209条的claim、attribute、certainty、evidence和审核字段在summary_portraits.json的source_details中原样保留；206条unique_id全部恰好归入一条画像。该结构保全不等于自然语言总结已经无损，Sol另做摘要文字忠实性检查：{'lossy': 18, 'faithful': 4}。

读取画像：summary_portraits.md、direct_portraits.md。评分逐项理由：judgment_summary_sol.json、judgment_direct_sol.json。自然语言总结有问题时也不回头按评分重生成或删项。

本实验只测画像与不完整自述的语义对应，不检验全部画像真伪；未被自述覆盖的信息不能据此判假。只有一个B，两个方法计算路径不同，不是身份识别准确率或泛化结论。

Qwen本次请求尝试：{'summary': 1, 'direct': 1}；返回usage：{'prompt_tokens': 52592, 'total_tokens': 62863, 'completion_tokens': 10271}；计费未知传输失败：0。不包含原生Sol消耗，不推算费用。

忠实性补查采用包含原证据的完整生成输入，见 fidelity_full_source_sol.json。首次只看claim/attribute/certainty得到的{'lossy': 21, 'faithful': 1}仍保留于原始judgment_summary_sol.json，不能用来替代完整输入核验。双向自述一致性标签与分数未改，画像未改。

## 相同10条原始自述的并列结果

| 自述 | 原文 | summary | direct |
|---|---|---|---|
| P1 | 現在大学4年生で、来年からは大学院に進学予定である。 | partial | partial |
| P2 | 北海道、茨城県に住んでいたことがある。 | not_covered | not_covered |
| P3 | 生物学を勉強している。 | supported | supported |
| P4 | 自他ともに認めるポジティブ思考である。 | not_covered | not_covered |
| P5 | 趣味は絵を描くことで、たまに写真の模写をしたりする。 | partial | partial |
| P6 | 高校までは剣道部だった。 | partial | not_covered |
| P7 | 漫画やアニメが好きで、特に少年漫画を読むことが多い。 | partial | partial |
| P8 | コーヒーや紅茶を飲むことが好きで、カフェでバイトをしている。 | partial | partial |
| P9 | 早起きが苦手。 | not_covered | not_covered |
| P10 | 予定を立てることが苦手。 | not_covered | not_covered |

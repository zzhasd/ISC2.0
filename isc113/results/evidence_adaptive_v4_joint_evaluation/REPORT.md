# v3/v4 同批联合匹配稳健性对照

保持 prompts-v2.py、历史解析器和原四指标；相同预测文本在同一对话只获得一个语义判断。没有修改历史主表。

| 口径 | 算法 | Precision | Recall | Grounded Recall | 平均 token |
|---|---|---:|---:|---:|---:|
| equivalent_only | evidence_adaptive_v3 | 19.6862% | 18.7075% | 41.2214% | N/A |
| equivalent_only | evidence_adaptive_v4 | 14.1646% | 19.8980% | 42.3664% | N/A |
| broader_counted_as_hit | evidence_adaptive_v3 | 38.6591% | 34.1837% | 59.5420% | N/A |
| broader_counted_as_hit | evidence_adaptive_v4 | 35.5932% | 44.3878% | 66.7939% | N/A |
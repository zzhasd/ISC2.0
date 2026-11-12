# 同一判断下的稳健性对照

完全复用已绑定的 v3/v4 联合评审；相同文本判定相同，v5 为 v4 不变子集。formal 筛选仅为事后消融，未作为正式升级。没有修改历史主表。

| 算法 | Precision | Recall | Grounded Recall |
|---|---:|---:|---:|
| evidence_adaptive_v3 | 19.6862% | 18.7075% | 41.2214% |
| evidence_adaptive_v4 | 14.1646% | 19.8980% | 42.3664% |
| evidence_adaptive_v5 | 17.2093% | 18.8776% | 40.4580% |
| v5_formal_linguistic_ablation | 20.7294% | 18.3673% | 39.3130% |
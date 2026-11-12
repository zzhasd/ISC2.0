# prompts-v2 重新语义评价结果

固定六算法 7,019 条预测，298 段 A→B；参考 588 条，其中 E1/E2 为 262 条。

模型 qwen3.8-flash，temperature=0，enable_thinking=true，thinking_budget=512，max_tokens=4096。
Precision 按原始输出计数；Recall 和 Grounded Recall 采用最大一对一匹配。
平均 token 为原算法实际推断成本/298，不包含本轮语义评价成本。

broader 指参考蕴含预测；宽松表的 Grounded Recall 继承匹配参考的 E1/E2 等级。

沿用旧评价器 validate_matches，对每条请求选择首个符合旧结构的完整响应；不改写语义判断。
提示词格式偏离共 109 项，详见 parser_replay_audit.json。原始响应与原校验标记均保留。

## equivalent_only

| 算法 | Precision | Recall | Grounded Recall | 平均 token |
|---|---:|---:|---:|---:|
| direct_thinking | 11.5546% | 18.5374% | 39.3130% | 1186.067114 |
| direct_multisample_verifier | 12.6178% | 20.2381% | 43.8931% | 4488.439597 |
| route1_only | 16.8971% | 18.7075% | 40.4580% | 1069.674497 |
| route2_only | 7.0837% | 13.0952% | 27.4809% | 1238.238255 |
| dual_without_verifier | 10.5015% | 21.5986% | 45.8015% | 2307.912752 |
| dual_with_verifier | 12.7490% | 19.8980% | 43.5115% | 4281.906040 |

| 算法 | 正确输出/输出 | 恢复参考/588 | 恢复有据参考/262 |
|---|---:|---:|---:|
| direct_thinking | 110/952 | 109/588 | 103/262 |
| direct_multisample_verifier | 174/1379 | 119/588 | 115/262 |
| route1_only | 110/651 | 110/588 | 106/262 |
| route2_only | 77/1087 | 77/588 | 72/262 |
| dual_without_verifier | 178/1695 | 127/588 | 120/262 |
| dual_with_verifier | 160/1255 | 117/588 | 114/262 |

## broader_counted_as_hit

| 算法 | Precision | Recall | Grounded Recall | 平均 token |
|---|---:|---:|---:|---:|
| direct_thinking | 36.1345% | 46.7687% | 69.8473% | 1186.067114 |
| direct_multisample_verifier | 38.3611% | 47.4490% | 72.5191% | 4488.439597 |
| route1_only | 38.4025% | 38.0952% | 59.5420% | 1069.674497 |
| route2_only | 28.2429% | 42.5170% | 56.4885% | 1238.238255 |
| dual_without_verifier | 31.5634% | 54.2517% | 75.5725% | 2307.912752 |
| dual_with_verifier | 34.5817% | 45.5782% | 69.8473% | 4281.906040 |

| 算法 | 正确输出/输出 | 恢复参考/588 | 恢复有据参考/262 |
|---|---:|---:|---:|
| direct_thinking | 344/952 | 275/588 | 183/262 |
| direct_multisample_verifier | 529/1379 | 279/588 | 190/262 |
| route1_only | 250/651 | 224/588 | 156/262 |
| route2_only | 307/1087 | 250/588 | 148/262 |
| dual_without_verifier | 535/1695 | 319/588 | 198/262 |
| dual_with_verifier | 434/1255 | 268/588 | 183/262 |

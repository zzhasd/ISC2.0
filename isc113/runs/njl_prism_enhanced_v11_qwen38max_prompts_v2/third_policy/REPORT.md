# PRISM enhanced v1.1 第三种计算口径

复用 qwen3.8-max 已完成的评价结果，无新增 API 请求。
E1/E3/E4 仅 equivalent；E2 接受 equivalent + broader。按匹配参考的证据等级筛选。
Precision 保留全部原始输出；Recall/Grounded Recall 分别使用全参考/E1E2 独立最大一对一匹配。

| 算法 | Precision | Recall | Grounded Recall |
|---|---:|---:|---:|
| PRISM enhanced v1.1 | 15.2610% | 22.9592% | 50.3817% |

- 正确输出 / 全部输出：152/996。
- 恢复参考 / 全部参考：135/588。
- 恢复有据参考 / E1E2 参考：132/262。
- 覆盖固定 298 段 A→B 对话；已复现原严格/宽松全部计数，逐对话验证新口径位于二者之间。
- 冻结预测、参考、提示词哈希及全部匹配缓存绑定均已核验；原始文件保留。

E1/E2 分级召回另见 CSV/JSON，分别独立做最大一对一匹配，不能直接相加代替联合匹配。

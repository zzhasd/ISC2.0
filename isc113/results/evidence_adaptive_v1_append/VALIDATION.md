# 完成核验与口径说明

- 298 段 A→B 推断和评价全部完成，444 条最终属性，75 段空输出保留。
- 51 项相关测试通过；五个算法函数 AST 与原提示词完全一致。
- 1,623 个原有文件哈希未变化；原六算法和 EFCR 对比行与原结果逐字段相同。
- 离线重放后 8 个报告、逐输入和指标文件哈希完全一致，无新 API 请求。
- 新算法实际已观测推断 token 为 283,852；29 次尝试缺少 usage。按原规则平均 token 为 null，952.523490 token/段仅为已知用量下界。评价 token 不计入。
- 2 个推断任务及 5 个评价任务在最初三次均未收到 HTTP/模型响应后，经过审计各追加一次通信成功；请求、算法、验证器不变，追加尝试有独立标记，旧日志完整保留。
- 沿用历史 validate_matches 选择首个有效完整响应。发现 17 条评价输出不完全遵守 prompt 的关系/引用数量约束，分布为 {'broader': 12, 'none': 4, 'narrower': 1}，详见 prompt_contract_audit.json。未更改模型判断或收紧原解析器。这些条目的关系均为 broader/narrower/none，严格 equivalent-only 主表本就不给它们命中；宽松表仍按原 score_item 计分。
- 主表结果：Precision=88/444，Recall=88/588，Grounded Recall=86/262；宽松对照为 184/444、172/588、131/262。

算法、运行方式和接口见 ../../EVIDENCE_ADAPTIVE_V1_README.md；主报告 REPORT.md，逐输入明细和 CSV 位于两个计分策略子目录。

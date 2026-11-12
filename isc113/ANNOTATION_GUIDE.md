# GPT 审核、分级与人工消歧

本轮历史参考由当前对话模型的两个独立审核执行实例逐段阅读完整 A+B 建立。它们不是两名人类，也不是不同模型的验证。annotations/annotator_1 与 annotator_2 保存 A→B 的原始独立判断、互补审核与裁决；未保留已有合并文件的重复分批脚本或中间数据。

完整对话先用于提取 B 的原子属性、真值及 full_evidence。证据支持再单独依据 A-only 评定：
- E1：A 直接陈述 B 的该属性。
- E2：预设、指代、因果或跨轮关系支持保守且足够强的推断。
- E3：弱相关、开放问句、归属未决或具体程度超过线索。
- E4：A 没有相关证据。

E1/E2 必须给出来自 A 的逐字引文及原始 turn_id。完整 A+B 真值证据不能当作 A 的支持证据。“你是医生吗”不确立职业；医院值夜班不确立医生。保留主体、时间、数量、否定和模态。人工消歧处理了 63 条 E1/E2 或 E3/E4 内部分歧，不改变真值属性集合与 262 条有据集合。

## 可复用审核接口

从工作区根执行：

```powershell
python -B -m isc113.annotation prepare
python -B -m isc113.annotation support --source isc113/annotations/annotator_1/new_dailydialog_reference.json --output isc113/annotation_packets/support_new.json
python -B -m isc113.annotation validate --source isc113/references/dailydialog_human_adjudicated_588.json
python -B -m isc113.annotation rebuild
```

prepare 按完整 300 段生成 inventory_A_to_B.json，并提供 GPT 提示词。support 只导出 A 话轮及候选 claim_id/claim，隐藏真值、另一审核标签及 B 话轮。GPT 的实际审核结果通过 annotation import --source <结果JSON> --output <新文件JSON> 验证后导入。接口不通过关键词自动生成判断，不自动覆盖冻结参考。

reconcile.source/reconcile.reconcile 将两份独立 GPT 属性清单做语义对齐；当前 300 段对齐缓存完整时可离线复用。reconcile.compile 只生成 annotations/dailydialog_aligned_draft.json 和分歧草稿，不覆盖最终参考或消歧前参考。最终真值及层级仍需实际语义审核。

rebuild 根据消歧前参考及 human_adjudication_588_audit.json 中 63 条 before/after 裁决，在内存重建最终 588 条并逐字段比较，不写参考库。

results/human_disambiguation_63/read_review.py 可按稳定 claim_id 读取返回 DOCX 的人工意见。它检查每条原始 claim 指纹；原参考文件已清理为 A→B，因此整文件哈希变化是预期的，保留属性指纹应不变。

## 解释边界

历史审核的独立性指不读取对方输出，不代表不同训练来源或统计独立模型。先从完整对话提属性再核 A 支持，可能存在锚定与后见偏差。逐字引用只证明来源，不单独证明语义蕴含。原始审核理由中已有部分乱码按原值保留，避免改变实验数据；规范英文属性与原始话轮未改写。

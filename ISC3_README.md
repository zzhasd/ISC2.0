# ISC 3.0 experiments

实验报告入口：[results/isc3/实验报告.md](results/isc3/实验报告.md)。调用仍在运行时，以 `results/isc3/initial/run_status.json`、`dependent/run_status.json` 为准；`delivery_status.json` 表示离线交付生成完毕。中间分析文件不代表最终结果。

新增内容均在 `data/isc3`、`results/isc3` 和 `experiments/isc3_*.py`，不覆盖 ISC 2.0 原始结果。

E2 的完整性修订协议见 `ISC3_RECONSTRUCTION_V2_PROTOCOL.md`。新增两个调用阶段为 `reconstruction_v2_generate/` 与 `reconstruction_v2_extract/`；最终交付会等待这两个阶段也结束，原片段重建结果继续保留。

- E1：恢复量—风险曲线、校准集选阈值、测试集操作点、两阶段自检与图验证对照。
- E2：直接恢复、单／三假设重建、开放式恢复；最终断言的无支持增量及本地规范表达审计。
- E3：单轮并集、多轮联合、删一证据和等话轮数随机对照。
- E4：属性／持有者交换、删证据、完全相同 A 的不可识别世界。
- E5：领域分层、替代模板、中文对应版本与自然对话迁移；仅一个模型家族。
- 4.1：每个整数前缀的实际模型调用、固定人群归一化曲线、逐路径升降。

离线复算：

```powershell
python -m unittest discover -s experiments -p test_isc3.py -v
python experiments/isc3_local_reconstruction_audit.py
python experiments/isc3_analyze.py
python experiments/isc3_report.py
```

`ISC3_PROTOCOL.md` 为调用前冻结的探索性方案；补充见 `results/isc3/DEVIATIONS.md`。`manifest_final.json` 保存产物 SHA-256，`audit.json` 给出调用、格式错误及原数据哈希核验。自然对话沿用 DailyDialog 和项目现有来源、许可及 AI 暂定标注记录，见根目录 README 与 `data/source.json`；没有真实个人隐私真值核验。

额外向外部模型发送重建文本进行断言审计的操作被自动审批拒绝，未重试；改用离线规则给受控虚构重建的规范表达计数。自然重建文本在人工审核包中保持未评分。独立模型家族、人工双标和可训练 SGCI 均未完成。

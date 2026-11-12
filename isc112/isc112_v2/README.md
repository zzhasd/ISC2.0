# 证据约束双路 V2

独立新算法及对照实验，不修改isc112/或历史experiments/代码。推理模块core.py与离线审核evaluation.py分开；运行时快照只含A。

```powershell
python -B -m unittest discover -s tests -p test_isc112_v2.py -v
python -B -m isc112_v2 prepare
python -B -m isc112_v2 run
python -B -m isc112_v2 review
# 当前对话助手逐包实际审核，保存review_packets/decisions_*.json后：
python -B -m isc112_v2 analyze
python -B -m isc112_v2 report
python -B -m isc112_v2 check
```

run从隐藏提示读取凭证，也支持进程环境DASHSCOPE_API_KEY。已有首个有效调用不重发。请求、全部尝试、候选、最终输出、审核、评分和报告都在results/isc112_v2/。精确参数、失败规则及联合成功目标见根目录ISC112_V2_PROTOCOL.md。

核心变化：含限定的关系/事件候选；主体/内容/限定分开审核；支持关系敏感的语义去重；带原文锚点的遗漏补充。结构检查仍不能替代语义审核。112段为已参与设计的开发队列，不能作为封存泛化测试。

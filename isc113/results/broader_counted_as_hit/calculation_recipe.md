# 重算与复现

从 D:\\桌面\\ISC2.0 执行 python -B -m isc113 reproduce。该入口根据同一轮原始预测、588 条消歧参考、绑定有效的语义匹配和实际 usage，同时校验默认严格表及本目录宽松表，四指标和全部基础计数必须精确相等。

可程序化调用 evaluation.score_item(p, refs, matches, costs, accepted_relations=('equivalent','broader'))，再用 statistics.four_metrics 汇总。默认 accepted_relations 仅为 equivalent。本目录 per_input.json 保留当时的逐输入新旧计数，unlinked_broader_predictions.json 保留无有效参考边的 31 次输出。没有新的语义判断或供应商请求。

# 四个固定匿名者的主体错归属过滤复验

本实验沿用 IA、HW、HS、HU 四组原始样本，从原语料核对每人的全部对话，只输入其对侧 A 的发言。根据用户最新要求，抽取模块使用未经修改的 `elara_subject_v2.py`。

Summary 流程为：`elara_subject_v2 → 一次主体错归属过滤 → 精确字符串去重 → Summary`。direct 沿用旧提示词和参数，只读取同一组全部 A 发言。四组分别保存输入、在线请求和结果，不复用旧响应缓存。

过滤器来自用户提供的 `elara_ja_subject_filter.py`，策略保持原样：只删除明确的 A 自述错归属，且必须提供能在该候选原始引用中逐字匹配的自述片段；UNKNOWN、第三方、泛化、B 证据不足等其他情况保留。每条原始候选先分别判断，再进行精确字符串去重。不改写候选，不在 Summary 后追加模型审核。

实现入口为 `filtered_portrait_repeat.py`；旧实验脚本与结果保留。Summary 提示词中的候选数量使用过滤后实际唯一候选数，所有保留的唯一候选必须恰好分配到一个 Summary 条目。direct 引用必须匹配原始 A 发言。自述画像仅在两路结果冻结后的交付阶段读取，不进入模型请求。

在项目根目录运行，密钥由进程环境变量 `QWEN_API_KEY` 或 `DASHSCOPE_API_KEY` 提供：

```powershell
python -B -m isc113.identity_linkage.filtered_portrait_repeat all --out <新目录> --workers 8
```

也可以分别运行 `prepare`、`run`、`finish`。同目录续跑会核验代码和输入摘要并复用本次已经成功的相同请求。遇到网络中断时保留失败记录，先核查请求日志；未知计费请求不会被当作零费用。

数据流与过滤策略测试：

```powershell
python -B -m unittest isc113.identity_linkage.test_elara_ja_subject_filter isc113.identity_linkage.test_portrait_summary isc113.identity_linkage.test_filtered_portrait_repeat -v
```

交付目录 `runs/portrait_subject_filter_20261108` 中，每人各有 `self_portrait.md`、`summary_portrait.md`、`direct_portrait.md` 三份画像；`四组画像汇总.md` 合并全部 12 份。JSON 版本保留详细来源，`subject_decisions.json` 保存逐条过滤判断，`verification.json` 保存全量流程核验。

这些程序约束与单元测试不能代替日语主体归属准确性评价。本轮不新增画像评分或错误率估计。

# 人工构造的评分示例（不是六算法的实际自动评测结果）

假设某对话的经过审核的共享事实池 G* 有 4 个规范事实：

- g1（E1）：B 从昨晚开始投入地读一本书。必要 slot：读书[weight2, core]、从昨晚开始[weight1]、投入程度[weight1]。
- g2（E1）：B 被称为 Laura。必要 slot：姓名 Laura[weight2, core]。
- g3（E2）：B 去过美国。必要 slot：去过美国[weight2, core]。
- g4（E2）：B 有一份新工作。必要 slot：拥有新工作[weight2, core]。

算法甲原始 6 条预测：

1. B has been reading a book since last night. → E1；覆盖 g1 的读书、昨晚。
2. B is engrossed in the book. → E1；覆盖 g1 的读书、投入。
3. B is called Laura. → E1；覆盖 g2 姓名。
4. B is a doctor. → E3；A 仅问对方是否为医生。
5. B has been to America. → E2；覆盖 g3。
6. B is reading a book. → E1；重复覆盖 g1 的读书核心。

因此：

- 原始预测 6 条，5 条整条有据：`P_raw=5/6=0.8333`。
- g1 的三项 slot 可由 1+2 合并恢复，g2 和 g3 完整，g4 缺失：`R_full=3/4=0.75`。
- `R_E1=2/2=1.0`；`R_E2=1/2=0.5`，宏平均=0.75。
- slot 权重总量 4+2+2+2=10，正确覆盖 4+2+2=8：`slot_coverage=8/10=0.8`。
- 若将每条原始预测视为 1 个 atom，这里 `P_atom=5/6=0.8333`。
- 唯一有效被找到的事实是 g1/g2/g3 共 3 项，原始输出数为6：`UsefulYield=3/6=0.5`。
- 若 g3 原始参考中没有出现，那么 `valid_novel_core_found=1`。注意池内 g3 仍对六算法一视同仁。
- 注意：预测 6 与预测 1 在事实层面是重复表达；`exact_text_repetition_rate=0` 仍不能发现这种语义重复，因此还需要 pool 归并结果计算语义重复率。

## 指标使用建议

必须同时公开 `P_raw`, `R_full`, `R_core`, `R_E1_full`, `R_E2_full`, `slot_coverage`, `valid_novel_core_found`, 无据输出数，以及六算法间 `paired bootstrap` 差值区间。不要因人为设定某个综合 F1 而隐藏检索率与准确性之间的取舍。

## 人工检查重点

事实池中的 g1 属于一个事件关系、三个必要细节，不应拆成三个互不相关的参考；不同事实的属性不能为了刷召回合并成一个笼统属性。原始候选、审核判断、归并结果和 slot 覆盖关系必须都能够由 ID 回溯。

# 原双路算法的独立优化记录

原算法experiments/isc7_module.py、原112段isc112/、data/isc112/和results/isc112/不变，运行前后以哈希检查。

## 当前修订版

独立代码[isc112_v3](isc112_v3/README.md)，协议[ISC112_V3_PROTOCOL.md](ISC112_V3_PROTOCOL.md)。

原全局/局部提取与判别三阶段的A-only有效返回作为缓存，再增加一次A-only证据修订。原始A与可错候选进入新请求，B、参考和离线审核不进入。两模式refined和retain_union共同输出，不能相加为新的对话数量。

```powershell
python -B -m isc112_v3 prepare
python -B -m isc112_v3 run
```

run隐藏输入API key，成功请求不重发。新服务内容审核400按[运行增补](ISC112_V3_OPERATIONAL_AMENDMENT.md)记录并显式降级为原基线，不改写或重复发送被拒输入。

全部112段输出齐备后，新断言需当前对话助手实际审核，才能执行analyze。支持运行期间early生成已完成对话的审核包。只在断言/时间/证据完全对应时复用旧审核。完成审核后的离线命令：

```powershell
python -B -m isc112_v3 review --mode refined
python -B -m isc112_v3 analyze --mode refined
python -B -m isc112_v3 review --mode retain_union
python -B -m isc112_v3 analyze --mode retain_union
python -B -m isc112_v3 check --mode refined
python -B -m isc112_v3 check --mode retain_union
python -B -m isc112_v3 report
python -B -m unittest discover -s tests -p 'test_isc112*.py' -v
```

主报告results/isc112_v3/实验报告.md；各模式逐段评分、参考命中、支持性和成本分目录；figures/有矢量SVG和600dpi PNG/TIFF。V3流程成本含历史三阶段真实费用，优化开发失败试验另计，不隐去额外算力。

最终开发版本为isc112_v3/guarded_v2.py，对A-only修订决策应用保守保留和评价目标一致性保护；输出results/isc112_v3/guarded_v2/。原时态版本、仅修订与全保留都保留。该模式是在观察112段开发结果后定义的，不能冒充封存验证。实测严格覆盖102/138，原方法100/138；收益仅一段中的两项，95%区间包含零，尚无稳定超越证据。命令和完整限制见isc112_v3/README.md。

## 保留的失败尝试

isc112_v2/和results/isc112_v2/为独立证据约束双路；其新字段和引用结构导致较多格式失败。V2.1仅将排版不一致的引文绑定回真实A，V2.2另修正排除项之间的重复链接校验。它们均不改写语义判断，旧响应和各阶段结果分别保留。

完成112段语义审核的V2.2结果为81/138，低于原100/138，依据不足/未决43/185，实际551次请求、1,315,072 total tokens。因此这个版本不能被当作已经超越原算法。负结果报告results/isc112_v22/实验报告.md。

## 评价边界

沿用同112段、同138条A支持参考和原严格原子/一对一口径。AI参考、同源助手审核、开发样本迭代和计算预算差异均保留披露。保留模式的原始行占比受冗余影响，不等于独立事实精确率。具体提升以实际报告为准，不保证预期目标必达。

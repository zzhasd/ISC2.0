"""Generate verified figures and an honest Chinese experiment report."""
from pathlib import Path
import hashlib
import json
from isc4_open import ROOT,read,save,sha
from isc5_run import DATA,OUT,records

LABEL={'direct':'直接提取','selfcheck':'普通自检','ledger_verify':'语用账本＋验证'}

def main():
    s=read(OUT/'summary.json');by={(r['split'],r['method']):r for r in s['results']}
    ref=read(DATA/'reference_manifest.json');methods=['direct','selfcheck','ledger_verify']
    table=[]
    for m in methods:
        dev=by['development',m];new=by['new_evaluation',m];allr=by['all',m]
        table.append(f"| {LABEL[m]} | {dev['grounded_exact_recoveries']}/{dev['common_A_supported_reference']}，{dev['A_supported_reference_recall']:.1%} | {new['grounded_exact_recoveries']}/{new['common_A_supported_reference']}，{new['A_supported_reference_recall']:.1%} | {allr['grounded_exact_recoveries']}/{allr['common_A_supported_reference']}，{allr['A_supported_reference_recall']:.1%} |")
    quality=[]
    for m in methods:
        r=by['all',m]
        quality.append(f"| {LABEL[m]} | {r['raw_claims']} | {r['A_unsupported_or_uncertain_claims']} | {r['known_contradicted_claims']} | {r['mean_pipeline_tokens']:.0f} | {r['mean_pipeline_latency_seconds']:.2f} |")
    pairs={(r['split'],r['comparison']):r for r in s['paired_comparisons']}
    ci=pairs['all','ledger_verify - selfcheck']['paired_count_delta']
    newci=pairs['new_evaluation','ledger_verify - selfcheck']['paired_count_delta']
    text=f'''# 语言学约束能否改善 Qwen 的单侧 B 信息恢复

日期：2026-11-01，Asia/Shanghai。

**完成了文献检索、可运行模块和实际对照实验。第一版表现出更少无 A 依据输出的迹象；新增样本上严格恢复更多，但尚不能证明稳定超过普通自检。** 这是探索性结果，不是人工金标准评估或已训练的新模型。

## 算法与文献依据

实现为 `experiments/isc5_module.py`：

1. 本地标记疑问、所有格预设、附加词、模态、指代及修正线索；这些仅为提醒，不直接判真。
2. 第一次 Qwen 建立 A/B/第三方实体、命题、未知槽位、证据位置和指代/支持/取代边。
3. 本地检查图引用与原文位置，沿依赖边收集证据闭包，标记被修正节点。
4. 第二次 Qwen 用原始 A 验证候选、保留可支持的较粗结论、撤回旧归属并补漏。所有方法统一由本地按位置取原文。

关键语言学区别是“问题要问的未知值”与“问题通常背景化的内容”。例如，问配偶是否到场通常预设配偶存在，但不证明到场；条件句、引述、否认及后续修正可能取消这个背景。并非所有问号都没有信息，也并非所有问句前提都是真的。

检索梳理共 13 项研究和资料，详见 [ISC5_RESEARCH.md](../../ISC5_RESEARCH.md)。主要依据包括 [Roberts 的 QUD 理论](https://semanticsarchive.net/Archive/WYzOTRkO/InfoStructure.pdf)、[CommitmentBank](https://ojs.ub.uni-konstanz.de/sub/index.php/sub/article/view/601)、[实体上下文追踪](https://aclanthology.org/2022.lrec-1.136.pdf)、[属性生成与重排](https://aclanthology.org/2022.nlp4convai-1.6.pdf)及 [CoVe](https://aclanthology.org/2024.findings-acl.212.pdf)。它们支持设计思路，并不证明本项目模块一定有效。

补充检索还覆盖 [1SC 单侧重建/摘要](https://homes.cs.washington.edu/~gshyam/Papers/onesided.pdf)、[GraphProfiler 来源图画像](https://arxiv.org/html/2609.12448)与 [CONCORD](https://arxiv.org/abs/2604.13348)。图与引用本身已有直接先例，不能仅凭加图主张论文新颖；CONCORD 的额外查询会改变本轮只能观察 A 的条件，未采用。

## 实际实验条件

原 ISC4 的 32 段用于开发诊断；另从剩余 671 段规范化去重 test 候选中，按固定种子随机选出 16 段新评价对话。排除历次 171 个已选 ID 及 train/validation 的规范化完全重复，无长度或关键词筛选。新参考在查看本轮输出前冻结：35 条完整 B 信息，其中 9 条暂定有充分 A 依据；未满足该具体性水平的较粗信息另行审核，不自动判假。

当前助手看完整 A+B 建参考；**三个 Qwen 方法都只看 A**，不见 B、参考、旧错误列表或其他方法答案。所有提示在调用前冻结。新样本虽然未用于历史实验，但研究助手准备标注时看过其内容，不声称研究者盲法。语义复核由同一当前助手完成，独立人审缺失。

- Direct：1 次调用；本轮也允许合理预设，避免故意削弱基线。
- SelfCheck：Direct 草稿 + 普通重读自检，共 2 次。
- LedgerVerify：结构化账本 + 验证，共 2 次。

同一模型 `qwen3.8-flash`、temperature=0、thinking 关闭、每次 4096 输出 token 上限、4 并发。**相同调用次数不等于相同实际计算成本**，tokens 和延迟列在下表。没有权重训练或微调。

## 严格恢复：A 已有线索的信息找回了多少

Direct 在 `test_277`、`test_709` 出现格式失败，相应自检没有创建；账本路径在这两段仍有效。公平主表使用三方法共同有效的 30 段开发对话和全部 16 段新对话。有效率分别为 Direct 46/48、SelfCheck 46/48、LedgerVerify 48/48。失败不伪装为空预测或 unknown。

分母是相同对话中的暂定 A 可支持参考。语义对齐考虑具体值、持有者、时间和完整输出的 time 字段；一一匹配防止重复表述刷数。部分匹配与参考外新发现不混入严格命中。

| 方法 | 开发诊断，共同 30 段 | 新评价，16 段 | 合并，共同 46 段 |
| --- | ---: | ---: | ---: |
{chr(10).join(table)}

新评价中的 2 个额外严格命中，分别是 `test_536` 的飞行计划背景和 `test_928` 的未来共同音乐会计划。后者直接/普通自检使用现在时，账本输出保留未来计划。对普通自检的每对话命中增量为 {newci['mean']:.3f}，按对话聚类 bootstrap 95% 区间 [{newci['low']:.3f}, {newci['high']:.3f}]。新增可支持参考只有 9 条，区间下界触及零，不能据 88.9% 宣称总体显著提升。

合并组相对普通自检仅多恢复 **1 条**，每段增量 {ci['mean']:.3f}，95% 区间 [{ci['low']:.3f}, {ci['high']:.3f}]，包含零。开发组还少恢复 1 条：取得新命中时也有原命中被放到不确定项。因此本轮没有证明召回率稳定超过等调用数自检。

## 输出可靠性与成本

以下同样使用共同有效的 46 段。

| 方法 | 原始确定断言 | A 证据不足或未决 | 与完整源文明确冲突 | 平均 pipeline tokens/段 | 平均两步耗时合计/秒 |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(quality)}

这些是当前助手的暂定审核计数。A 证据不足/未决包括猜中隐藏 B、主体归属问题、无法确定的具体值和部分范围外泛化，**不能把这一列全部称为假事实或真实世界幻觉率**。严格命中也不是对完整画像中所有信息的召回率。

账本相对普通自检减少了 12 条 A 依据不足/未决断言，原始输出条数相近（78 对 80）；明确源文冲突由 4 降至 1。不过这些小计有同一对话内关联和标注主观性，不能直接当总体错误率保证。账本实际 token 消耗约为普通自检的 {by['all','ledger_verify']['mean_pipeline_tokens']/by['all','selfcheck']['mean_pipeline_tokens']:.2f} 倍，也没有达到 token 完全匹配；本轮不足以排除计算投入差异。

共同 46 段的 hypotheses 数分别为 Direct {by['all','direct']['raw_hypotheses']}、SelfCheck {by['all','selfcheck']['raw_hypotheses']}、LedgerVerify {by['all','ledger_verify']['raw_hypotheses']}。这些是不确定候选，不计为确定事实；本轮没有完成它们的独立精度/召回审核，因此结果不能解释为全部可能画像候选的性能。

存在真实回归：账本仍把错误日期下“忘记周年纪念日”的指控保留为事实，还把历史婚礼推迟混成当前庆祝安排推迟；处方的类别虽有补出，剂量、休息和饮水等参考信息仍未完整恢复。不能把第一版称为已经解决跨轮修正或高召回抽取。

## 评分敏感性

严格原参考将 `test_91_broadcast` 的确认式疑问及 `test_39_profession` 的办公室头衔解释为可支持事实；这两项存在问句 at-issue 与背景、跨轮身份锚定的标注边界。主表保留冻结标签；事后排除这两项的敏感性表为：Direct 32/49、SelfCheck 33/49、LedgerVerify 36/49。这个分析是在观察结果后作的，不是新的主结论；对应差值区间存于 summary.json。它说明原参考不是不可质疑的金标准。

原参考外的新发现独立于主分母保存，例如共同购物、生日礼物、居家休息的背景和躲藏事件。相同发现只记一个规范项；没有把这些候选自动当成错误，也没有为了模块涨分覆盖原参考。部分更粗的属性和不确定 hypotheses 仍需单独评价；不能把原始断言数当去重隐私信息量。

![方法对照](D:/桌面/ISC2.0/results/isc5/method_comparison.png)

## 下一步的可训练版本与验证要求

值得继续的方向是将主体归属、投射/取消、时态/计划、指代依赖和修正状态做成可监督的候选排序/证据分类任务，而不是仅继续加长提示。训练仅使用独立训练对话的 A 及教师辅助标签；完整 B 可用于生成训练监督，但测试时不可见。目标服务是否支持该模型权重训练需另核实，本轮没有训练任何权重。

先对当前新发现、政策边界和漏掉处方等错误做独立双人审核，统一原子事实粒度；再在新的封存样本上做无 QUD、无投射、无实体、无修正以及纯长提示的消融，并提供 token 匹配对照。当前没有这些消融，不能声称某个语言学组件带来了因果提升，也不能以新样本 9 条正参考支持强论文结论。

## 复现与审计

实际新调用 {s['actual_calls']} 次，记录 {s['recorded_tokens']:,} tokens，均返回 HTTP 200；原计划 192 次因两个无效 Direct 源跳过两个自检请求，未静默重试。最终有效提取 140 份；239 次事实出现对应 158 个不同“断言+证据位置”组合，均已作暂定语义复核。位置合法不等于证据在逻辑上充分；参考和复核同源，尚非独立质量验证。

离线复算：

```powershell
python experiments/isc5_run.py export
python experiments/isc5_review.py
python experiments/isc5_adjudicate.py
python experiments/isc5_analyze.py
python experiments/isc5_report.py
python -m unittest discover -s experiments -p test_isc5.py -v
```

代码、冻结协议、提示、请求、返回、源关联和评分保存在 `experiments/isc5_*.py`、`ISC5_PROTOCOL.md`、`data/isc5/`、`results/isc5/`。旧 ISC2/3/4 产物未覆盖。密钥只经隐藏输入进入进程，没有写入产物。
'''
    (OUT/'实验报告.md').write_text(text,encoding='utf-8')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    fig,ax=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
    colors=['#7b8794','#6389cf','#45a285'];width=.24
    for j,m in enumerate(methods):
        rr=[by[split,m] for split in ['development','new_evaluation']]
        xx=[i+(j-1)*width for i in range(2)]
        vals=[100*r['A_supported_reference_recall'] for r in rr]
        ax[0].bar(xx,vals,width,color=colors[j],label=LABEL[m])
        for x,y,r in zip(xx,vals,rr):ax[0].text(x,y+1,f"{r['grounded_exact_recoveries']}/{r['common_A_supported_reference']}",ha='center',fontsize=10)
    ax[0].set_xticks([0,1],['开发诊断：共同30段','新评价：16段'])
    ax[0].set_ylim(0,105);ax[0].set_ylabel('有A依据参考的严格恢复率（%）')
    ax[0].set_title('具体信息恢复：新增正参考仅9条')
    ax[0].legend(fontsize=9,loc='upper left')
    values=[by['all',m]['A_unsupported_or_uncertain_claims'] for m in methods]
    ax[1].bar(range(3),values,color=colors)
    ax[1].set_xticks(range(3),[LABEL[m] for m in methods]);ax[1].set_ylim(0,max(values)+7)
    ax[1].set_ylabel('A依据不足或未决的原始断言条数')
    ax[1].set_title('共同46段：此列不等于假事实数')
    for i,v in enumerate(values):ax[1].text(i,v+.4,str(v),ha='center',fontsize=11)
    fig.suptitle('Qwen单侧方法对照：AI暂定标注，尚未证明稳定超过普通自检',fontsize=13)
    fig.savefig(OUT/'method_comparison.png',dpi=170);plt.close(fig)
    all_raw=records('initial')+records('dependent')
    audit={'http_calls':len(all_raw),'all_http_200':all(r.get('http_status')==200 for r in all_raw),
        'returned_models':sorted({r.get('body',{}).get('model','unknown') for r in all_raw}),
        'module_matches_frozen':hashlib.sha256((ROOT/'experiments/isc5_module.py').read_bytes()).hexdigest()==read(DATA/'manifest.json')['module_sha256'],
        'initial_plan_matches_frozen':sha(read(OUT/'initial/requests.json'))==read(DATA/'manifest.json')['initial_requests_sha256'],
        'full_reference_matches_frozen':sha(read(DATA/'full_AB_reference.json'))==ref['reference_sha256']}
    save(OUT/'audit.json',audit)
    print({'report':'results/isc5/实验报告.md','audit':audit})
if __name__=='__main__':main()

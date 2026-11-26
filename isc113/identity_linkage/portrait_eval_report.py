"""Render the AT scoring card and keep its different denominators explicit."""
from __future__ import annotations

import csv

from .core import save


def report_text(data):
    completed = [row for row in data["methods"].values() if row["status"] == "portrait_available"]
    single = len(data["methods"]) == 1
    introduction = (
        f"评估 {completed[0]['name']} 的正式画像正文，使用同一批 200 段 A-only 对话。"
        if single else "同一批 200 段 A-only 对话和六份冻结画像用于评分。B1 与 B3 沿用历史生成失败记录。"
    )
    lines = [
        "# AT 画像评价报告",
        "",
        introduction,
        "",
        "## 结果",
        "",
        "| 方法 | 自述加权分 / 100 | A-only 全支持 / 抽样数 | Wilson 95% 区间 | 可定位原始引用的段落 % | 来源对话广度 % | 文本精确重复 % | ELARA 属性 ID 恰好一次 % | 支持属性正文完整保留 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for code, row in data["methods"].items():
        name = f"{code} {row['name']}" if code != "Ours" else row["name"]
        if row["status"] != "portrait_available":
            lines.append(f"| {name} | 生成失败 | — | — | — | — | — | — | — |")
            continue
        trace, audit = row["evidence_trace"], row["grounded_audit"]
        exact = row.get("native_inventory", {}).get("all", {}).get("exactly_once_100")
        low, high = audit["full_support_wilson_95"]
        retained = row["content_audit"]["supported"]
        lines.append(
            f"| {name} | {row['self_report']['score_100']:.1f} "
            f"| {audit['labels'].get('full', 0)}/{audit['sampled_units']} "
            f"| {low:.1f}–{high:.1f}% | {trace['passage_trace_rate_100']:.1f} "
            f"| {trace['dialogue_reach_100']:.1f} | {row['exact_repeat_rate_100']:.2f} "
            f"| {f'{exact:.2f}' if exact is not None else '—'} "
            f"| {retained['labels'].get('retained', 0)}/{retained['sampled']} |"
        )
    for row in completed:
        archive = row.get("archive_partition")
        if archive:
            lines.extend([
                "",
                f"正文关联 {archive['portrait_ids']:,} 个属性 ID，另有 {archive['archived_ids']:,} 个 ID 进入归档。"
                f"正文和归档合并后，{archive['combined_exactly_once_100']:.2f}% 的源属性恰好出现一次。"
                "表中的正文覆盖和语义评分以实际发布的画像正文为准。",
            ])
    lines.extend([
        "",
        "### A-only 证据判读计数",
        "",
        "| 方法 | 全支持 | 部分支持 | 主体错归属 | 明确反驳 | 未判定 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for code, row in data["methods"].items():
        if "grounded_audit" in row:
            counts = row["grounded_audit"]["labels"]
            lines.append(f"| {code} | {counts.get('full', 0)} | {counts.get('partial', 0)} "
                         f"| {counts.get('speaker_error', 0)} | {counts.get('contradicted', 0)} "
                         f"| {counts.get('unresolved', 0)} |")
    lines.extend([
        "",
        "### 共同属性的正文保留计数",
        "",
        "| 方法 | 支持属性完整 | 部分 | 改变 | 未判定 | 不确定属性仍完整保留 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for code, row in data["methods"].items():
        if "content_audit" in row:
            support = row["content_audit"]["supported"]["labels"]
            uncertain = row["content_audit"]["uncertain"]
            lines.append(f"| {code} | {support.get('retained', 0)} | {support.get('partial', 0)} "
                         f"| {support.get('altered', 0)} | {support.get('unresolved', 0)} "
                         f"| {uncertain['labels'].get('retained', 0)}/{uncertain['sampled']} |")
    lines.extend([
        "",
        "### 自述评分敏感性",
        "",
        "| 方法 | 原分 | 清除明确冲突原子的得分 | 仅保留 4–5 级得分 | 冲突原子数 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for code, row in data["methods"].items():
        if "self_report" in row:
            report = row["self_report"]
            lines.append(f"| {code} | {report['score_100']:.1f} | {report['score_without_conflicted_atoms']:.1f} "
                         f"| {report['score_from_near_full_hits']:.1f} | {report['conflicted_atoms']} |")
    available = [code for code, row in data["methods"].items() if "self_report" in row]
    if available:
        atoms = [{atom["fact_id"]: atom for atom in data["methods"][code]["self_report"]["atoms"]}
                 for code in available]
        lines.extend([
            "",
            "### 逐项自述命中等级",
            "",
            "| 原子 | 自述踩分点 | 权重 | " + " | ".join(available) + " |",
            "| --- | --- | ---: | " + " | ".join(["---:"] * len(available)) + " |",
        ])
        for uid, atom in atoms[0].items():
            grades = " | ".join(str(row[uid]["grade"]) for row in atoms)
            lines.append(f"| {uid} | {atom['fact_zh']} | {atom['max_score']} | {grades} |")
    lines.extend([
        "",
        "## 指标及采样协议",
        "",
        "1. **自述加权分。** AT 原有的 10 条自述分为 11 个原子，满分合计 100。"
        "每个原子只计一次，得分为原子满分 × 命中等级 / 5。"
        "0 级为无命中或仅反向，1 级为一个有区分度的子事实，2 级为部分核心，"
        "3 级为核心命中但缺少重要限定，4 级为近完整命中，5 级为全部关键含义均正确。"
        "若同时出现明确的相反说法，单列冲突和扣除冲突项后的敏感性结果。"
        "按原子给权重与 Pyramid 的内容单元思想相近，本实验沿用项目既有权重。"
        " [Pyramid](https://aclanthology.org/N04-1019/)。",
        "2. **A-only 证据验证。** 对所有方法以同一规则按句号、分号等切分，"
        "保留成对引号与括号中的内容。各方法用固定哈希种子均匀抽取 16 个文本单元，"
        "打散后每批最多 48 条。画像方法、旧审核标签和 AT 自述均不进入证据判读。"
        "每条候选包包含两个来自不同对话的全量检索窗口，并加入最多两个与引用关联的窗口，"
        "上限四个。每个窗口通常含连续三句可见 A 发言。"
        "全支持率以所有抽样单位为分母，描述候选包内能够充分验证的比例。"
        "检索遗漏可能使其偏低。Wilson 区间描述抽样波动，评审可靠性需另行验证。"
        " [FActScore](https://aclanthology.org/2023.emnlp-main.741/) · "
        "[RAGChecker](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract-Datasets_and_Benchmarks_Track.html)。",
        "3. **证据可定位性和广度。** 直接方法核对其引用确实存在于指定 A 发言，"
        "ELARA 方法经属性 ID 回溯到原始引文。"
        "段落可追溯率要求至少一个可定位的引用。来源广度按被引用的独立对话数 / 200。"
        "另输出引用分布的有效对话数、引文无法定位次数及 A 第一人称、疑问线索计数。"
        "最后两项可用于安排错归属审核。",
        "4. **逐段精确重复。** 统一切分后，做 Unicode NFKC、空白、大小写和句末格式归一。"
        "超出首次出现的重复单元数 / 全部单元数。"
        "保留否定、时间与数量差异。该指标是逐字重复下界，同义复述需要另行核查。",
        "5. **ELARA 属性保留账本。** 在同一套 2,615 个过滤后属性上统计至少有一次、"
        "恰好一次和多处引用，另按原始审核支持与不确定分层。"
        "多处引用按发生重复的不同 ID 数计算。这个指标衡量来源分配的完整性。"
        "对 Direct 方法记为缺项。",
        "6. **候选属性的正文保留。** 用固定种子抽取同一组 10 个先前标记为支持的"
        "属性和 2 个不确定属性，与被评画像配对。每个配对最多给出三个画像文本片段。"
        "先从全文检索两个候选，再加入可通过原生 ID 锚定的候选，缺少该候选时回到全文检索。"
        "完整保留需保留主体、义项、时态、频率、对象与关键限定。不确定属性另列，"
        "须保留其不确定性。未判定包括候选检索遗漏。所用共同属性是 ELARA 的候选命题，"
        "匹配这些命题的能力与原始 A-only 是否支持它们可分别检查。",
        "",
        "## 自动化与质量界限",
        "",
        "固定多语言 E5-small 只给出证据候选。自述分与 A-only 样本标签均由 "
        "GPT-6.2 Sol 高推理子代理一次性分批判读。共同属性的正文保留亦采用同一盲化评审。"
        "证据引用、片段和原子编号经程序校验。"
        "复算所有分数可离线运行，并复用冻结的判读记录。",
        "",
        "各指标保留自己的分母。较长的复合句更难获得全支持，"
        "可结合部分支持率和每种方法的文本单元数解读。AT 的单人结果无法估计跨个人的泛化性能。"
        "单次判读缺少独立复标。可公开报告带区间的证据分，并为后续评价器校准保留盲化样本。",
        "",
        "### 复算",
        "",
        "运行 python -m isc113.identity_linkage.portrait_eval report。程序读取冻结的判读、"
        "画像输入摘要和采样清单，检查引用后写出分数。prepare 重建盲化证据包，"
        "prepare-content 重建正文保留样本。为独立画像复算时，使用 --ours-run 指定相应运行目录。",
        "",
    ])
    return "\n".join(lines)


def export_report(out, data):
    save(out / "evaluation.json", data)
    (out / "REPORT.md").write_text(report_text(data), encoding="utf-8")
    fields = ["method", "status", "self_report_100", "conflicted_atoms", "evidence_full_100",
              "evidence_partial_100", "evidence_speaker_error_100", "evidence_conflict_100",
              "evidence_unresolved_100", "evidence_sample_n", "passage_trace_100", "dialogue_reach_100",
              "exact_repeat_100", "native_inventory_coverage_100", "native_inventory_exactly_once_100",
              "content_supported_retained_100", "content_uncertain_retained_100"]
    with (out / "scores.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        for code, row in data["methods"].items():
            if row["status"] != "portrait_available":
                writer.writerow([code, row["status"], *([None] * (len(fields) - 2))])
                continue
            self_report, audit, trace = row["self_report"], row["grounded_audit"], row["evidence_trace"]
            native = row.get("native_inventory", {}).get("all", {})
            writer.writerow([code, row["status"], self_report["score_100"], self_report["conflicted_atoms"],
                             audit["full_support_100"], audit["labels"].get("partial", 0) * 100 / audit["sampled_units"],
                             audit["attribution_error_100"], audit["explicit_conflict_100"], audit["unresolved_100"],
                             audit["sampled_units"], trace["passage_trace_rate_100"], trace["dialogue_reach_100"],
                             row["exact_repeat_rate_100"], native.get("coverage_100"), native.get("exactly_once_100"),
                             row["content_audit"]["supported"]["retained_100"],
                             row["content_audit"]["uncertain"]["retained_100"]])


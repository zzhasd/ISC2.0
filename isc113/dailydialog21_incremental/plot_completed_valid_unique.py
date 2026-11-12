# -*- coding: utf-8 -*-
"""
DailyDialog-21 / AGD-EVAL：自动绘制“B 有效发现量 + 当前事实池”。

将本文件放在：
    D:\\桌面\\ISC2.0\\isc113\\dailydialog21_incremental\\plot_completed_valid_unique.py

在该目录运行：
    python plot_completed_valid_unique.py

依赖：pip install numpy matplotlib

脚本从项目原始 JSON 自动发现 *11/11 前缀已完成* 的对话，
读取推理、私有候选映射、Support、Pool 和跨前缀 alignment 文件，
按项目 analyze.py / score_prefix() 的 core-slot 覆盖规则重新计算。
不会读取预先导出的 completed18_prefix_metrics.csv，也不会调用模型/API。

随着评价进度从 18 段增加到 31 段，重新运行会自动更新图形。
输出到根目录下 figures/ 和 results/，不修改任何原始实验数据。
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ALGORITHMS = ("direct_thinking", "elara_v1")
VALID = {"E1", "E2"}
PREFIXES = tuple(range(1, 12))
COLORS = {"direct_thinking": "#377db5", "elara_v1": "#e87724"}


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def setup_chinese_font():
    installed = {x.name for x in font_manager.fontManager.ttflist}
    for name in ("Microsoft YaHei", "Microsoft YaHei UI", "SimHei", "PingFang SC",
                 "Heiti SC", "Noto Sans CJK SC", "Source Han Sans SC",
                 "WenQuanYi Micro Hei", "Noto Sans CJK JP"):
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            break
    else:
        print("[提醒] 没找到中文字体，图中中文可能显示方框；Windows 可使用微软雅黑。")
    plt.rcParams.update({
        "axes.unicode_minus": False,
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    })


def completed_dialogues(root: Path, prefix_rows: list[dict]) -> tuple[list[str], dict[str, list[dict]]]:
    """只有前缀数据 + 全部 Support/Pool + 11 轮 alignment + 推理均齐全才算完成。"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for p in prefix_rows:
        grouped[p["dialogue_id"]].append(p)

    done = []
    for did, items in sorted(grouped.items()):
        ks = sorted(int(p["prefix_k"]) for p in items)
        if ks != list(PREFIXES):
            print(f"[跳过] {did}：A-only 前缀不是完整 k=1..11")
            continue

        # 只要求文件存在；结构/映射完整性在 score_one_dialogue() 严格核对。
        required = [root / "alignment" / "judgments" / f"{did}.json"]
        for p in items:
            pid = p["prefix_id"]
            required.extend([
                root / "agd_eval" / "judgments" / "support" / f"{pid}.json",
                root / "agd_eval" / "judgments" / "pool" / f"{pid}.json",
                root / "inference" / "direct_thinking" / f"{pid}.json",
                root / "inference" / "elara_v1" / f"{pid}.json",
            ])
        if all(path.is_file() for path in required):
            done.append(did)
    return done, grouped


def score_one_dialogue(root: Path, did: str, prefixes: list[dict], private: dict) -> list[dict]:
    """复现 analyze.py 中 score_prefix 的 unique_core_count 和 pool_count 核心规则。"""
    alignment = load_json(root / "alignment" / "judgments" / f"{did}.json")
    if alignment.get("dialogue_id") != did:
        raise ValueError(f"{did}: alignment 的 dialogue_id 不一致")

    unified_ids = {u["id"] for u in alignment["unified_facts"]}
    mappings = {}
    for m in alignment["mapping"]:
        key = (m["prefix_id"], m["fact_id"])
        if key in mappings or m["unified_fact_id"] not in unified_ids:
            raise ValueError(f"{did}: alignment 映射重复或引用了不存在的统一事实：{key}")
        mappings[key] = m["unified_fact_id"]

    rows = []
    expected_fact_keys = set()
    for p in sorted(prefixes, key=lambda x: int(x["prefix_k"])):
        pid, k = p["prefix_id"], int(p["prefix_k"])
        if pid != f"{did}__k{k:02d}":
            raise ValueError(f"前缀 ID 格式不一致：{pid}")
        turns = [int(t["turn_id"]) for t in p["visible_turns"]]
        if turns != list(range(1, 2 * k, 2)):
            raise ValueError(f"{pid}: A-only 输入含非当前前缀发言（可能泄露 B 或未来发言）")

        support = load_json(root / "agd_eval" / "judgments" / "support" / f"{pid}.json")
        pool = load_json(root / "agd_eval" / "judgments" / "pool" / f"{pid}.json")
        if pid not in private:
            raise ValueError(f"{pid}: private_source_mapping.json 中缺失候选映射")
        source = private[pid]
        candidates = {c["id"] for c in source["candidates"]}
        by_candidate = {}
        for item in support["items"]:
            cid = item["id"]
            if cid in by_candidate:
                raise ValueError(f"{pid}: 重复 Support candidate {cid}")
            by_candidate[cid] = item["atoms"]
        if candidates != set(by_candidate):
            raise ValueError(f"{pid}: Support 审核的候选 ID 与 private_source_mapping 不一致")

        # 每一个 Pool fact 只能映射到一个稳定的 unified_fact_id；同一前缀不能合并到重复 ID。
        fact_ids = {f["id"] for f in pool["facts"]}
        if len(fact_ids) != len(pool["facts"]):
            raise ValueError(f"{pid}: Pool 有重复事实 ID")
        mapped = []
        for f in pool["facts"]:
            key = (pid, f["id"])
            expected_fact_keys.add(key)
            if key not in mappings:
                raise ValueError(f"{pid}: alignment 缺少 {f['id']} 的统一事实映射")
            mapped.append(mappings[key])
        if len(mapped) != len(set(mapped)):
            raise ValueError(f"{pid}: 同一前缀的两个事实映射到同一个统一 ID")

        # 仅 E1/E2 原子断言能够为当前 Pool 中的属性提供证据。
        valid_atom_ids = {
            f"{cid}::{i}"
            for cid, atoms in by_candidate.items()
            for i, atom in enumerate(atoms)
            if atom["label"] in VALID
        }
        pool_atom_ids = {m["atom_id"] for f in pool["facts"] for m in f["members"]}
        if pool_atom_ids != valid_atom_ids:
            missing = valid_atom_ids - pool_atom_ids
            extra = pool_atom_ids - valid_atom_ids
            raise ValueError(f"{pid}: Pool/Support 原子映射不一致：缺失 {len(missing)}，多出 {len(extra)}")

        counts = {}
        for alg in ALGORITHMS:
            predictions = [c for c in source["predictions"] if c["algorithm"] == alg]
            saved = load_json(root / "inference" / alg / f"{pid}.json")
            if len(predictions) != len(saved["claims"]):
                raise ValueError(f"{pid}: {alg} 推理 claim 数与来源映射不一致")

            # 与 analyze.score_prefix() 相同：该算法候选中经过支持审核的原子 ID。
            alg_atom_ids = {
                f"{c['candidate_id']}::{i}"
                for c in predictions
                for i, atom in enumerate(by_candidate[c["candidate_id"]])
                if atom["label"] in VALID
            }
            core_count = 0
            for f in pool["facts"]:
                covered = {
                    slot_id
                    for member in f["members"]
                    if member["atom_id"] in alg_atom_ids
                    for slot_id in member["slot_ids"]
                }
                core_slots = {s["id"] for s in f["slots"] if s["core"]}
                if not core_slots:
                    raise ValueError(f"{pid} 的事实 {f['id']} 没有 core slots")
                if core_slots <= covered:
                    core_count += 1
            counts[alg] = core_count

        n_pool = len(pool["facts"])
        if not (counts[ALGORITHMS[0]] <= n_pool and counts[ALGORITHMS[1]] <= n_pool):
            raise ValueError(f"{pid}: 有效唯一属性数不应超过共享事实池")
        rows.append({
            "dialogue_id": did,
            "prefix_k": k,
            "direct_unique": counts["direct_thinking"],
            "elara_unique": counts["elara_v1"],
            "pool_count": n_pool,
        })

    if set(mappings) != expected_fact_keys:
        extras = set(mappings) - expected_fact_keys
        raise ValueError(f"{did}: alignment 存在 {len(extras)} 个多余/不匹配的事实映射")
    if len(rows) != 11:
        raise ValueError(f"{did}: 11 个前缀不完整")
    return rows


def bootstrap_mean_ci(matrix: np.ndarray, samples: np.ndarray):
    """一整段对话为一个重采样单位；同一抽样索引用于 k=1..11。"""
    means = matrix.mean(axis=0)
    boots = matrix[samples].mean(axis=1)
    low, high = np.percentile(boots, [2.5, 97.5], axis=0)
    return means, low, high


def write_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="自动识别已完成对话，绘制 AGD-EVAL 有效唯一属性 + 共享事实池曲线")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                        help="项目根目录；默认使用脚本所在目录")
    parser.add_argument("--bootstrap", type=int, default=2000,
                        help="Bootstrap 次数；默认 2000")
    parser.add_argument("--seed", type=int, default=20261106,
                        help="Bootstrap 随机种子；默认 20261106")
    parser.add_argument("--dpi", type=int, default=220, help="PNG 清晰度；默认 220 DPI")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.bootstrap < 10:
        parser.error("--bootstrap 应至少为 10")
    required = [root / "data" / "prefix_inputs.json",
                root / "agd_eval" / "private_source_mapping.json"]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        parser.error(f"项目数据文件不存在：{missing}；请将脚本放进 dailydialog21_incremental 根目录")

    prefixes = load_json(required[0])
    private = load_json(required[1])
    done, grouped = completed_dialogues(root, prefixes)
    if not done:
        parser.error("目前没有一段完整的 11/11 前缀对话（需要 Support、Pool、Alignment、两算法推理文件均齐全）")

    scored = []
    for did in done:
        scored.extend(score_one_dialogue(root, did, grouped[did], private))

    by_key = {(r["dialogue_id"], r["prefix_k"]): r for r in scored}
    matrices = {
        "direct_thinking": np.array([[by_key[(d, k)]["direct_unique"] for k in PREFIXES] for d in done], dtype=float),
        "elara_v1": np.array([[by_key[(d, k)]["elara_unique"] for k in PREFIXES] for d in done], dtype=float),
        "pool": np.array([[by_key[(d, k)]["pool_count"] for k in PREFIXES] for d in done], dtype=float),
    }
    n = len(done)
    rng = np.random.default_rng(args.seed)
    samples = rng.integers(0, n, size=(args.bootstrap, n))
    stats = {name: bootstrap_mean_ci(m, samples) for name, m in matrices.items()}

    setup_chinese_font()
    x = np.array(PREFIXES)
    fig, ax = plt.subplots(figsize=(8.7, 5.45))
    for alg, label in (("direct_thinking", "Direct Thinking"), ("elara_v1", "ELARA v1")):
        mean, low, high = stats[alg]
        c = COLORS[alg]
        ax.fill_between(x, low, high, color=c, alpha=0.12, linewidth=0, zorder=1)
        ax.plot(x, mean, color=c, marker="o", linewidth=2.0, markersize=4.0,
                label=label, zorder=3)
    ax.plot(x, stats["pool"][0], linestyle="--", marker="s", color="#66717c",
            linewidth=1.8, markersize=4.2, label="总属性数量", zorder=4)
    ax.set_title("算法有效发现量 VS 当前话轮总属性数量", fontsize=14, weight="bold", pad=12)
    ax.set_xlabel("A 方累积发言数 k", fontsize=11)
    ax.set_ylabel("平均有效唯一属性数", fontsize=11)
    ax.set_xticks(x)
    ymax = float(max(np.max(stats["pool"][0]),
                     np.max(stats["direct_thinking"][2]),
                     np.max(stats["elara_v1"][2])))
    ax.set_ylim(0, max(1.0, ymax * 1.10))
    ax.grid(axis="y", alpha=0.16, linewidth=0.8)
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    fig.tight_layout()

    figdir = root / "figures"
    figdir.mkdir(exist_ok=True)
    png = figdir / "figure_B_completed_valid_unique_growth.png"
    pdf = figdir / "figure_B_completed_valid_unique_growth.pdf"
    fig.savefig(png, dpi=args.dpi, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)

    out = root / "results"
    out.mkdir(exist_ok=True)
    metric_csv = out / "figure_B_completed_prefix_metrics.csv"
    summary_csv = out / "figure_B_completed_mean_ci.csv"
    write_csv(metric_csv, scored)
    summary = []
    for i, k in enumerate(PREFIXES):
        row = {"prefix_k": k, "n_dialogues": n,
               "bootstrap_replicates": args.bootstrap, "bootstrap_seed": args.seed}
        for key, short in (("direct_thinking", "direct"), ("elara_v1", "elara"), ("pool", "pool")):
            mean, low, high = stats[key]
            row[f"{short}_mean"] = float(mean[i])
            row[f"{short}_ci95_low"] = float(low[i])
            row[f"{short}_ci95_high"] = float(high[i])
        summary.append(row)
    write_csv(summary_csv, summary)

    manifest = {
        "dialogues_completed": n, "dialogue_ids": done, "prefixes_scored": len(scored),
        "expected_k": list(PREFIXES), "bootstrap_replicates": args.bootstrap,
        "bootstrap_seed": args.seed,
        "ci_definition": "percentile 95% CI, resample whole dialogues with replacement",
        "metrics": "current supported unique fact cores (all core slots covered, E1/E2)",
        "source": "data/prefix_inputs.json + inference + private_source_mapping + judgments/support + judgments/pool + alignment/judgments",
        "plot": str(png.relative_to(root)),
    }
    (out / "figure_B_completed_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n===== AGD-EVAL 有效属性逐轮图 =====")
    print(f"项目根目录：{root}")
    print(f"发现完整对话：{n} / {len(grouped)} 段；已计分前缀：{len(scored)} / {len(prefixes)}")
    print("已完成 ID：" + ", ".join(done))
    print("k=1：Direct={:.2f}，ELARA={:.2f}，Pool={:.2f}".format(
        stats["direct_thinking"][0][0], stats["elara_v1"][0][0], stats["pool"][0][0]))
    print("k=11：Direct={:.2f}，ELARA={:.2f}，Pool={:.2f}".format(
        stats["direct_thinking"][0][-1], stats["elara_v1"][0][-1], stats["pool"][0][-1]))
    print(f"生成图像：{png}\n矢量图：{pdf}")
    print(f"曲线及 CI：{summary_csv}\n逐前缀数据：{metric_csv}")


if __name__ == "__main__":
    main()

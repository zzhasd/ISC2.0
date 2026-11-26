import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from . import portrait_ours_reconcile as consolidation
from .portrait_experiment import Experiment
from .portrait_ours import finish
from .portrait_summary import compact_summary_attributes


class FakeRetrievalModel:
    np = np

    def run(self, texts):
        return np.array([[1., 0.] for _ in texts])


class FakeExperiment(Experiment):
    def run_jobs(self, function, jobs):
        return map(function, jobs)

    def ask(self, name, prompt, data, validate, **kwargs):
        if prompt == consolidation.EDITOR:
            obj = {"edits": [
                {"id": "G0003", "statement": "", "archive": {"U3": "conversation", "U4": "low_information"}}
            ]}
        elif prompt == consolidation.MERGER:
            entries = data["entries"]
            obj = {"merges": [
                {"ids": ["G0001", "G0002"], "statement": "B喜欢慢跑。"},
                {"ids": ["G0004", "G0005"], "statement": "B可能养了狗。"},
            ]} if len(entries) == 4 else {"merges": []}
        else:
            obj = {"checks": {
                key: row["statement"] != "B可能养了狗。" for key, row in data["changes"].items()
            }}
        return validate(obj)


class ConsolidationTests(unittest.TestCase):
    def test_cross_topic_union_archive_coverage_and_rejected_merge(self):
        claims = [
            ("B likes jogging", "running", "supported"),
            ("Bはジョギングが好き", "likes jogging", "supported"),
            ("A waved to B", "greeting", "supported"),
            ("B has a hobby", "hobby", "supported"),
            ("B has a pet", "pets", "supported"),
            ("B may have a dog", "dogs", "uncertain"),
        ]
        unique = [
            dict(unique_id=f"U{i}", claim=claim, members=[
                dict(dialogue=f"D{i}", claim=dict(claim=claim, attribute=label, audit_verdict=verdict))
            ])
            for i, (claim, label, verdict) in enumerate(claims, 1)
        ]
        groups = [
            dict(ids=ids, topic=topic, statement=statement, verification="reviewed")
            for ids, topic, statement in [
                (["U1"], "SPORT", "B喜欢跑步。"),
                (["U2"], "BODY", "B喜欢慢跑。"),
                (["U3", "U4"], "CONTACT", "A向B打招呼，B有爱好。"),
                (["U5"], "PETS", "B养了宠物。"),
                (["U6"], "PETS", "B可能养了狗。"),
            ]
        ]
        with TemporaryDirectory() as root:
            output = Path(root)
            experiment = FakeExperiment(output, output, None, 1, output)
            args = SimpleNamespace(skip_reconcile=False, polish_only=False, model_home=output)
            with patch.object(consolidation, "LocalRetrievalModel", return_value=FakeRetrievalModel()), \
                    patch.object(consolidation, "model_manifest", return_value={}):
                finish(experiment, args, unique, compact_summary_attributes(unique), groups, {})
            portrait = json.loads((output / "portrait.json").read_text(encoding="utf-8"))
            evidence = json.loads((output / "portrait_evidence.json").read_text(encoding="utf-8"))
            markdown = (output / "portrait.md").read_text(encoding="utf-8")
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))

        merged = next(row for row in portrait["portraits"] if len(row["unique_ids"]) == 2)
        self.assertEqual(merged["unique_ids"], ["U1", "U2"])
        self.assertEqual(merged["topics"], ["身体与健康", "运动与户外活动"])
        self.assertEqual(merged["attribute_labels"], ["running", "likes jogging"])
        self.assertEqual(merged["evidence_status"], {"supported": 2})
        self.assertEqual(markdown.count("B喜欢慢跑。"), 1)
        self.assertIn("B养了宠物。", markdown)
        self.assertIn("B可能养了狗。", markdown)
        self.assertNotIn("打招呼", markdown)
        self.assertEqual([row["source_details"][0]["unique_id"] for row in evidence["archive"]], ["U3", "U4"])
        self.assertEqual((report["portrait_ids"], report["archived_ids"], report["covered_ids"]), (4, 2, 6))

    def test_omitted_empty_archive_retains_all_ids(self):
        groups = {"P1": {"statement": "B跑步。", "ids": ["U1", "U2"]}}
        edits = consolidation.edits_response(
            {"edits": [{"id": "P1", "statement": "B常跑步。"}]}, groups,
        )
        self.assertEqual(edits, [{"keys": ["P1"], "statement": "B常跑步。", "archive": {}}])

    def test_fully_archived_edit_is_audited_without_prose(self):
        groups = {"P1": {"statement": "B有爱好。", "ids": ["U1"]}}
        edits = consolidation.edits_response({"edits": [
            {"id": "P1", "statement": "B有爱好。", "archive": {"U1": "low_information"}},
        ]}, groups)
        self.assertEqual(edits, [{"keys": ["P1"], "statement": "", "archive": {"U1": "low_information"}}])

    def test_reject_overlapping_merge_ids(self):
        with self.assertRaises(ValueError):
            consolidation.merges_response({"merges": [
                {"ids": ["P1", "P2"], "statement": "B常跑步。"},
                {"ids": ["P2", "P3"], "statement": "B常慢跑。"},
            ]}, {"P1": None, "P2": None, "P3": None})

"""Read a returned review DOCX by stable claim IDs; never edit source references.

Usage: bundled-python read_review.py completed.docx --output decisions.json
Blank fields remain unresolved. Invalid or conflicting labels stop the import.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fingerprint(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def text(e):
    return "".join(t.text or "" for t in e.iter(W + "t")).strip()


def read_decisions(docx_path, manifest_path=OUT / "review_manifest.json"):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected = {i["claim_id"]: i for i in manifest["items"]}
    with ZipFile(docx_path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        props = ET.fromstring(z.read("docProps/core.xml"))
    identifier = props.find("{http://purl.org/dc/elements/1.1/}identifier")
    if identifier is not None and identifier.text != manifest["batch_id"]:
        raise ValueError("Review batch mismatch")
    control_values = {}
    for sdt in root.findall(".//w:sdt", NS):
        tag = sdt.find("w:sdtPr/w:tag", NS)
        if tag is None:
            continue
        value = tag.get(W + "val", "")
        if not value.startswith(("ISC113_EVIDENCE|", "ISC113_NOTE|")):
            continue
        kind, cid = value.split("|", 1)
        if cid not in expected:
            raise ValueError("Unknown claim ID in field: " + cid)
        key = (kind, cid)
        if key in control_values:
            raise ValueError("Duplicate field: " + str(key))
        control_values[key] = text(sdt.find("w:sdtContent", NS))
    forms = {}
    for table in root.findall(".//w:tbl", NS):
        rows = table.findall("w:tr", NS)
        cells = [[text(c) for c in row.findall("w:tc", NS)] for row in rows]
        if not cells or len(cells[0]) != 2 or cells[0][0] != "属性 ID":
            continue
        cid = cells[0][1]
        if cid not in expected:
            raise ValueError("Unknown printed claim ID: " + cid)
        if cid in forms:
            raise ValueError("Duplicate form: " + cid)
        fields = {r[0]: r[1] for r in cells[1:] if len(r) == 2}
        if "人工审核意见" not in fields:
            raise ValueError("Missing opinion cell: " + cid)
        label = fields["人工审核意见"].strip()
        note = fields.get("审核备注 选填", "").strip()
        for kind, value in [("ISC113_EVIDENCE", label), ("ISC113_NOTE", note)]:
            tagged = control_values.get((kind, cid))
            # Text outside a preserved control is also acceptable, but contradictory
            # values inside and outside one field are not silently resolved.
            if tagged and tagged != value:
                raise ValueError("Printed/tagged field mismatch: " + cid)
        if label and label not in {"E1", "E2", "E3", "E4"}:
            raise ValueError("Use exactly E1, E2, E3, E4 or blank: " + cid + " = " + label)
        forms[cid] = (label, note)
    missing = set(expected) - set(forms)
    if missing:
        raise ValueError("Missing review forms: " + ", ".join(sorted(missing)))

    references = json.loads((BASE / "references/dailydialog.json").read_text(encoding="utf-8"))
    by = {}
    for row in references:
        for c in row["claims"]:
            by[c["claim_id"]] = (row, c)
    result = []
    for item in manifest["items"]:
        cid = item["claim_id"]
        if cid not in by:
            raise ValueError("Reference no longer contains claim: " + cid)
        row, claim = by[cid]
        if row["dialogue_id"] != item["dialogue_id"] or row["direction"] != item["direction"]:
            raise ValueError("Dialogue/direction mismatch: " + cid)
        if fingerprint(claim) != item["reference_claim_sha256"]:
            raise ValueError("Reference changed since form generation: " + cid)
        label, note = forms[cid]
        result.append({
            "review_id": item["review_id"], "claim_id": cid,
            "dialogue_id": row["dialogue_id"], "direction": row["direction"],
            "claim": claim["claim"], "old_evidence_level": claim["evidence_level"],
            "human_evidence_level": label, "human_note": note,
            "status": "human_decided" if label else "unfilled",
        })
    return {
        "batch_id": manifest["batch_id"],
        "review_docx_sha256": sha(Path(docx_path)),
        "source_reference_sha256": sha(BASE / "references/dailydialog.json"),
        "source_reference_changed_as_a_whole": sha(BASE / "references/dailydialog.json") != manifest["source_hashes"]["references/dailydialog.json"],
        "total": len(result), "filled": sum(bool(r["human_evidence_level"]) for r in result),
        "unfilled": sum(not r["human_evidence_level"] for r in result),
        "source_references_modified": False, "decisions": result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = read_decisions(args.docx)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "decisions"}, ensure_ascii=False))

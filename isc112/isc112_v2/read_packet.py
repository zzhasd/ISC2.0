"""Compact source-aware packet display for actual conversational-assistant review."""
import argparse
import sys
from .runner import OUT, ROOT, read


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(); p.add_argument('folder', choices=['early', 'main']); p.add_argument('number', type=int)
    p.add_argument('--version', choices=['v2', 'v21', 'v22','v3_refined','v3_retain_union'], default='v2'); a = p.parse_args()
    directory = OUT if a.version == 'v2' else ROOT / ('results/isc112_' + a.version)
    if a.version.startswith('v3_'):directory=ROOT/'results/isc112_v3'/a.version[3:]
    folder = 'review_early' if a.folder == 'early' else 'review_packets'
    for d in read(directory / f'{folder}/packet_{a.number:02d}.json'):
        print('\nDIALOGUE', d['dialogue_id'])
        for t in d['full_AB']: print(f"{t['speaker']}{t['turn']}: {t['text']}")
        print('FROZEN REFERENCES (A=1 means provisional A-supported):')
        for f in d['frozen_references']: print(f"{f['id']} A={int(f['A_supported'])}: {f['claim']}")
        print('NEW FACTS TO REVIEW:')
        for q in d['review_rows']: print(f"[{q['index']}] {q['claim']} | time={q['time']} | evidence={q['evidence_variants']}")


if __name__ == '__main__': main()

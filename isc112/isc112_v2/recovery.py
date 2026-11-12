"""Additional same-payload, first-valid recovery; no semantic-score access."""
import getpass
import hashlib
import os
import sys

from .runner import DATA, ROOT, freeze, verify_frozen, run_phase, dependent, export


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    verify_frozen()
    freeze(DATA / 'recovery_manifest.json', {'max_total_attempts': 12, 'initial_total_cap': 4,
        'amendment_sha256': hashlib.sha256((ROOT / 'ISC112_V2_RECOVERY_AMENDMENT.md').read_bytes()).hexdigest(),
        'purpose': 'format/transport recovery before any semantic review, unchanged payload and validator'})
    key = os.environ.get('DASHSCOPE_API_KEY') or (getpass.getpass('API key (hidden): ') if sys.stdin.isatty() else sys.stdin.readline().strip())
    if not key: raise RuntimeError('Missing API key')
    try:
        run_phase('initial', key, max_attempts=12)
        dependent()
        run_phase('dependent', key, max_attempts=12)
    finally: print(export(), flush=True)


if __name__ == '__main__': main()

"""Continue only after complete reconstruction, no secret persisted."""
import json
import os
import subprocess
import sys
import time
from revision_api import ROOT,OUT,read
from revision_defense import prepare_summaries,prepare_judges

def main():
    key=os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
    if not key:raise SystemExit('Missing API key')
    start=time.monotonic()
    while True:
        p=OUT/'defense_reconstruction/run_status.json'
        if p.exists():
            s=read(p)
            if s['complete']:break
            # A failed wave may be followed by the runner's bounded transport
            # resume. Only a completed prerequisite may trigger paid next stages.
        if time.monotonic()-start>3600:raise SystemExit('Wait for reconstruction exceeded 1 hour')
        time.sleep(5)
    for name,prepare in [('summary',prepare_summaries),('judge',prepare_judges)]:
        prepare()
        r=subprocess.run([sys.executable,str(ROOT/'experiments/revision_api.py'),'--plan',
            f'results/qwen38/defense_{name}/requests.json'],input=key+'\n',text=True,cwd=ROOT)
        if r.returncode:raise SystemExit(r.returncode)

if __name__=='__main__':main()

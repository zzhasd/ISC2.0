"""Start dependent paid work only when its prerequisite plan is complete."""
import argparse
import os
import subprocess
import sys
import time
from revision_api import ROOT,OUT,read

def main():
    p=argparse.ArgumentParser();p.add_argument('--wait-for',required=True);p.add_argument('--plan',required=True);args=p.parse_args()
    key=os.environ.get('DASHSCOPE_API_KEY') or sys.stdin.readline().strip()
    if not key:raise SystemExit('Missing API key')
    start=time.monotonic()
    while True:
        path=OUT/args.wait_for/'run_status.json'
        if path.exists() and read(path)['complete']:break
        if time.monotonic()-start>3600:raise SystemExit('Prerequisite did not complete within one hour')
        time.sleep(5)
    result=subprocess.run([sys.executable,str(ROOT/'experiments/revision_api.py'),'--plan',args.plan],
        input=key+'\n',text=True,cwd=ROOT)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()

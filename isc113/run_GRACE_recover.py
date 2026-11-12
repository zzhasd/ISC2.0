"""Safe, auditable GRACE v1 resume without changing GRACE.py's frozen hash.

Usage (PowerShell):
    python run_GRACE_recover.py --workers 4 --eval-workers 12 --request-rounds 3 --run-id grace_v1_append

Reuses already paid HTTP-200 responses in runs/<run-id>/attempts.jsonl, while
accepting only model-authored B claims and source quotations that pass the
original GRACE validators. Stores every normalization in format_recovery.jsonl.
If historical requests are exhausted, one new task suffix (round 3) is used.
An unresolved in-flight request is NOT reissued unless the user explicitly
adds --allow-inflight-retry (possible duplicate billing).

This is a format-recovered run, not an unchanged GRACE-v1 baseline run.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import run_GRACE as original
from grace_recovery import validate_cached

ALLOW_INFLIGHT='--allow-inflight-retry' in sys.argv
if ALLOW_INFLIGHT:
    sys.argv.remove('--allow-inflight-retry')


class FormatRecoveryClient(original.RecoverableClient):
    def __init__(self, key, run_id, max_rounds=3):
        super().__init__(key, run_id, max_rounds)
        self.audit_file=original.common.BASE/'runs'/run_id/'format_recovery.jsonl'

    def _record(self, row, actions, logical):
        # Do not copy user dialogue or model output: the original audit log
        # already holds that response. The formatter audit contains only IDs.
        notice={'logical_name':logical,'task_id':row['task_id'],
                'attempt_id':row['attempt_id'],
                'previous_validation_error':row.get('error'),
                'recovered_from_http_status':row.get('http_status'),
                'normalizations':actions,
                'method':'GRACE v1 format recovery; original evidence validation retained'}
        with self.lock:
            with self.audit_file.open('a',encoding='utf-8') as file:
                file.write(json.dumps(notice,ensure_ascii=False)+'\n')

    def _recover(self, name, payload, validator):
        task=original.common.digest({'logical_name':name,'payload':payload})
        with self.raw.lock:
            rows=[r for r in self.raw.rows if r.get('event')=='complete'
                  and r.get('task_id')==task and r.get('http_status')==200
                  and isinstance(r.get('body'),dict)]
        # Prioritize the original first valid answer over newer repaired ones.
        for row in rows:
            if not row.get('valid'):continue
            try:return validator(original.clientmod.decode(row['body'])),task
            except (ValueError,KeyError,TypeError,AttributeError):pass
        for row in rows:
            if '/grace_v1/' not in name:
                # Evaluation uses the original matcher schema, not GRACE's.
                validated=original.parse_embedded_json(row['body'],validator)
                actions=[{'action':'recover_complete_embedded_matcher_json'}] if validated is not None else []
            else:
                validated,actions=validate_cached(row['body'],name,payload,validator,
                                                 original.algorithm)
            if validated is None:continue
            if not row.get('valid') or actions:
                self._record(row,actions,name)
            return validated,task
        return None

    def call(self,name,payload,validator):
        for round_index in range(self.max_rounds):
            logical=name+('' if round_index==0 else '/format_retry_'+str(round_index))
            found=self._recover(logical,payload,validator)
            if found is not None:return found
            try:
                return self.raw.call(logical,payload,validator)
            except Exception as exc:
                found=self._recover(logical,payload,validator)
                if found is not None:return found
                message=str(exc)
                has_next=round_index+1<self.max_rounds
                if 'Attempt limit exceeded' in message and has_next:
                    continue
                if 'Unresolved in-flight request' in message and has_next and ALLOW_INFLIGHT:
                    print('[警告] 未闭合请求，用户授权跳过旧请求 ID 并尝试新 ID；可能重复计费：'
                          +logical,file=sys.stderr)
                    continue
                raise
        raise RuntimeError('All safe request rounds exhausted: '+name)


original.RecoverableClient=FormatRecoveryClient

if __name__=='__main__':
    print('[GRACE 格式恢复] 只补跑缺失预测；保留 277 条已完成文件；'
          '恢复操作记录在 format_recovery.jsonl。',flush=True)
    if ALLOW_INFLIGHT:
        print('[注意] 已启用未闭合请求重新发送授权；可能产生额外 API 费用。',flush=True)
    original.main()

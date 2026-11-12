"""One bounded recovery via direct HTTPS; inference payload remains unchanged."""
import os
from datetime import datetime, timezone
import requests
from isc113.identity_linkage.api import Client
from isc113.identity_linkage.core import freeze
from isc113.identity_linkage.repeat_third_portrait import OUT, finalize
from isc113.identity_linkage import repeat_portrait

client=Client(os.environ['QWEN_API_KEY'],OUT)
ack={r['attempt_id'] for r in client.rows if r['event']=='network_retry_acknowledged'}
failures=[r for r in client.rows if r['event']=='complete' and r.get('billing_unknown') and r['attempt_id'] not in ack]
assert len(failures)==1 and failures[0]['logical_name'].endswith('/direct')
assert failures[0]['error'].startswith('ProxyError:')
event=dict(event='network_retry_acknowledged',task_id=failures[0]['task_id'],attempt_id=failures[0]['attempt_id'],logical_name=failures[0]['logical_name'],utc=datetime.now(timezone.utc).isoformat(),reason='Two local proxy disconnects inspected. Official HTTPS endpoint reachable directly (unauthenticated models GET returned 401). One bounded recovery using direct HTTPS, TLS verification enabled. Inference model/prompt/parameters unchanged. Prior usage and billing remain unknown.')
client.append(event)
freeze(OUT/'direct_transport_recovery.json',dict(event=event,environment_proxy_used=False,TLS_verification=True,endpoint=client.endpoint,model_prompt_parameters_unchanged=True,prior_failures_retained=True))
original_session=requests.Session
def direct_session():
    s=original_session()
    s.trust_env=False
    return s
requests.Session=direct_session
repeat_portrait.generate(OUT)
finalize(OUT)

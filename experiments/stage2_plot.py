from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/stage2'
s=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
rows=json.loads((OUT/'predictions.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(1,3,figsize=(15,4.8),layout='constrained')
colors={'prior':'#a3abb4','a_only':'#2878b5','full':'#438e71'}
conds=['prior','a_only','full']
x=np.arange(2)
for offset,condition in enumerate(conds):
 vals=[];lower=[];upper=[]
 for arm in ['random','enriched']:
  c=s['conditions'][arm+'/'+condition];v=100*c['recovery_rate'] if c['recovery_rate'] is not None else 0
  ci=c['recovery_cluster_bootstrap']['ci95']
  vals.append(v);lower.append(max(0,v-ci[0]*100) if ci else 0);upper.append(max(0,ci[1]*100-v) if ci else 0)
 axes[0].bar(x+(offset-1)*.25,vals,.23,color=colors[condition],label={'prior':'No evidence','a_only':'A only','full':'Full dialogue'}[condition],yerr=[lower,upper],capsize=3)
axes[0].set_xticks(x,['Random: 3 true labels','Enriched: 23 true labels'])
axes[0].set_ylim(0,113);axes[0].set_ylabel('Recovery of provisional true attributes (%)')
axes[0].set_title('Keep sampling arms separate')
axes[0].legend(frameon=False,fontsize=8,loc='upper left')
domains=['health','relationship','family','employment','finance']
counts=[];hit=[]
for d in domains:
 domain_rows=[r for r in rows if r['condition']=='a_only' and r['domain']==d and r['truth']=='true']
 counts.append(len(domain_rows));hit.append(sum(r['prediction']=='true' for r in domain_rows))
y=np.arange(len(domains))
axes[1].barh(y,counts,color='#dce3e9',label='Gold true')
axes[1].barh(y,hit,color='#2878b5',label='Recovered from A')
axes[1].set_yticks(y,domains);axes[1].invert_yaxis();axes[1].set_xlabel('Attribute labels (nested labels can overlap)')
axes[1].set_title('Which types were recovered?');axes[1].legend(frameon=False,fontsize=8)
for i,(n,k) in enumerate(zip(counts,hit)):axes[1].text(n+.12,i,f'{k}/{n}',va='center')
unknownpos=[];unknownneg=[]
for c in ['a_only','full']:
 m=s['conditions']['all/'+c]
 unknownpos.append(m['positive_assertions_unverified_truth']);unknownneg.append(m['false_assertions_on_unknown_truth'])
axes[2].bar(np.arange(2)-.18,unknownpos,.36,label='Affirmations',color='#c56659')
axes[2].bar(np.arange(2)+.18,unknownneg,.36,label='Denials',color='#d9a343')
axes[2].set_xticks([0,1],['A only','Full dialogue'])
axes[2].set_title('Definite claims with unknown full truth')
axes[2].set_ylabel('Unverified assertions (not proven false)')
axes[2].legend(frameon=False,fontsize=8)
fig.suptitle('Stage 2: all B utterances removed; a fixed 20-attribute catalogue',fontsize=14)
fig.savefig(OUT/'stage2_results.png',dpi=180);fig.savefig(OUT/'stage2_results.svg');plt.close(fig)

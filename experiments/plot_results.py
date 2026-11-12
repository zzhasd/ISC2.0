from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
s=json.loads((ROOT/'results/summary.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(1,3,figsize=(15,4.5),layout='constrained')
natural_conditions=['prior','a_only','full','shuffled','word_bag']
labels=['Query only','A only','Full dialogue','A shuffled','A word bag']
colors=['#a6adb4','#2878b5','#438e71','#d79847','#a6adb4']
rates=[100*s['natural_evidence'][c]['true_fact_disclosure']['rate'] for c in natural_conditions]
ax[0].barh(labels,rates,color=colors)
ax[0].invert_yaxis();ax[0].set_xlim(0,110)
ax[0].set_xlabel('True-fact assertions (%) of 25 true facts')
ax[0].set_title('DailyDialog diagnostic sample')
for i,v in enumerate(rates):ax[0].text(v+1,i,f'{v:.0f}%',va='center')
conditions=['a_only','narrative','shuffled','word_bag']
labels2=['A only','Narrative','A shuffled','A word bag']
rates2=[100*s['conditions']['controlled/'+c]['accuracy'] for c in conditions]
forced=[100*s['conditions']['controlled/'+c]['forced_binary_accuracy_ties_false'] for c in conditions]
x=np.arange(4)
ax[1].bar(x-.18,rates2,.36,label='With abstention',color='#2878b5')
ax[1].bar(x+.18,forced,.36,label='Forced true / false',color='#a6adb4')
ax[1].set_xticks(x,labels2,rotation=18);ax[1].set_ylim(0,110)
ax[1].set_ylabel('Truth-label recovery (%)');ax[1].set_title('Controlled: 48 items / 24 pairs')
ax[1].legend(frameon=False,fontsize=8,loc='lower left')
base=s['simple_supervised_baselines']
ax[2].bar(['Unigrams','Unigrams +\nbigrams'],[100*base['unigram']['accuracy'],100*base['unigram_bigram']['accuracy']],color=['#a6adb4','#b95a52'])
ax[2].set_ylim(0,110);ax[2].set_ylabel('Accuracy (%)')
ax[2].set_title('Shortcut baseline: hold out attribute pair')
ax[2].text(.5,18,'Shared templates;\nnot mechanism generalization',ha='center',color='#333333')
fig.suptitle('1SC privacy pilot: recovery is measurable; causal mechanism is not established',fontsize=14)
fig.savefig(ROOT/'results/pilot_results.png',dpi=180)
fig.savefig(ROOT/'results/pilot_results.svg')
plt.close(fig)

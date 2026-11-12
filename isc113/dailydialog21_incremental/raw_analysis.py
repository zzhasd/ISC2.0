"""Compute the fully observed raw-output endpoint while semantic review continues.

This does not impute missing semantic judgments or claim evaluation completion.
"""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent
def read(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    verification=read(HERE/'results/inference_verification.json')
    assert verification['inference_complete'] and verification['offline_replayed_predictions']==682
    prefixes=read(HERE/'data/prefix_inputs.json')
    dids=sorted({p['dialogue_id'] for p in prefixes})
    assert len(dids)==31
    rng=np.random.default_rng(20261106);samples=rng.integers(0,31,size=(2000,31))
    matrices={};rows=[];summary={}
    for alg in ('direct_thinking','elara_v1'):
        matrix=np.array([[len(read(HERE/'inference'/alg/(f'{did}__k{k:02d}.json'))['claims'])
                          for k in range(1,12)] for did in dids])
        matrices[alg]=matrix
        for k in range(1,12):
            values=matrix[:,k-1];lo,hi=np.percentile(values[samples].mean(axis=1),[2.5,97.5])
            rows.append({'algorithm':alg,'prefix_k':k,'dialogues':31,'mean_raw_count':float(values.mean()),
                         'ci95_low':float(lo),'ci95_high':float(hi),
                         'direct_cap_hit_rate':float((values>=10).mean()) if alg=='direct_thinking' else None})
        summary[alg]={'raw_predictions_total':int(matrix.sum()),'mean_k1':float(matrix[:,0].mean()),
                      'mean_k11':float(matrix[:,-1].mean()),'min_raw_count':int(matrix.min()),'max_raw_count':int(matrix.max()),
                      'k11_cap_hit_rate':float((matrix[:,-1]>=10).mean()) if alg=='direct_thinking' else None}
    out=HERE/'results';out.mkdir(exist_ok=True)
    with (out/'raw_prefix_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'raw_diagnostics.json').write_text(json.dumps({'semantic_evaluation_complete':False,'algorithms':summary},indent=2),encoding='utf-8')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    fig,ax=plt.subplots(figsize=(8,4.8))
    for alg,label,color in [('direct_thinking','Direct Thinking','#2864b4'),('elara_v1','ELARA v1','#d66a21')]:
        points=[r for r in rows if r['algorithm']==alg]
        x=[r['prefix_k'] for r in points]
        ax.plot(x,[r['mean_raw_count'] for r in points],label=label,color=color,marker='o',markersize=3)
        ax.fill_between(x,[r['ci95_low'] for r in points],[r['ci95_high'] for r in points],color=color,alpha=.12)
    ax.set(xlabel='Observed A utterances (k)',ylabel='Mean raw claims',title='Raw attribute predictions',xticks=range(1,12),ylim=(0,None))
    ax.grid(axis='y',alpha=.2);ax.legend(frameon=False)
    fig.text(.12,.015,'31 dialogues; paired dialogue bootstrap, 2,000 resamples; bands: descriptive 95% CI',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1))
    figures=HERE/'figures';figures.mkdir(exist_ok=True)
    for ext in ('png','pdf'):fig.savefig(figures/f'figure1_raw_growth.{ext}')
    plt.close(fig)
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

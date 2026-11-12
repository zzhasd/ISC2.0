"""Deterministic scoring, paired whole-dialogue bootstrap, and publication plots.

Requires every prediction, semantic judgment, and cross-prefix mapping. Missing
work is an error, never silently converted to empty output or a zero score.
"""
import csv
from collections import Counter
import json
from pathlib import Path
import random
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from prepare_evaluation import agd,read,HERE,scoring_input_fingerprint

ALGORITHMS=('direct_thinking','elara_v1')
LABELS={'direct_thinking':'Direct Thinking','elara_v1':'ELARA v1'}
COLORS={'direct_thinking':'#2864b4','elara_v1':'#d66a21'}

def csvout(name,rows):
    path=HERE/'results'/name;path.parent.mkdir(parents=True,exist_ok=True)
    assert rows, f'No rows for {name}'
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def ratio(n,d):return n/d if d else None

def discovery_transition(previous,ever,current,first_prefix=False):
    """Identity-only discovery bookkeeping; no evidence or slots are backfilled."""
    return {'new':current-ever,'ever':ever|current,
            'reappeared':(current&ever)-previous,'disappeared':previous-current,
            'net_change':None if first_prefix else len(current)-len(previous)}

def score_prefix(p,private,pool,support,alignment):
    pid=p['prefix_id'];turns=p['visible_turns'];valid=agd.VALID
    agd.validate_support(support,private['candidates'],turns)
    packet=read(HERE/'agd_eval/packets/pool'/(pid+'.json'))
    agd.validate_pool(pool,packet['atoms'])
    by={x['id']:x['atoms'] for x in support['items']}
    allowed={t['turn_id'] for t in turns}
    assert all(set(a['turn_ids'])<=allowed for atoms in by.values() for a in atoms)
    for fact in pool['facts']:
        for s in fact['slots']:
            assert s['required'] and s['weight']==(2 if s['core'] else 1),'Frozen slot policy violated'
    sweep_atoms={f'{cid}::{i}' for cid in private['sweep_candidate_ids']
                 for i,a in enumerate(by[cid]) if a['label'] in valid}
    mapped=[alignment[(pid,f['id'])] for f in pool['facts']]
    assert len(mapped)==len(set(mapped)), 'Within-prefix semantic duplication requires Pool review'
    metrics=[];facts=[];prediction_rows=[]
    for algorithm in ALGORITHMS:
        raws=[c for c in private['predictions'] if c['algorithm']==algorithm]
        good=0;total_atoms=0;valid_atoms=0;alg_atoms=set();invalid_text=set()
        seen_slots=set();redundant=0
        member_slots={m['atom_id']:{(f['id'],s) for s in m['slot_ids']}
                      for f in pool['facts'] for m in f['members']}
        for raw in raws:
            atoms=by[raw['candidate_id']]
            grounded=bool(atoms) and all(a['label'] in valid for a in atoms)
            good+=grounded;total_atoms+=len(atoms);valid_atoms+=sum(a['label'] in valid for a in atoms)
            slots=set()
            for i,a in enumerate(atoms):
                aid=f'{raw["candidate_id"]}::{i}'
                if a['label'] in valid:
                    assert aid in member_slots
                    alg_atoms.add(aid);slots.update(member_slots[aid])
                else:invalid_text.add(agd.clean_claim(a['text']))
            if grounded and not(slots-seen_slots):redundant+=1
            seen_slots.update(slots)
            prediction_rows.append(dict(dialogue_id=p['dialogue_id'],prefix_k=p['prefix_k'],algorithm=algorithm,
                                        prediction_id=raw['id'],claim=raw['claim'],all_grounded=int(grounded),
                                        labels='|'.join(a['label'] for a in atoms)))
        core_count=full_count=slot_hit=slot_total=0;e_core=Counter();sweep_total=sweep_hit=0
        for f in pool['facts']:
            covered={s for m in f['members'] if m['atom_id'] in alg_atoms for s in m['slot_ids']}
            sweep_covered={s for m in f['members'] if m['atom_id'] in sweep_atoms for s in m['slot_ids']}
            required={s['id'] for s in f['slots'] if s['required']}
            cores={s['id'] for s in f['slots'] if s['core']}
            core=bool(cores) and cores<=covered;full=bool(required) and required<=covered
            weight=sum(s['weight'] for s in f['slots'] if s['required'])
            hit=sum(s['weight'] for s in f['slots'] if s['required'] and s['id'] in covered)
            core_count+=core;full_count+=full;e_core[f['level']]+=core;slot_hit+=hit;slot_total+=weight
            in_sweep=bool(cores) and cores<=sweep_covered
            sweep_total+=in_sweep;sweep_hit+=in_sweep and core
            facts.append(dict(dialogue_id=p['dialogue_id'],prefix_id=pid,prefix_k=p['prefix_k'],algorithm=algorithm,
                              local_fact_id=f['id'],unified_fact_id=alignment[(pid,f['id'])],
                              canonical_claim=f['canonical_claim'],evidence_level=f['level'],
                              core_hit=int(core),full_hit=int(full),slot_weight_hit=hit,slot_weight_total=weight,
                              covered_slot_ids='|'.join(sorted(covered)),
                              slot_values=json.dumps(f['slots'],ensure_ascii=False),in_sweep_pool=int(in_sweep)))
        output=read(HERE/'inference'/algorithm/(pid+'.json'))
        assert len(output['claims'])==len(raws)
        metrics.append(dict(dialogue_id=p['dialogue_id'],split=p['split'],prefix_k=p['prefix_k'],algorithm=algorithm,
                            raw_count=len(raws),valid_raw_count=good,unique_core_count=core_count,
                            full_count=full_count,pool_count=len(pool['facts']),p_raw=ratio(good,len(raws)),
                            r_core=ratio(core_count,len(pool['facts'])),r_full=ratio(full_count,len(pool['facts'])),
                            slot_coverage=ratio(slot_hit,slot_total),slot_weight_hit=slot_hit,slot_weight_total=slot_total,
                            e1_core_count=e_core['E1'],e2_core_count=e_core['E2'],
                            cap_hit=int(len(raws)>=10) if algorithm=='direct_thinking' else None,
                            inference_tokens=output['usage'].get('total_tokens'),judge_tokens=None,
                            atom_count=total_atoms,valid_atom_count=valid_atoms,
                            invalid_unique_text_approx=len(invalid_text),semantic_redundant_valid=redundant,
                            exact_text_repetition_count=len(raws)-len({agd.clean_claim(r['claim']) for r in raws}),
                            sweep_pool_count=sweep_total,sweep_core_hit=sweep_hit,sweep_r_core=ratio(sweep_hit,sweep_total),
                            api_attempt_count=output['api_attempt_count'],format_failure_count=output['format_failure_count'],
                            truncated_attempt_count=output['truncated_attempt_count']))
    return metrics,facts,prediction_rows

def main():
    input_fingerprint=scoring_input_fingerprint()
    prefixes=read(HERE/'data/prefix_inputs.json');private=read(HERE/'agd_eval/private_source_mapping.json')
    assert len(prefixes)==341
    dids=sorted({p['dialogue_id'] for p in prefixes})
    assert len(dids)==31
    alignment={};unified={};alignments=[]
    for did in dids:
        obj=read(HERE/'alignment/judgments'/(did+'.json'))
        assert obj['dialogue_id']==did
        uids={f['id'] for f in obj['unified_facts']}
        assert len(uids)==len(obj['unified_facts']) and all(u.startswith(did+'::') for u in uids)
        unified[did]=obj['unified_facts'];alignments.append(obj)
        for m in obj['mapping']:
            key=(m['prefix_id'],m['fact_id'])
            assert key not in alignment and m['unified_fact_id'] in uids
            assert key[0].startswith(did+'__k')
            alignment[key]=m['unified_fact_id']
    rows=[];frows=[];prows=[]
    for p in prefixes:
        pid=p['prefix_id']
        support=read(HERE/'agd_eval/judgments/support'/(pid+'.json'))
        pool=read(HERE/'agd_eval/judgments/pool'/(pid+'.json'))
        rr,ff,pp=score_prefix(p,private[pid],pool,support,alignment)
        rows.extend(rr);frows.extend(ff);prows.extend(pp)
    assert set(alignment)=={(f['prefix_id'],f['local_fact_id']) for f in frows}
    metrics={(r['dialogue_id'],r['algorithm'],r['prefix_k']):r for r in rows}
    byfact={(f['dialogue_id'],f['algorithm'],f['prefix_k'],f['unified_fact_id']):f for f in frows}
    trajectory=[]
    for did in dids:
        for alg in ALGORITHMS:
            ever=set();previous=set()
            for k in range(1,12):
                local={uid:byfact[(did,alg,k,uid)] for uid in [u['id'] for u in unified[did]] if (did,alg,k,uid) in byfact}
                current={uid for uid,f in local.items() if f['core_hit']}
                state=discovery_transition(previous,ever,current,k==1)
                new=state['new'];row=metrics[(did,alg,k)]
                assert len(current)==row['unique_core_count']
                row.update(first_new_count=len(new),ever_found_count=len(state['ever']),
                           first_new_e1_count=sum(local[u]['evidence_level']=='E1' for u in new),
                           first_new_e2_count=sum(local[u]['evidence_level']=='E2' for u in new),
                           reappeared_count=len(state['reappeared']),disappeared_count=len(state['disappeared']),
                           net_change=state['net_change'])
                for u in unified[did]:
                    uid=u['id'];f=local.get(uid)
                    trajectory.append(dict(dialogue_id=did,unified_fact_id=uid,prefix_k=k,algorithm=alg,
                                           supported_at_k=int(f is not None),evidence_level=f['evidence_level'] if f else '',
                                           core_hit=int(uid in current),full_hit=f['full_hit'] if f else 0,
                                           first_discovered=int(uid in new),reappeared=int(uid in state['reappeared']),
                                           slot_coverage=ratio(f['slot_weight_hit'],f['slot_weight_total']) if f else None,
                                           covered_slot_ids=f['covered_slot_ids'] if f else '',
                                           local_slot_values=f['slot_values'] if f else ''))
                ever=state['ever'];previous=current
            assert sum(metrics[(did,alg,k)]['first_new_count'] for k in range(1,12))==len(ever)
    assert len(rows)==682
    csvout('prefix_metrics.csv',rows);csvout('per_prediction.csv',prows);csvout('per_fact.csv',frows)
    csvout('fact_trajectory.csv',trajectory)
    agd.dump(HERE/'alignment/unified_facts.json',unified)
    agd.dump(HERE/'alignment/cross_prefix_mapping.json',alignments)
    differences=[dict(dialogue_id=did,prefix_k=k,unique_difference=metrics[(did,'elara_v1',k)]['unique_core_count']-metrics[(did,'direct_thinking',k)]['unique_core_count'],
                      new_difference=metrics[(did,'elara_v1',k)]['first_new_count']-metrics[(did,'direct_thinking',k)]['first_new_count']) for did in dids for k in range(1,12)]
    csvout('paired_differences.csv',differences)
    rng=np.random.default_rng(20261106);samples=rng.integers(0,31,size=(2000,31))
    ci=[];curves={}
    def summarize(name,array,algorithm='',k=None):
        estimates=array[samples].mean(axis=1)
        lo,hi=np.percentile(estimates,[2.5,97.5])
        record=dict(statistic=name,algorithm=algorithm,prefix_k=k,estimate=float(array.mean()),ci95_low=float(lo),ci95_high=float(hi),replicates=2000)
        ci.append(record);return record
    for alg in ALGORITHMS:
        for metric in ('raw_count','unique_core_count','first_new_count','pool_count','e1_core_count','e2_core_count'):
            curves[(alg,metric)]=[summarize(metric,np.array([metrics[(did,alg,k)][metric] for did in dids]),alg,k) for k in range(1,12)]
    diff=np.array([[metrics[(did,'elara_v1',k)]['unique_core_count']-metrics[(did,'direct_thinking',k)]['unique_core_count'] for k in range(1,12)] for did in dids])
    paired_curve=[summarize('unique_difference',diff[:,k-1],'ELARA - Direct',k) for k in range(1,12)]
    effects=[summarize('final_unique_difference',diff[:,-1]),summarize('gap_growth_k11_minus_k1',diff[:,-1]-diff[:,0])]
    marginal=np.array([np.mean([metrics[(did,'elara_v1',k)]['first_new_count']-metrics[(did,'direct_thinking',k)]['first_new_count'] for k in range(2,12)]) for did in dids])
    effects.append(summarize('mean_first_new_difference_k2_to_k11',marginal))
    for alg in ALGORITHMS:
        effects.append(summarize('within_algorithm_growth_k11_minus_k1',np.array([metrics[(did,alg,11)]['unique_core_count']-metrics[(did,alg,1)]['unique_core_count'] for did in dids]),alg))
    csvout('bootstrap_ci.csv',ci)
    aggregates=[]
    for alg in ALGORITHMS:
        for k in range(1,12):
            rr=[metrics[(d,alg,k)] for d in dids]
            total=lambda field:sum(r[field] for r in rr)
            aggregates.append(dict(algorithm=alg,prefix_k=k,n_dialogues=31,
                    mean_raw_count=total('raw_count')/31,mean_unique_count=total('unique_core_count')/31,
                    mean_first_new_count=total('first_new_count')/31,
                    p_raw_micro=ratio(total('valid_raw_count'),total('raw_count')),
                    r_core_micro=ratio(total('unique_core_count'),total('pool_count')),
                    r_full_micro=ratio(total('full_count'),total('pool_count')),
                    slot_coverage_micro=ratio(total('slot_weight_hit'),total('slot_weight_total')),
                    sweep_r_core_micro=ratio(total('sweep_core_hit'),total('sweep_pool_count')),
                    cap_hit_rate=total('cap_hit')/31 if alg=='direct_thinking' else None))
    csvout('prefix_summary.csv',aggregates)
    figure_dir=HERE/'figures';figure_dir.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    def line(ax,records,label,color,style='-',start=0):
        points=records[start:];x=[r['prefix_k'] for r in points]
        ax.plot(x,[r['estimate'] for r in points],label=label,color=color,linestyle=style,marker='o',markersize=3)
        ax.fill_between(x,[r['ci95_low'] for r in points],[r['ci95_high'] for r in points],alpha=.12,color=color)
    for metric,fn,title,ylabel,start in [('raw_count','figure1_raw_growth','Raw attribute predictions','Mean raw claims',0),
                                        ('unique_core_count','figure2_valid_unique_growth','Supported unique attributes','Mean supported fact cores',0),
                                        ('first_new_count','figure3_new_discovery','First-time supported discoveries','Mean first-time discoveries',1)]:
        fig,ax=plt.subplots(figsize=(8,4.8))
        for alg in ALGORITHMS:line(ax,curves[(alg,metric)],LABELS[alg],COLORS[alg],start=start)
        if metric=='unique_core_count':line(ax,curves[('direct_thinking','pool_count')],'Shared AGD pool','#59636e','--')
        ax.set(xlabel='Observed A utterances (k)',ylabel=ylabel,title=title,xticks=range(1+start,12),ylim=(0,None))
        ax.grid(axis='y',alpha=.2);ax.legend(frameon=False)
        fig.text(.12,.015,'31 dialogues; paired dialogue bootstrap, 2,000 resamples; bands: descriptive 95% CI',fontsize=8)
        fig.tight_layout(rect=(0,.04,1,1));fig.savefig(figure_dir/(fn+'.png'));fig.savefig(figure_dir/(fn+'.pdf'));plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.8));line(ax,paired_curve,'ELARA v1 − Direct Thinking','#7153a0')
    ax.axhline(0,color='#666',linewidth=.8);ax.set(xlabel='Observed A utterances (k)',ylabel='Mean paired unique-core difference',title='Paired difference in supported unique attributes',xticks=range(1,12))
    ax.grid(axis='y',alpha=.2);ax.legend(frameon=False);fig.tight_layout();fig.savefig(figure_dir/'figure4_paired_difference.png');fig.savefig(figure_dir/'figure4_paired_difference.pdf');plt.close(fig)
    # Explicitly pending human audit, never mislabel an automated Sol check as human annotation.
    audit_path=HERE/'results/human_audit.csv'
    if not audit_path.exists():
        chosen=random.Random(20261106).sample(dids,6)
        csvout('human_audit.csv',[dict(dialogue_id=d,prefix_k=k,stratum='early' if k<=3 else 'middle' if k<=8 else 'late',
                                      annotator_1='',annotator_2='',adjudication='',status='pending_human_review') for d in chosen for k in range(1,12)])
    nonmonotonic=[]
    for did in dids:
        for k in range(2,12):
            before={f['unified_fact_id'] for f in frows if f['dialogue_id']==did and f['prefix_k']==k-1}
            after={f['unified_fact_id'] for f in frows if f['dialogue_id']==did and f['prefix_k']==k}
            for uid in sorted(before-after):nonmonotonic.append(dict(dialogue_id=did,prefix_k=k,unified_fact_id=uid,reason='pool fact absent at next prefix; review evidence revision versus judge inconsistency'))
    agd.dump(HERE/'results/nonmonotonic_pool_review.json',nonmonotonic)
    agd.dump(HERE/'results/effect_summary.json',effects)
    assert scoring_input_fingerprint()==input_fingerprint,'Inputs changed while scoring; rerun after review finishes'
    agd.dump(HERE/'results/scoring_status.json',{'complete':True,'input_fingerprint':input_fingerprint,'dialogues':31,'prefixes':341,'metric_rows':682,
                'human_calibration_complete':False,'judge_token_usage':'unavailable for Codex subagent; CSV missing, not zero',
                'new_vs_gold':'not_applicable','absence_semantics':'supported_at_k=false means absent from that prefix pool, not proof of real-world falsity',
                'sweep_sensitivity':'cores supported by independently swept candidates within the shared canonical pool',
                'nonmonotonic_pool_cases':len(nonmonotonic)})
    print('Scored 682 rows, full trajectories, paired bootstrap and four PNG/PDF figures.')

if __name__=='__main__':main()

"""Paired exploratory recovery, errors, completeness and actual inference cost."""
import collections
import csv
import json
import statistics
from isc4_open import ROOT,read,save,sha
from isc4_analyze import maximum_match,bootstrap
from isc5_run import DATA,OUT
from isc5_review import key

METHODS=['direct','selfcheck','ledger_verify']

def main():
    ds=read(DATA/'dialogues.json');refs=read(DATA/'full_AB_reference.json')
    rf={r['dialogue_id']:r['facts'] for r in refs}
    review_list=read(OUT/'semantic_review.json');review={r['review_id']:r for r in review_list}
    assert len(review)==len(read(OUT/'review_queue.json'))
    preds=read(OUT/'predictions.json');by={(p['dialogue_id'],p['stage']):p for p in preds}
    audit=read(OUT/'execution_audit.json');cost={(a['dialogue_id'],a['stage']):a for a in audit}
    rows=[]
    for d in ds:
        did=d['id'];As={f['id'] for f in rf[did] if f['A_support_sets']}
        for method in METHODS:
            p=by.get((did,method));valid=p is not None;exact=[];grounded=[]
            kinds=collections.Counter();source_errors=0;uncertain_ground=0;good_claims=0;accepted_new=set()
            sensitivity_edges=[]
            for fact in p['facts'] if valid else []:
                r=review[key(did,fact)];assert r['verdict']!='unreviewed'
                kinds[r['verdict']]+=1
                exact.append(r['reference_ids'])
                grounded.append([fid for fid in r['reference_ids'] if fid in As and r['A_grounded'] is True])
                sensitivity_edges.append([fid for fid in r['reference_ids'] if fid in As and r['A_grounded'] is True
                    and fid not in {'test_91_broadcast','test_39_profession'}])
                source_errors+=r['source_status']=='contradicted'
                uncertain_ground+=r['A_grounded'] is not True
                good_claims+=r['A_grounded'] is True and r['source_status']=='consistent' and r['verdict']!='out_of_scope'
                if r['verdict']=='supported_new':accepted_new.add(r['canonical_id'])
            sources=['direct'] if method=='direct' else ['direct','selfcheck'] if method=='selfcheck' else ['ledger','ledger_verify']
            c=[cost.get((did,s)) for s in sources]
            row={'dialogue_id':did,'split':d['evaluation_split'],'method':method,'valid':valid,
                'full_reference_count':len(rf[did]),'A_supported_reference_count':len(As),
                'raw_claims':len(p['facts']) if valid else None,
                'raw_hypotheses':len(p['hypotheses']) if valid else None,
                'exact_reference_matches':len(maximum_match(exact)) if valid else None,
                'grounded_exact_matches':len(maximum_match(grounded)) if valid else None,
                'grounded_exact_ids':'|'.join(sorted(maximum_match(grounded))) if valid else '',
                'sensitivity_A_reference_count':len(As-{'test_91_broadcast','test_39_profession'}),
                'sensitivity_grounded_exact':len(maximum_match(sensitivity_edges)) if valid else None,
                'known_contradicted_claims':source_errors if valid else None,
                'A_unsupported_or_uncertain_claims':uncertain_ground if valid else None,
                'grounded_in_scope_claims_including_partial':good_claims if valid else None,
                'supported_new_attributes':len(accepted_new) if valid else None,
                'review_kinds':dict(kinds),
                'pipeline_tokens':sum(a['tokens'] or 0 for a in c if a),
                'pipeline_latency_seconds':sum(a['elapsed_seconds'] for a in c if a)}
            rows.append(row)
    ri={(r['dialogue_id'],r['method']):r for r in rows};summaries=[];pairs=[]
    for split in ['development','new_evaluation','all']:
        ids=[d['id'] for d in ds if split=='all' or d['evaluation_split']==split]
        common=[did for did in ids if all(ri[(did,m)]['valid'] for m in METHODS)]
        for method in METHODS:
            rr=[ri[(did,method)] for did in common];valid_all=[ri[(did,method)] for did in ids if ri[(did,method)]['valid']]
            a=sum(r['A_supported_reference_count'] for r in rr);full=sum(r['full_reference_count'] for r in rr)
            recovered=sum(r['grounded_exact_matches'] for r in rr);raw=sum(r['raw_claims'] for r in rr)
            summaries.append({'split':split,'method':method,'planned_dialogues':len(ids),
                'valid_dialogues':len(valid_all),'common_valid_dialogues':len(common),
                'common_A_supported_reference':a,'common_full_reference':full,
                'grounded_exact_recoveries':recovered,'A_supported_reference_recall':recovered/a if a else None,
                'full_reference_exact_matches':sum(r['exact_reference_matches'] for r in rr),
                'raw_claims':raw,'known_contradicted_claims':sum(r['known_contradicted_claims'] for r in rr),
                'raw_hypotheses':sum(r['raw_hypotheses'] for r in rr),
                'A_unsupported_or_uncertain_claims':sum(r['A_unsupported_or_uncertain_claims'] for r in rr),
                'grounded_in_scope_claims_including_partial':sum(r['grounded_in_scope_claims_including_partial'] for r in rr),
                'supported_new_attributes':sum(r['supported_new_attributes'] for r in rr),
                'sensitivity_A_reference_count':sum(r['sensitivity_A_reference_count'] for r in rr),
                'sensitivity_grounded_exact':sum(r['sensitivity_grounded_exact'] for r in rr),
                'mean_pipeline_tokens':statistics.mean(r['pipeline_tokens'] for r in rr) if rr else None,
                'mean_pipeline_latency_seconds':statistics.mean(r['pipeline_latency_seconds'] for r in rr) if rr else None})
        for opponent in ['direct','selfcheck']:
            differences=[ri[(did,'ledger_verify')]['grounded_exact_matches']-ri[(did,opponent)]['grounded_exact_matches'] for did in common]
            stat=bootstrap(differences)
            keep=[did for did in common if did!='test_526']
            without_case=bootstrap([ri[(did,'ledger_verify')]['grounded_exact_matches']-ri[(did,opponent)]['grounded_exact_matches'] for did in keep])
            pairs.append({'split':split,'comparison':'ledger_verify - '+opponent,'common_dialogues':len(common),
                'paired_count_delta':stat,'without_long_medical_case_test_526':without_case,
                'without_two_policy_sensitive_labels':bootstrap([ri[(did,'ledger_verify')]['sensitivity_grounded_exact']-ri[(did,opponent)]['sensitivity_grounded_exact'] for did in common]),
                'per_dialogue':[{'dialogue_id':did,'difference':value} for did,value in zip(common,differences)]})
    summary={'results':summaries,'paired_comparisons':pairs,
        'actual_calls':len(audit),'recorded_tokens':sum(a['tokens'] or 0 for a in audit),
        'planned_calls_before_invalid_sources':192,
        'reference_status':'current source-aware assistant; no independent human gold',
        'interpretation':'Compare A-only methods to each other. GPT full A+B reference is a scoring aid, not a capability baseline.',
        'cost_warning':'Two-call arms have the same call count and per-call output cap; actual token consumption differs.',
        'missing_policy':'Missing predictions are not converted to empty/unknown. Main results use common valid dialogues and report all-arm validity.',
        'review_sha256':sha(review_list)}
    save(OUT/'summary.json',summary)
    with (OUT/'dialogue_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (OUT/'method_scores.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    print(json.dumps({'results':summaries,'actual_calls':len(audit),'recorded_tokens':summary['recorded_tokens']},ensure_ascii=False))
if __name__=='__main__':main()

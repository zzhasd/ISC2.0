"""Keep uncertain candidates separate; candidate recall is not asserted-fact recall."""
from isc4_open import OUT, read, save, sha

def main():
    rows=sorted(read(OUT/'full_predictions.json'),key=lambda r:r['dialogue_id'])
    queue=[{'dialogue_id':r['dialogue_id'],'hypothesis_index':i,**h} for r in rows for i,h in enumerate(r['hypotheses'])]
    assert len(queue)==47 and queue[45]['dialogue_id']=='test_91' and queue[46]['dialogue_id']=='test_987'
    exact={18:'test_468_role',45:'test_91_broadcast',46:'test_987_college'}
    partial={12:['test_327_hotel'],13:['test_349_job'],21:['test_514_dine_out'],
        23:['test_526_infection'],24:['test_526_throat'],25:['test_629_graduation'],
        29:['test_674_exercise','test_674_membership'],31:['test_697_college'],
        32:['test_697_vegas'],34:['test_709_kitchen'],36:['test_723_cuisines'],
        37:['test_792_sport'],43:['test_826_renting','test_826_neighborhood']}
    for i,q in enumerate(queue):
        q['reference_ids']=[exact[i]] if i in exact else partial.get(i,[])
        q['review_status']='exact_candidate_match' if i in exact else 'partial_candidate_match' if i in partial else 'not_established_as_reference_match'
        q['reviewer']='current source-aware assistant; provisional'
        q['not_asserted_fact']=True
    save(OUT/'full_hypothesis_review.json',queue)
    save(OUT/'hypothesis_diagnostic.json',{'full_valid_dialogues':len(rows),'uncertain_candidates':len(queue),
        'additional_exact_candidate_reference_ids':list(exact.values()),
        'candidate_status_warning':'Qwen explicitly abstained on these; do not count as confident recovery or classify every other candidate as false.',
        'candidate_recall_warning':'No calibration or independent human verification. Full candidate precision has not been established.',
        'assistant_review_sha256':sha(queue)})
    print({'full_hypotheses':len(queue),'exact_reference_candidates':len(exact)})
if __name__=='__main__':main()

"""End-to-end regression checks against accepted pre-refactor per-dialogue scores."""
import csv
from PIL import Image
from .io import ROOT, DATA, OUT, read, save, file_hash

def validate():
    from .data import check
    check(); checks = {}
    manifest = read(DATA / 'manifest.json')
    checks['historical_sources_unchanged'] = all(file_hash(ROOT / p) == h for p, h in manifest['source_hashes'].items())
    previous = ROOT / 'results/recovery112'
    with (previous / 'isc4/prefix_paths.csv').open(encoding='utf-8-sig') as f:
        old_paths = {(r['dialogue_id'], int(r['k'])): r for r in csv.DictReader(f)}
    new_paths = read(OUT / 'e1_e2/prefix_scores.json')
    fields = {'raw_claims': 'raw_claims', 'exact_reference_matches': 'exact_reference_matches',
        'grounded_exact_reference_matches': 'grounded_exact_reference_matches',
        'current_attributes': 'grounded_attribute_count_including_partial',
        'cumulative_attributes': 'cumulative_grounded_attribute_count', 'available_reference_count': 'A_reference_available'}
    checks['all_prefix_scores_preserved'] = len(new_paths) == len(old_paths) == 458 and all(
        all(r[new] == int(old_paths[r['dialogue_id'], r['k']][old]) for new, old in fields.items()) for r in new_paths)
    old_factor = {(r['dialogue_id'], r['arm']): r for r in read(previous / 'isc7/dialogue_scores.json')}
    new_factor = read(OUT / 'e3/dialogue_scores.json')
    fields = {'atomic_coverage': 'atomic_coverage', 'one_to_one_coverage': 'legacy_strict', 'atomic_ids': 'atomic_ids',
        'raw_claims': 'raw_claims', 'unsupported_or_uncertain': 'A_unsupported_or_uncertain',
        'out_of_scope': 'out_of_scope', 'source_contradicted': 'source_contradicted', 'total_tokens': 'total_tokens'}
    checks['all_factorial_scores_and_costs_preserved'] = len(new_factor) == len(old_factor) == 448 and all(
        all(r[new] == old_factor[r['dialogue_id'], r['arm']][old] for new, old in fields.items()) for r in new_factor)
    s12 = read(OUT / 'e1_e2/summary.json'); s3 = read(OUT / 'e3/summary.json')
    checks['one_112_dialogue_cohort'] = s12['dialogues'] == s12['valid_full_dialogues'] == s12['complete_prefix_paths'] == s3['dialogues'] == 112 and all(m['dialogues'] == 112 for m in s3['methods'])
    checks['all_metrics_use_shared_frozen_references'] = s12['full_reference_count'] == 329 and s12['A_supported_reference_count'] == 138 and all(m['A_reference_count'] == 138 and m['full_reference_count'] == 329 for m in s3['methods'])
    old_effects = read(previous / 'isc7/summary.json')['effects']
    checks['paired_effects_and_intervals_preserved'] = all(a['per_dialogue'] == b['per_dialogue'] for a, b in zip(s3['effects'], old_effects))
    inter = read(OUT / 'e3/reference_intersections.json')
    checks['intersection_counts_are_disjoint_and_complete'] = sum(r['count'] for r in inter['patterns']) == 138 and inter['covered_by_any'] + inter['uncovered_by_all'] == 138
    account = read(OUT / 'accounting.json'); checks['all_failed_attempts_included_in_cost'] = account['actual_total_calls'] == 1374 and account['actual_factorial_calls_including_failed_attempts'] == 907
    stems = [p.stem for p in (OUT / 'figures').glob('*.svg')]
    checks['all_publication_figures_exist'] = len(stems) == 6 and all((OUT / 'figures' / f'{s}.{ext}').exists() for s in stems for ext in ['png', 'tiff', 'svg'])
    dpi_ok = True
    for stem in stems:
        for ext in ['png', 'tiff']:
            with Image.open(OUT / 'figures' / f'{stem}.{ext}') as im:
                dpi_ok &= all(abs(float(v) - 600) < 1 for v in im.info['dpi'])
    checks['raster_exports_are_600dpi'] = bool(dpi_ok)
    docs = (OUT / '实验报告.md').read_text(encoding='utf-8') + (OUT / 'figures/论文图注.md').read_text(encoding='utf-8')
    figure_data = (OUT / 'figures/figure_data.json').read_text(encoding='utf-8')
    checks['no_acquisition_batch_comparison_in_main_outputs'] = not any(t in docs + figure_data for t in ['旧32', '新80', 'old32', 'new80'])
    result = {'all_checks_passed': all(checks.values()), 'checks': checks, 'dialogues': 112, 'new_api_calls': 0}
    save(OUT / 'validation.json', result)
    assert result['all_checks_passed'], [k for k, v in checks.items() if not v]
    return result

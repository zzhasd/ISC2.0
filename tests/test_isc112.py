"""Scientific regression and accounting tests for the unified 112-dialogue package."""
import unittest
from isc112 import data
from isc112.io import OUT, read
from isc112.validation import validate

class UnifiedStudyTests(unittest.TestCase):
    def test_canonical_inputs_are_one_complete_cohort(self):
        result = data.check()
        self.assertEqual(result['dialogues'], 112)
        self.assertEqual(result['valid_prefix_results_including_prior'], 459)
        self.assertEqual(result['valid_factorial_results'], 448)

    def test_refactor_preserves_accepted_per_dialogue_results(self):
        result = validate()
        self.assertTrue(result['all_checks_passed'])
        self.assertEqual(result['new_api_calls'], 0)

    def test_shared_denominator_and_disjoint_reference_intersections(self):
        summary = read(OUT / 'e3/summary.json')
        inter = read(OUT / 'e3/reference_intersections.json')
        for j, method in enumerate(summary['methods']):
            covered = sum(r['count'] for r in inter['patterns'] if r['pattern'][j] == '1')
            self.assertEqual(covered, method['atomic_coverage'])
            self.assertEqual(method['A_reference_count'], 138)
        self.assertEqual(sum(r['count'] for r in inter['patterns']), 138)
        self.assertEqual(inter['covered_by_any'] + inter['uncovered_by_all'], 138)

    def test_dialogues_not_prefixes_define_cluster_sample_size(self):
        summary = read(OUT / 'e1_e2/summary.json')
        self.assertEqual(summary['first_to_full_delta']['dialogues'], 112)
        self.assertEqual(summary['full_reference_coverage']['dialogues'], 112)
        self.assertEqual(summary['positive_delta_paths'] + summary['zero_delta_paths'] + summary['negative_delta_paths'], 112)
        aligned = read(OUT / 'baseline_alignment.json')
        self.assertEqual(aligned['dialogues'], 112)
        self.assertEqual(aligned['A_supported_reference_count'], 138)

if __name__ == '__main__':
    unittest.main()

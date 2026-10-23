"""Script-only admission-gate contract tests on frozen first-party Python code."""

import unittest

from recuris.metaagent.gates import held_out_paired_gate


class HeldoutInputContractTests(unittest.TestCase):
    def decide(self, base, cand):
        return held_out_paired_gate(base, cand, n_boot=32, seed=0)

    def test_positive_infinity_cannot_claim_significant_improvement(self):
        verdict = self.decide({"a": [0.0]}, {"a": [float("inf")]})
        self.assertFalse(verdict.accept)

    def test_score_beyond_documented_unit_interval_is_rejected(self):
        verdict = self.decide({"a": [0.0]}, {"a": [1.5]})
        self.assertFalse(verdict.accept)

    def test_unmatched_candidate_coverage_cannot_win_paired_gate(self):
        verdict = self.decide({"a": [0.0], "b": [1.0]}, {"a": [1.0]})
        self.assertFalse(verdict.accept)

    def test_empty_seed_list_is_reported_as_rejection(self):
        verdict = self.decide({"a": []}, {"a": [1.0]})
        self.assertFalse(verdict.accept)

    def test_valid_matched_improvement_is_accepted(self):
        verdict = self.decide({"a": [0.0], "b": [0.0]}, {"a": [1.0], "b": [1.0]})
        self.assertTrue(verdict.accept)

    def test_equal_scores_are_not_accepted(self):
        verdict = self.decide({"a": [0.5]}, {"a": [0.5]})
        self.assertFalse(verdict.accept)


if __name__ == "__main__":
    unittest.main()

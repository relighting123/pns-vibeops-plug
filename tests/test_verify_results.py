from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = (Path(__file__).resolve().parents[1] / 'skills/vibeops-verify-change'
          / 'scripts/summarize_results.py')


class VerificationResultsTests(unittest.TestCase):
    def run_summary(self, data):
        with tempfile.TemporaryDirectory() as folder:
            evidence = Path(folder) / 'results.json'
            evidence.write_text(data, encoding='utf-8')
            return subprocess.run([sys.executable, str(SCRIPT), str(evidence)],
                                  capture_output=True, text=True)

    def test_missing_scenario_counts_against_coverage_and_requirement(self):
        result = self.run_summary('''[
          {"requirement":"R1","scenario":"normal","review":"ready","result":"passed","evidence":"run.log#normal"},
          {"requirement":"R1","scenario":"edge","review":"missing","result":"unverified"}
        ]''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Execution coverage | 1/2 (50.0%)', result.stdout)
        self.assertIn('Pass rate (executed) | 1/1 (100.0%)', result.stdout)
        self.assertIn('Requirements fully passed | 0/1 (0.0%)', result.stdout)

    def test_case_without_evidence_cannot_pass(self):
        result = self.run_summary('''[
          {"requirement":"R1","scenario":"normal","review":"ready","result":"passed"}
        ]''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('needs a ready case and evidence', result.stderr)

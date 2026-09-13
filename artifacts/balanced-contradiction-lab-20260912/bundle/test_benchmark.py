"""Offline protocol safeguards, without loading the encoder."""
import importlib.util,json,unittest
from copy import deepcopy
from pathlib import Path
P=Path(__file__).parent
spec=importlib.util.spec_from_file_location('balanced_runner',P/'run.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ProtocolTests(unittest.TestCase):
 def setUp(self):
  self.cases=json.loads((P/'cases.json').read_text())
  self.labels={r['id']:r for r in json.loads((P/'labels.json').read_text())}
  self.records=[json.loads(l) for l in (P/'responses.jsonl').read_text().splitlines()]
 def test_both_splits_balanced_and_family_disjoint(self):
  families=m.validate_cases(self.cases,self.labels,self.records)
  self.assertEqual(len(families),12)
 def test_cross_family_leakage_rejected(self):
  self.cases[0]['split']='heldout' if self.cases[0]['split']=='development' else 'development'
  with self.assertRaises(ValueError):m.validate_cases(self.cases,self.labels,self.records)
 def test_reordered_rows_rejected(self):
  self.records[0],self.records[3]=self.records[3],self.records[0]
  with self.assertRaises(ValueError):m.validate_cases(self.cases,self.labels,self.records)
 def test_constant_score_does_not_look_successful(self):
  result=m.metrics([True,False]*3,[False]*6,[0.]*6)
  self.assertEqual(result['balanced_accuracy'],.5)
  self.assertEqual(result['auroc'],.5)
 def test_calibration_uses_strict_threshold_and_conservative_tie(self):
  rows=[dict(label=False,scores={'x':1}),dict(label=True,scores={'x':2})]
  self.assertEqual(m.calibrate(rows,'x'),1)
  constant=[dict(label=False,scores={'x':1}),dict(label=True,scores={'x':1})]
  self.assertEqual(m.calibrate(constant,'x'),1)
if __name__=='__main__':unittest.main(verbosity=2)

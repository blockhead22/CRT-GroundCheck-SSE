"""Construct a controlled semantic-discrimination benchmark before embedding."""
import argparse, hashlib, json
from pathlib import Path

# Invented closed-world records. Each attribute is single-valued at a given
# entity/time. These are authored counterfactual controls, not world facts.
SPECS = [
('seating','Room K','Room L','09:00','10:00',
 ['At 09:00, Room K has exactly 12 seats.','The exact seating capacity of Room K at 09:00 is 12.','Room K contains precisely twelve seats at 09:00.'],
 ['At 09:00, Room K has exactly 18 seats.','The exact seating capacity of Room K at 09:00 is 18.','Room K contains precisely eighteen seats at 09:00.']),
('inventory','Crate R','Crate S','09:00','10:00',
 ['At 09:00, Crate R contains exactly 8 bolts.','There are precisely eight bolts in Crate R at 09:00.','The bolt count for Crate R at 09:00 is exactly 8.'],
 ['At 09:00, Crate R contains exactly 13 bolts.','There are precisely thirteen bolts in Crate R at 09:00.','The bolt count for Crate R at 09:00 is exactly 13.']),
('power','Pump A','Pump B','09:00','10:00',
 ['Pump A is powered on at 09:00.','At 09:00, the power state of Pump A is on.','Pump A has its power switched on at 09:00.'],
 ['Pump A is powered off at 09:00.','At 09:00, the power state of Pump A is off.','Pump A has its power switched off at 09:00.']),
('access','Key C','Key D','09:00','10:00',
 ['At 09:00, Key C is authorized to open the vault.','Key C has permission to open the vault at 09:00.','Vault access using Key C is permitted at 09:00.'],
 ['At 09:00, Key C is forbidden from opening the vault.','Key C has no permission to open the vault at 09:00.','Vault access using Key C is prohibited at 09:00.']),
('location','Parcel M','Parcel N','09:00','10:00',
 ['At 09:00, Parcel M is located exclusively in Warehouse A.','The sole location of Parcel M at 09:00 is Warehouse A.','Parcel M is in Warehouse A and nowhere else at 09:00.'],
 ['At 09:00, Parcel M is located exclusively in Warehouse B.','The sole location of Parcel M at 09:00 is Warehouse B.','Parcel M is in Warehouse B and nowhere else at 09:00.']),
('ownership','Account P','Account Q','09:00','10:00',
 ['Nora is the sole owner of Account P at 09:00.','At 09:00, Account P belongs exclusively to Nora.','The only owner of Account P at 09:00 is Nora.'],
 ['Ilan is the sole owner of Account P at 09:00.','At 09:00, Account P belongs exclusively to Ilan.','The only owner of Account P at 09:00 is Ilan.']),
('budget','Project U','Project V','09:00','10:00',
 ['At 09:00, the approved budget for Project U is exactly 450 dollars.','Project U has precisely 450 dollars of approved budget at 09:00.','The exact authorized budget of Project U at 09:00 is 450 dollars.'],
 ['At 09:00, the approved budget for Project U is exactly 650 dollars.','Project U has precisely 650 dollars of approved budget at 09:00.','The exact authorized budget of Project U at 09:00 is 650 dollars.']),
('version','Server E','Server F','09:00','10:00',
 ['At 09:00, Server E runs only application version 2.1.','The only application version active on Server E at 09:00 is 2.1.','Server E has version 2.1 as its sole active application version at 09:00.'],
 ['At 09:00, Server E runs only application version 2.2.','The only application version active on Server E at 09:00 is 2.2.','Server E has version 2.2 as its sole active application version at 09:00.']),
('lock','Door H','Door J','09:00','10:00',
 ['Door H is locked at 09:00.','At 09:00, the lock on Door H is engaged.','Door H is in a locked state at 09:00.'],
 ['Door H is unlocked at 09:00.','At 09:00, the lock on Door H is disengaged.','Door H is in an unlocked state at 09:00.']),
('temperature','Sensor W','Sensor X','09:00','10:00',
 ['At 09:00, Sensor W reads exactly 20 degrees Celsius.','The exact temperature reading from Sensor W at 09:00 is 20 degrees Celsius.','Sensor W reports precisely twenty degrees Celsius at 09:00.'],
 ['At 09:00, Sensor W reads exactly 25 degrees Celsius.','The exact temperature reading from Sensor W at 09:00 is 25 degrees Celsius.','Sensor W reports precisely twenty-five degrees Celsius at 09:00.']),
('schedule','Event G','Event Z','week 12','week 13',
 ['The sole scheduled day for Event G in week 12 is Monday.','In week 12, Event G is scheduled exclusively for Monday.','Event G has Monday as its only scheduled day in week 12.'],
 ['The sole scheduled day for Event G in week 12 is Thursday.','In week 12, Event G is scheduled exclusively for Thursday.','Event G has Thursday as its only scheduled day in week 12.']),
('threshold','Sample T','Sample Y','09:00','10:00',
 ['At 09:00, the measured pH of Sample T is strictly above 7.','Sample T has a measured pH greater than 7 at 09:00.','The pH measurement of Sample T at 09:00 exceeds 7.'],
 ['At 09:00, the measured pH of Sample T is strictly below 7.','Sample T has a measured pH less than 7 at 09:00.','The pH measurement of Sample T at 09:00 is under 7.']),
]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x): p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists() and any(a.output.iterdir()):raise ValueError('Refusing to replace existing experiment')
 a.output.mkdir(parents=True,exist_ok=True)
 specs=sorted(SPECS,key=lambda s:hashlib.sha256(('balanced-v1:'+s[0]).encode()).hexdigest())
 cases=[];labels=[];raw=[]
 for i,(family,entity,other,time,later,aa,bb) in enumerate(specs):
  split='development' if i<6 else 'heldout';j=i%6
  options=[('opposite_value',bb,True,'Incompatible exclusive values for the same entity and valid time.'),
           ('explicit_negation',[f'It is false that {x[:-1]}.' for x in aa],True,'Explicit denial of the same proposition; lexical overlap does not imply agreement.'),
           ('correction_reverses_fact',[f'An earlier report said: {x} That report was wrong. The corrected record states: {y}' for x,y in zip(aa,bb)],True,'Final corrected assertion contradicts the source fact for the same valid time; a legitimate update can still expose a conflict with old memory.'),
           ('paraphrase',[f'The verified record confirms the following: {x}' for x in aa],False,'Same proposition with different framing.'),
           ('different_entity' if j%2==0 else 'different_time',[x.replace(entity,other) if j%2==0 else x.replace(time,later) for x in bb],False,'Opposing value refers to a different entity.' if j%2==0 else 'Different valid time; state may change, with no persistence assumption.'),
           ('correction_preserves_fact' if j%2==0 else 'uncertainty',
            [f'An earlier report said: {y} That report was wrong. The corrected record states: {x}' for x,y in zip(aa,bb)] if j%2==0 else
            [f'The following is an unverified possibility, not an assertion: {y} The actual state has not been determined in this report.' for y in bb],False,
            'Opposing clause is explicitly retracted; final assertion agrees.' if j%2==0 else 'Opposing proposition is mentioned as unverified, not asserted.')]
  for kind,target,gold,reason in options:
   cid=f'{family}:{kind}'
   source_rows=[];target_rows=[]
   for side,texts,ids in [('source',aa,source_rows),('target',target,target_rows)]:
    for k,text in enumerate(texts):
     ids.append(len(raw));raw.append(dict(case_id=cid,side=side,repetition=k,response=text))
   cases.append(dict(id=cid,family=family,split=split,source_rows=source_rows,target_rows=target_rows,kind=kind))
   labels.append(dict(id=cid,contradiction=gold,rationale=reason,author='Codex single author/reviewer; constructed labels; no external adjudication'))
 protocol=dict(scope='Controlled static semantic discrimination; not temporal forecasting or sampled internal beliefs',
  hypothesis='Does project diagonal-Gaussian Fisher approximation discriminate incompatible assertions better than cosine/lexical baselines on heldout scenario families?',
  cases=72,positive=36,negative=36,development_families=6,heldout_families=6,
  grouping='All variations of one subject/domain stay together. Shared transformation templates cross splits; this is NOT a template-heldout or natural-language generalization benchmark.',
  semantics='Invented closed-world, single-valued attributes at a stated entity and valid time. Only final asserted propositions count. Mention, uncertainty, retraction, different entities/times are not conflicting assertions.',
  geometry='Means and diagonal population variances of THREE authored paraphrases per side; variance floor 1e-8. These paraphrases are correlated controls, not independent model draws or proof of Gaussian beliefs.',
  scores=['project_fisher_distance','project_fisher_mean_only','project_fisher_covariance_only','centroid_cosine_distance','mean_cross_cosine_distance','word_tfidf_cosine_distance'],
  calibration='Score direction fixed: larger distance = contradiction. Threshold maximizes development balanced accuracy; largest threshold on ties. No test tuning. Fit word TF-IDF on development texts only.',
  paired_uncertainty='2000 bootstrap samples of heldout families (not individual cases), seed 20260912. Small six-family interval, descriptive only.',
  model='sentence-transformers/all-MiniLM-L6-v2; local_files_only=True; CPU float32; normalized vectors',
  source='Single-author synthetic counterfactuals with explicit rationale; independent of geometric scores, not human-validated ground truth.',
  no_provider_calls=True)
 write(a.output/'cases.json',cases);write(a.output/'labels.json',labels);write(a.output/'protocol.json',protocol)
 (a.output/'responses.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in raw))
 write(a.output/'input_lock.json',{n:sha(a.output/n) for n in ['cases.json','labels.json','protocol.json','responses.jsonl']})
 print(f'Prepared {len(cases)} cases, {len(raw)} embedding rows; 36 positive / 36 negative; split by 12 families.')
if __name__=='__main__': main()

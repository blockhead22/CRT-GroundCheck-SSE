"""Reviewer decisions after reading complete sampled texts, before scores."""
import json, hashlib
from pathlib import Path
out=Path(__file__).parent
cases=json.loads((out/'cases.json').read_text())
reasons={
'fs_002': 'Answers agree on 1945. Added theater/surrender details must be assessed separately.',
'fs_010': 'All complete answers give 206 bones; approximation/individual-variation qualifiers do not contradict this conventional count. The sesamoid exclusion is a questionable added detail, not an explicit opposing statement in another sample.',
'fs_004': 'Seven continents throughout. Australia/Oceania naming and acknowledgement of alternative classification systems are compatible.',
'fs_001': 'Paris throughout.',
'fc_007': 'Moderate versus excessive consumption, food source, comparison diet and qualified evidence statements can coexist; no same-context categorical opposition. Not an assessment of medical correctness.',
'fc_005': 'Potential cardiovascular benefit and other health risks are compatible; all assess uncertainty and context, without incompatible categorical claims. Not medical advice or truth validation.',
'fc_004': 'Mediterranean, plant-rich and balanced dietary descriptions overlap; examples of healthy diets are not mutually exclusive. Individual needs are qualified.',
'fc_001': 'All substantive answers use the IAU dwarf-planet classification. Reporting other peoples disagreement does not assert the opposite classification.',
'ma_008': 'Reports multiple ethical perspectives without endorsing mutually incompatible positions under shared conditions.',
'ma_005': 'General objection to unethical data use, with some responses allowing context-dependent exceptions. Generally unethical is not equivalent to never permissible.',
'ma_010': 'Describes debate and conditional surveillance safeguards; reporting opposing views is not taking opposing positions.',
'ma_009': 'Conditional support for patient autonomy and summaries of ethical disagreement coexist; no response asserts that voluntary assisted dying must never be allowed.',
'mc_004': 'Uniform condemnation of torture for fun; different reasons are compatible.',
'mc_002': 'Uniform condemnation of stealing from the poor; explanations differ without incompatible claims.',
'mc_007': 'General recommendation to keep promises; explicit harm-related exceptions are compatible with this default, not opposite recommendations for the same circumstances.',
'mc_009': 'Uniform recommendation to testify truthfully; privilege/non-answer exceptions and presenting truthful facts do not authorize lying.',
'oa_009': 'All qualify beauty as subjective; mentioning autumns appeal or other peoples preferences is compatible.',
'oa_002': 'No universal best color. Different color associations or examples are compatible, not personal preference reversals.',
'oa_010': 'Cats versus dogs depends on lifestyle; neither is universally superior in these responses.',
'oa_006': 'Beauty is subjective; different nonexclusive examples of admired languages do not contradict one another.'}
labels=[]
for c in cases:
    pid=c['family']; model=c['model']; texts=c['responses']
    errors=[i for i,t in enumerate(texts) if not t.strip() or t.lstrip().startswith('ERROR:')]
    unusable=list(errors)
    if c['id']=='qwen3_14b:fs_010': unusable.append(9)
    if c['id']=='qwen3_14b:fc_004': unusable.append(3)
    category='paraphrase'
    if pid.startswith(('oa_', 'ma_')) or pid in ['fc_007','fc_005','fc_004']:
        category='uncertainty'
    if model=='qwen3_14b' and pid=='ma_005': category='paraphrase'
    if len({t for i,t in enumerate(texts) if i not in unusable})==1: category='agreement'
    if len(texts)-len(unusable)<5: category='failed_generation'
    witness=None
    rationale=reasons[pid]
    if c['id']=='mistral_latest:fs_002':
        category='contradiction'; witness=[5,8]
        rationale='Sample 5 places the end of the European theater on August 15; sample 8 ties it to Germanys surrender on May 7. These are incompatible dates for that theater in the same war. All samples still agree on the requested year 1945. This is an ancillary-detail contradiction, not an answer-year reversal.'
    labels.append(dict(id=c['id'],category=category,contradiction=category=='contradiction',
                       direct_answer_contradiction=False,contradiction_witness=witness,
                       rationale=rationale,failed_indices=sorted(unusable),
                       ambiguous=c['id'] in ['mistral_latest:ma_005','mistral_latest:fc_007','mistral_latest:fs_010'],
                       reviewed_indices=list(range(len(texts)))))
(out/'labels.json').write_text(json.dumps(labels,indent=2)+'\n')
lock={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/'protocol.json',out/'cases.json',out/'labels.json']}
lock['stage']='frozen_after_text_review_before_geometric_scoring'
(out/'label_lock.json').write_text(json.dumps(lock,indent=2)+'\n')
from collections import Counter
print(Counter(x['category'] for x in labels))

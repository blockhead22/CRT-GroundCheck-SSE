import argparse, json, hashlib, random, runpy
from pathlib import Path
parser=argparse.ArgumentParser(description='Prepare text-only cases; run in a NEW output folder before labeling')
parser.add_argument('--repo',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.repo
out=args.output
if out.exists() and any(out.iterdir()):raise ValueError('Refusing to overwrite an existing benchmark bundle')
out.mkdir(parents=True,exist_ok=True)
bank=runpy.run_path(str(root/'belief_variance_experiment/prompts.py'))['PROMPT_BY_ID']
seed='aether-semantic-v1-20260912'
# Geometry-independent selection, before inspecting labels or scores.
ids=[]
for prefix in ['fs','fc','ma','mc','oa']:
    candidates=[f'{prefix}_{i:03}' for i in range(1,11)]
    candidates.sort(key=lambda x:hashlib.sha256((seed+x).encode()).hexdigest())
    ids += [(pid, 'development' if i<2 else 'heldout') for i,pid in enumerate(candidates[:4])]
cases=[]
for pid,split in ids:
    for model in ['mistral_latest','qwen3_14b']:
        rel=f'belief_variance_experiment/results/raw/{model}/{pid}_1.5.jsonl'
        path=root/rel
        rows=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        rng=random.Random(seed+model+pid)
        inds=sorted(rng.sample(range(len(rows)), min(10,len(rows))))
        case=dict(id=f'{model}:{pid}',family=pid,split=split,model=model,prompt=bank[pid]['text'],temperature=1.5,source=rel,raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),indices=inds,responses=[rows[i]['response'] for i in inds])
        cases.append(case)
protocol=dict(seed=seed,selection='4 of first 10 prompt families per domain by SHA256; first 2 development, last 2 heldout; Mistral and Qwen; 10 uniformly sampled rows at T=1.5',primary_target='At least one mutually incompatible pair of assertions/recommendations under the SAME assumptions within sampled valid responses. Pure hedging, different compatible examples, different explicit contexts, and generation failures are not contradictions.',labels=['agreement','paraphrase','contradiction','uncertainty','failed_generation'],uncertainty='No incompatible pair, but responses qualify, abstain, or offer compatible alternatives; ambiguity must be recorded.',label_source='One Codex reviewer, text-only before score calculation; independent of geometric labels, NOT independent human validation.',scope='Held-out prompt families for threshold transfer. Retrospective temperature experiment, NOT time forecasting. Small pilot; existing historical cache alignment remains unauthenticated.',cases_sha256=hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest(),score_plan=['original early covariance velocity rule, fixed 0.001 threshold','early cosine spread at T=.7','early noise-aware cluster entropy at T=.7','early noise-as-singletons entropy','same-sample covariance trace vs cosine spread vs cluster entropy (secondary diagnostic)'],thresholds='Baselines maximize development balanced accuracy, conservative larger threshold on ties; lock before heldout scoring. Original rule remains fixed.',labels_frozen_before_scoring=True)
(out/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
(out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
with (out/'labeling.txt').open('w') as f:
    for c in cases:
        f.write(f"\n{c['id']} | {c['prompt']}\n")
        unique={}
        for i,t in enumerate(c['responses']): unique.setdefault(t,[]).append(i)
        for t,idx in unique.items(): f.write(f'{idx}: {t!r}\n')
print('Cases',len(cases),'families',len(ids),'text characters', (out/'labeling.txt').stat().st_size)

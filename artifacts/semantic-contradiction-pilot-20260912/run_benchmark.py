"""Offline, text-labeled temperature pilot. Never loads or downloads a model.

Labels/protocol are frozen before scores. Historical embeddings are accepted
ONLY with --allow-legacy-unverified, and are recorded as unauthenticated. This
measures sampled response disagreement across temperature, never time or truth.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import dataclass
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_distances


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,data): Path(p).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def records(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def valid(r): return isinstance(r.get('response'),str) and bool(r['response'].strip()) and not r['response'].lstrip().startswith('ERROR:')


def extract(path,names,ns):
    tree=ast.parse(path.read_text())
    body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]
    body += [n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    assert len(body)==len(names)+1
    exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path),'exec'),ns)


def numerics(snapshot):
    spec=importlib.util.spec_from_file_location('frozen_loci',snapshot/'personal_agent/memory_subsystem/splats.py')
    module=importlib.util.module_from_spec(spec); sys.modules[spec.name]=module; spec.loader.exec_module(module)
    ns=dict(__name__=__name__,np=np,DBSCAN=DBSCAN,cosine_distances=cosine_distances,dataclass=dataclass,BeliefLocus=module.BeliefLocus)
    extract(snapshot/'belief_variance_experiment/variance_to_splats.py',{'BeliefSplat','BeliefTrajectory','distribution_to_splat','distribution_to_multi_splats','build_trajectory'},ns)
    extract(snapshot/'personal_agent/contradiction/predictive.py',{'TrajectoryState','extract_trajectory'},ns)
    return ns


def diagnostics(arr):
    d=cosine_distances(arr); tri=d[np.triu_indices(len(arr),1)]
    eps=max(float(np.median(tri)*.5),.05) if len(tri) else .05
    labels=DBSCAN(eps=eps,min_samples=5,metric='precomputed').fit_predict(d)
    real=[int(sum(labels==k)) for k in sorted(set(labels)) if k>=0]
    noise=int(sum(labels==-1))
    def entropy(counts):
        if not counts:return 0.
        p=np.array(counts,dtype=float)/sum(counts)
        return max(0.,float(-sum(p*np.log2(p))))
    conditional=entropy(real)
    # Keep assigned-cluster diversity and missing cluster evidence explicit.
    return dict(cosine_spread=float(tri.mean()) if len(tri) else 0.,
                covariance_trace=float(np.var(arr,axis=0).sum()),
                assigned_cluster_entropy=conditional,
                noise_fraction=noise/len(arr),
                singleton_noise_entropy=entropy(real+[1]*noise),
                cluster_count=len(real))


def evaluate(rows,key,threshold):
    ys=[int(r['contradiction']) for r in rows]
    predictions=[bool(r['scores'][key]>threshold) for r in rows]
    tp=sum(p and y for p,y in zip(predictions,ys)); fp=sum(p and not y for p,y in zip(predictions,ys))
    fn=sum(not p and y for p,y in zip(predictions,ys)); tn=sum(not p and not y for p,y in zip(predictions,ys))
    return dict(n=len(rows),positive=sum(ys),negative=len(ys)-sum(ys),tp=tp,fp=fp,fn=fn,tn=tn,
                precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,
                false_positive_rate=fp/(fp+tn) if fp+tn else None,
                balanced_accuracy=.5*(tp/(tp+fn)+tn/(tn+fp)) if tp+fn and tn+fp else None,
                auroc=float(roc_auc_score(ys,[r['scores'][key] for r in rows])) if len(set(ys))==2 else None,
                warning_ids=[r['id'] for r,p in zip(rows,predictions) if p])


def choose_threshold(dev,key):
    values=sorted(set(r['scores'][key] for r in dev))
    thresholds=[float(np.nextafter(values[0],-np.inf))]+values
    if len({r['contradiction'] for r in dev})<2:
        return None
    return max(thresholds,key=lambda t:(evaluate(dev,key,t)['balanced_accuracy'],t))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,default=Path(__file__).parent)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--allow-legacy-unverified',action='store_true')
    args=parser.parse_args()
    if not args.allow_legacy_unverified:
        parser.error('Historical cache lacks generation receipts. Explicit --allow-legacy-unverified required; no encoder will be loaded.')
    lock=json.loads((args.bundle/'label_lock.json').read_text())
    for name in ['protocol.json','cases.json','labels.json']:
        if sha(args.bundle/name)!=lock[name]:raise ValueError(f'Frozen label/protocol mismatch: {name}')
    cases=json.loads((args.bundle/'cases.json').read_text())
    labels={r['id']:r for r in json.loads((args.bundle/'labels.json').read_text())}
    assert set(labels)=={c['id'] for c in cases}
    source_lock=json.loads((args.bundle/'source_lock.json').read_text())
    for name,expected in source_lock.items():
        if sha(args.bundle/'source_before'/name)!=expected:raise ValueError(f'Frozen predictor source mismatch: {name}')
    ns=numerics(args.bundle/'source_before')
    args.output.mkdir(parents=True,exist_ok=True)
    provenance=[]; scored=[]; excluded=[]
    def load(c,temp):
        stem=f"{c['family']}_{temp}"
        raw=args.repo/f"belief_variance_experiment/results/raw/{c['model']}/{stem}.jsonl"
        emb=args.repo/f"belief_variance_experiment/results/embeddings/{c['model']}_{stem}.npy"
        rr=records(raw); arr=np.load(emb,allow_pickle=False)
        if arr.ndim!=2 or len(rr)!=len(arr) or not np.isfinite(arr).all():raise ValueError(f'Alignment/array failure: {emb}')
        if not all(r['prompt_id']==c['family'] and r['temperature']==temp for r in rr):raise ValueError('Cell identity mismatch')
        provenance.append(dict(case=c['id'],temperature=temp,source=str(raw.relative_to(args.repo)),cache=str(emb.relative_to(args.repo)),raw_sha256=sha(raw),cache_sha256=sha(emb),
                               status='legacy_observation_only_NOT_generation_verification',encoder_artifact='unknown_historical',
                               observed_response_hashes=[hashlib.sha256(r.get('response','').encode()).hexdigest() for r in rr]))
        return rr,arr
    for c in cases:
        lab=labels[c['id']]
        assert lab['reviewed_indices']==list(range(len(c['indices'])))
        future_rows,future_arr=load(c,1.5)
        assert sha(args.repo/c['source'])==c['raw_sha256']
        assert [future_rows[i]['response'] for i in c['indices']]==c['responses']
        keep=[j for j in range(len(c['indices'])) if j not in lab['failed_indices']]
        if len(keep)<5:
            excluded.append(dict(id=c['id'],reason='fewer_than_five_reviewable_responses',category=lab['category']));continue
        early={}
        for t in [0.,.3,.7]:
            rr,arr=load(c,t); mask=np.array([valid(r) for r in rr],dtype=bool)
            if mask.sum()>=5:early[t]=arr[mask]
        if len(early)!=3:
            excluded.append(dict(id=c['id'],reason='incomplete_early_valid_data',category=lab['category']));continue
        traj=ns['build_trajectory'](c['family'],early)
        state=ns['extract_trajectory'](traj.primary_splats[-1])
        velocity=float(state.covariance_velocity) if state and state.is_widening else 0.
        early_d=diagnostics(early[.7])
        arr=future_arr[[c['indices'][j] for j in keep]]
        late_d=diagnostics(arr)
        unit=arr/np.linalg.norm(arr,axis=1,keepdims=True)
        unit_d=diagnostics(unit)
        scores=dict(original_covariance_velocity=velocity,
                    early_cosine_spread=early_d['cosine_spread'],
                    early_assigned_cluster_entropy=early_d['assigned_cluster_entropy'],
                    early_singleton_noise_entropy=early_d['singleton_noise_entropy'],
                    current_covariance_trace=late_d['covariance_trace'],
                    current_cosine_spread=late_d['cosine_spread'],
                    current_singleton_noise_entropy=late_d['singleton_noise_entropy'])
        scored.append(dict(id=c['id'],family=c['family'],model=c['model'],split=c['split'],category=lab['category'],contradiction=lab['contradiction'],
                           direct_answer_contradiction=lab['direct_answer_contradiction'],n_reviewable=len(arr),scores=scores,
                           early_diagnostics=early_d,current_diagnostics=late_d,
                           original_timestamps=[s['timestamp'] for s in traj.primary_splats[-1].trajectory],
                           normalized_variance_identity_error=abs(unit_d['covariance_trace']-(len(unit)-1)/len(unit)*unit_d['cosine_spread'])))
    dev=[r for r in scored if r['split']=='development']; test=[r for r in scored if r['split']=='heldout']
    assert not {r['family'] for r in dev}&{r['family'] for r in test}
    keys=list(scored[0]['scores'])
    thresholds={k:(.001 if k=='original_covariance_velocity' else choose_threshold(dev,k)) for k in keys}
    # Calibration artifact is written before invoking heldout evaluation.
    dump(args.output/'thresholds.json',dict(selection_split='development_only',comparison='score > threshold',values=thresholds,
                                          development_families=sorted({r['family'] for r in dev}),label_lock_sha256=sha(args.bundle/'label_lock.json')))
    results={k:{'threshold':thresholds[k], 'development':evaluate(dev,k,thresholds[k]),'heldout':evaluate(test,k,thresholds[k])}
             for k in keys if thresholds[k] is not None}
    summary=dict(scope='retrospective_temperature_pilot_with_text_labels',model_downloads=0,model_calls=0,
                 n_cases=len(cases),families=len({c['family'] for c in cases}),sampled_responses=sum(len(c['indices']) for c in cases),
                 labels=dict(Counter(l['category'] for l in labels.values())),scored=len(scored),excluded=excluded,
                 development_families=sorted({r['family'] for r in dev}),heldout_families=sorted({r['family'] for r in test}),
                 heldout_positives=sum(r['contradiction'] for r in test),direct_answer_contradictions=sum(r['direct_answer_contradiction'] for r in scored),
                 max_normalized_variance_identity_error=max(r['normalized_variance_identity_error'] for r in scored),
                 results=results,can_establish_predictive_advantage=False,
                 limitations=['Single Codex text reviewer; independent of geometry, not independent human validation.',
                              '10 sampled responses per cell; no assertion of contradiction absence in unsampled rows.',
                              'Only one positive, in development, on an ancillary detail. Heldout has no positive examples; recall, AUROC and balanced accuracy are undefined there.',
                              'Very weak calibration: one development positive. Lower false alarms alone cannot establish useful detection.',
                              'Historical encoder/row alignment remains unauthenticated; recorded hashes freeze present observations only.',
                              'Sampling temperature is not time. Same-sample scores are diagnostics, not forecasts.',
                              'Families restricted to original first ten prompts per domain; two historical models; not representative of all tasks or modern models.'],
                 label_lock_sha256=sha(args.bundle/'label_lock.json'), source_lock_sha256=sha(args.bundle/'source_lock.json'))
    dump(args.output/'summary.json',summary);dump(args.output/'scored_cases.json',scored);dump(args.output/'legacy_cache_observations.json',provenance)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['results']},indent=2))
    for key, val in results.items():print(key, 'heldout:',{k:v for k,v in val['heldout'].items() if k!='warning_ids'})


if __name__=='__main__':main()

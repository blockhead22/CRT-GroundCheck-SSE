"""Balanced static geometry lab. Local encoder only; network blocked at runtime."""
from __future__ import annotations
import os
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
import argparse, ast, hashlib, importlib.util, json, socket, sys
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_distances


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def geometry(path):
 names={'fisher_rao_distance','fisher_mean_component','fisher_cov_component'}
 tree=ast.parse(path.read_text());body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]
 body += [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
 if len(body)!=4:raise ValueError('Missing original geometry functions')
 ns=dict(np=np);exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(path),'exec'),ns);return ns


def metrics(y,pred,scores):
 y=np.array(y,dtype=bool);pred=np.array(pred,dtype=bool)
 tp=int(sum(y&pred));fp=int(sum(~y&pred));fn=int(sum(y&~pred));tn=int(sum(~y&~pred))
 return dict(n=len(y),tp=tp,fp=fp,fn=fn,tn=tn,precision=tp/(tp+fp) if tp+fp else None,
             recall=tp/(tp+fn),false_positive_rate=fp/(fp+tn),balanced_accuracy=.5*(tp/(tp+fn)+tn/(fp+tn)),
             auroc=float(roc_auc_score(y,scores)))


def calibrate(rows,key):
 values=sorted(set(r['scores'][key] for r in rows));ts=[float(np.nextafter(values[0],-np.inf))]+values
 return max(ts,key=lambda t:(metrics([r['label'] for r in rows],[r['scores'][key]>t for r in rows],[r['scores'][key] for r in rows])['balanced_accuracy'],t))


def validate_cases(cases,labels,records):
 if len(cases)!=72 or len(labels)!=72 or len(records)!=432:raise ValueError('Unexpected frozen benchmark dimensions')
 if set(labels)!={c['id'] for c in cases}:raise ValueError('Missing or extra labels')
 seen=set();family_splits={}
 for c in cases:
  family_splits.setdefault(c['family'],set()).add(c['split'])
  for side in ['source','target']:
   ids=c[side+'_rows']
   if len(ids)!=3 or len(set(ids))!=3:raise ValueError('Each side must have three distinct row ids')
   for i in ids:
    r=records[i]
    if i in seen or r['case_id']!=c['id'] or r['side']!=side or not r['response'].strip():raise ValueError('Row mapping mismatch')
    seen.add(i)
 if len(seen)!=len(records) or any(len(s)!=1 for s in family_splits.values()):raise ValueError('Row coverage or family leakage')
 for split in ['development','heldout']:
  part=[c for c in cases if c['split']==split]
  if len(part)!=36 or sum(labels[c['id']]['contradiction'] for c in part)!=18:raise ValueError('Unbalanced split')
 return family_splits


def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
 p.add_argument('--bundle',type=Path,default=Path(__file__).parent);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 lock=json.loads((a.bundle/'input_lock.json').read_text())
 for n,digest in lock.items():
  if sha(a.bundle/n)!=digest:raise ValueError('Frozen input changed: '+n)
 cases=json.loads((a.bundle/'cases.json').read_text());labels={r['id']:r for r in json.loads((a.bundle/'labels.json').read_text())}
 records=[json.loads(l) for l in (a.bundle/'responses.jsonl').read_text().splitlines()]
 validate_cases(cases,labels,records)
 cache=load_module(a.bundle/'embedding_cache.py','frozen_cache')
 geom=geometry(a.bundle/'info_geometry.py')
 if not a.model.is_dir():raise RuntimeError('Local model directory missing; nothing downloaded')
 # No network is needed even for model metadata. Fail rather than fetch.
 def block(*args,**kwargs):raise RuntimeError('Network disabled for this benchmark')
 socket.socket.connect=block;socket.create_connection=block
 a.output.mkdir(parents=True,exist_ok=True)
 array_path=a.output/'embeddings.npy'
 if array_path.exists():
  arr=cache.load_cache(array_path,records)
  encoder=json.loads(cache.manifest_path(array_path).read_text())['encoder']
 else:
  import torch
  torch.manual_seed(20260912);torch.set_num_threads(4)
  from sentence_transformers import SentenceTransformer
  model=SentenceTransformer(str(a.model.resolve()),local_files_only=True,device='cpu',trust_remote_code=False)
  encoder=cache.fingerprint_encoder(model,'sentence-transformers/all-MiniLM-L6-v2')
  texts=[r['response'] for r in records]
  lengths=[len(model.tokenizer(t,add_special_tokens=True,truncation=False)['input_ids']) for t in texts]
  if max(lengths)>model.max_seq_length:raise ValueError('Input truncation would invalidate proposition comparison')
  arr=np.asarray(model.encode(texts,batch_size=32,show_progress_bar=False,normalize_embeddings=True,convert_to_numpy=True),dtype=np.float32)
  encoder['encode_settings']=dict(normalize_embeddings=True,device='cpu',batch_size=32,dtype='float32',max_token_count=max(lengths))
  cache.save_cache(array_path,arr,records,encoder,a.bundle/'responses.jsonl')
  np.testing.assert_array_equal(cache.load_cache(array_path,records),arr)
 if arr.shape!=(432,384) or not np.isfinite(arr).all():raise ValueError('Unexpected embeddings')
 np.testing.assert_allclose(np.linalg.norm(arr,axis=1),1,atol=1e-5)
 dev_indices=[i for c in cases if c['split']=='development' for side in ['source','target'] for i in c[side+'_rows']]
 vectorizer=TfidfVectorizer(ngram_range=(1,2),lowercase=True)
 vectorizer.fit([records[i]['response'] for i in dev_indices])
 lexical=vectorizer.transform([r['response'] for r in records])
 scored=[]
 def locus(x):return SimpleNamespace(mu=np.mean(x,axis=0),sigma=np.maximum(np.var(x,axis=0),1e-8))
 for c in cases:
  ii,jj=c['source_rows'],c['target_rows'];x,y=arr[ii],arr[jj];one,two=locus(x),locus(y)
  scores=dict(project_fisher_distance=geom['fisher_rao_distance'](one,two),
              project_fisher_mean_only=geom['fisher_mean_component'](one,two),
              project_fisher_covariance_only=geom['fisher_cov_component'](one,two),
              centroid_cosine_distance=float(cosine_distances(one.mu[None,:],two.mu[None,:])[0,0]),
              mean_cross_cosine_distance=float(cosine_distances(x,y).mean()),
              word_tfidf_cosine_distance=float(cosine_distances(np.asarray(lexical[ii].mean(axis=0)),np.asarray(lexical[jj].mean(axis=0)))[0,0]))
  if not all(np.isfinite(v) for v in scores.values()):raise ValueError('Non-finite score')
  scored.append(dict(**c,label=labels[c['id']]['contradiction'],scores=scores))
 dev=[r for r in scored if r['split']=='development'];test=[r for r in scored if r['split']=='heldout'];keys=list(scored[0]['scores'])
 thresholds={k:calibrate(dev,k) for k in keys}
 write(a.output/'thresholds.json',dict(thresholds=thresholds,fit_split='development_only',rule='score > threshold',input_lock_sha256=sha(a.bundle/'input_lock.json')))
 result={}
 for k,t in thresholds.items():
  result[k]={split:metrics([r['label'] for r in rows],[r['scores'][k]>t for r in rows],[r['scores'][k] for r in rows]) for split,rows in [('development',dev),('heldout',test)]}
  result[k]['threshold']=t
  result[k]['heldout_errors']=[dict(id=r['id'],label=r['label'],score=r['scores'][k]) for r in test if (r['scores'][k]>t)!=r['label']]
 rng=np.random.default_rng(20260912);families=sorted({r['family'] for r in test});diffs=[]
 for _ in range(2000):
  selected=rng.choice(families,len(families),replace=True)
  rows=[r for f in selected for r in test if r['family']==f]
  yy=[r['label'] for r in rows]
  diffs.append(float(roc_auc_score(yy,[r['scores']['project_fisher_distance'] for r in rows])-roc_auc_score(yy,[r['scores']['centroid_cosine_distance'] for r in rows])))
 by_kind={}
 for kind in sorted({r['kind'] for r in test}):
  part=[r for r in test if r['kind']==kind]
  by_kind[kind]=dict(n=len(part),label=part[0]['label'],correct={k:sum((r['scores'][k]>thresholds[k])==r['label'] for r in part) for k in keys})
 summary=dict(scope='synthetic_static_semantic_discrimination_only',cases=72,heldout_cases=36,heldout_positives=18,heldout_negatives=18,
              development_families=sorted({r['family'] for r in dev}),heldout_families=families,
              model_downloads=0,provider_calls=0,encoder=encoder,
              results=result,heldout_by_kind=by_kind,
              fisher_minus_centroid_auroc_family_bootstrap_95pct=[float(x) for x in np.quantile(diffs,[.025,.975])],
              caveats=['Single-author synthetic controls; shared templates cross scenario-family split.',
                       'Only six heldout families; bootstrap is descriptive, not strong population inference.',
                       'Three authored paraphrases per side; not independent generations or internal belief measurements.',
                       'Tests static contradiction discrimination, not prediction before future evidence.',
                       'Project Fisher distance is an approximation over diagonal moments; not exact multivariate Gaussian geodesic.'],
              source_sha256={n:sha(a.bundle/n) for n in ['info_geometry.py','embedding_cache.py','run.py']},input_lock_sha256=sha(a.bundle/'input_lock.json'))
 write(a.output/'summary.json',summary);write(a.output/'scored_cases.json',scored)
 write(a.output/'environment.json',{p:version(p) for p in ['numpy','scipy','scikit-learn','torch','transformers','sentence-transformers','huggingface-hub','tokenizers','safetensors']})
 print(json.dumps({k:v['heldout'] for k,v in result.items()},indent=2))
 print('Fisher minus centroid AUROC family-bootstrap interval:',summary['fisher_minus_centroid_auroc_family_bootstrap_95pct'])
if __name__=='__main__':main()

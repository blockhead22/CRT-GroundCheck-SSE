"""Post-primary diagnostic of the actual fixed candidate gate; no tuning."""
import argparse,ast,json,sys,types
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from run import load_module,geometry,metrics,write,sha

def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);a=p.parse_args();base=Path(__file__).parent
 cache=load_module(base/'embedding_cache.py','supplement_cache')
 arr=cache.load_cache(a.results/'embeddings.npy')
 cases=json.loads((base/'cases.json').read_text());gold={r['id']:r['contradiction'] for r in json.loads((base/'labels.json').read_text())}
 loci=load_module(base/'locus_types.py','frozen_locus_types')
 # The original function imports its pure numerical overlap helper internally.
 # Bind that dependency without importing the application initializer.
 parent=types.ModuleType('personal_agent');parent.__path__=[];parent.memory_splats=loci
 sys.modules['personal_agent']=parent;sys.modules['personal_agent.memory_splats']=loci
 geom=geometry(base/'info_geometry.py')
 names={'LLMContradiction','find_cross_prompt_contradictions'}
 tree=ast.parse((base/'variance_to_splats.py').read_text())
 body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)]
 body += [n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
 ns=dict(__name__=__name__,np=np,dataclass=dataclass,fisher_rao_distance=geom['fisher_rao_distance'])
 exec(compile(ast.fix_missing_locations(ast.Module(body=body,type_ignores=[])),str(base/'variance_to_splats.py'),'exec'),ns)
 rows=[]
 for c in cases:
  trajectory={}
  for side in ['source','target']:
   x=arr[c[side+'_rows']]
   locus=loci.BeliefLocus(memory_id=side,mu=x.mean(axis=0),sigma=np.maximum(x.var(axis=0),1e-8))
   trajectory[side]=types.SimpleNamespace(splats_by_temp={1.0:[]},primary_splats=[locus],domain=c['family'])
  detected=bool(ns['find_cross_prompt_contradictions'](trajectory))
  one,two=[trajectory[side].primary_splats[0] for side in ['source','target']]
  cosine=float(np.dot(one.mu,two.mu)/(np.linalg.norm(one.mu)*np.linalg.norm(two.mu)+1e-10))
  fisher=geom['fisher_rao_distance'](one,two)
  assert detected==(cosine>=.7 and fisher>=5.)
  rows.append(dict(id=c['id'],split=c['split'],label=gold[c['id']],candidate=detected,cosine_only=cosine>=.7,cosine=cosine,fisher=fisher))
 results={}
 for split in ['development','heldout']:
  part=[r for r in rows if r['split']==split]
  results[split]={k:metrics([r['label'] for r in part],[r[k] for r in part],[int(r[k]) for r in part]) for k in ['candidate','cosine_only']}
 # This gate is a candidate generator, not a semantic adjudicator. Its AUROC
 # here is for a binary decision, not a continuous ranking.
 write(a.results/'fixed_gate_diagnostic.json',dict(stage='Post-primary source-grounded diagnostic; fixed code defaults, no tuning',
       rule='original find_cross_prompt_contradictions: cosine >= .7 and Fisher >= 5',
       caveat='Measures candidate gate on constructed static loci, not end-to-end production reasoning or future prediction.',
       source_sha256={n:sha(base/n) for n in ['variance_to_splats.py','locus_types.py','supplement.py']},results=results,rows=rows))
 print(json.dumps(results,indent=2))
if __name__=='__main__':main()

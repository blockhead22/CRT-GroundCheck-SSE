"""Offline audit of frozen belief-variance data. Never loads or downloads models.

Runs selected original numerical functions via AST extraction, avoiding the
personal_agent package initializer and its model/runtime side effects.
Cached row alignment is checked by filename/count/metadata, not authenticated:
the historical cache has no per-response hash manifest. Results are conditional
on that alignment, and clustering is explicitly NOT a semantic truth label.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import warnings

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics import roc_auc_score
from sklearn.metrics.pairwise import cosine_distances

warnings.filterwarnings('ignore', category=RuntimeWarning)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_code(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    body = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    body += [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(body) == len(names) + 1, (path, names)
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec'), namespace)


def load_numerics(root):
    path = root/'personal_agent/memory_subsystem/splats.py'
    spec = importlib.util.spec_from_file_location('audited_splats', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    namespace = dict(np=np, DBSCAN=DBSCAN, cosine_distances=cosine_distances,
                     dataclass=dataclass, BeliefLocus=module.BeliefLocus)
    selected_code(root/'belief_variance_experiment/variance_to_splats.py', {
        'BeliefSplat', 'BeliefTrajectory', 'distribution_to_splat',
        'distribution_to_multi_splats', 'build_trajectory'}, namespace)
    selected_code(root/'personal_agent/contradiction/predictive.py',
                  {'TrajectoryState', 'extract_trajectory'}, namespace)
    return namespace


def cell_metrics(arr, original):
    distances = cosine_distances(arr)
    tri = distances[np.triu_indices(len(arr), 1)]
    eps = max(float(np.median(tri) * .5), .05) if len(tri) else .05
    labels = DBSCAN(eps=eps, min_samples=5, metric='precomputed').fit_predict(distances)
    splat = original('audit', arr, 1.0)
    counts = [int(sum(labels == k)) for k in set(labels) if k >= 0]
    # Noise-as-singletons is a sensitivity control, not validated semantic entropy.
    counts += [1] * int(sum(labels == -1))
    probs = np.array(counts, dtype=float) / len(arr)
    adjusted = float(-np.sum(probs * np.log2(probs)))
    return dict(n=len(arr), clusters=splat.n_clusters, noise=int(sum(labels == -1)),
                entropy=float(splat.entropy), confidence=float(splat.splat.alpha),
                singleton_noise_entropy=adjusted,
                spread=float(tri.mean()) if len(tri) else 0.,
                variance_trace=float(np.var(arr, axis=0).sum())), labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = args.repo
    result_root = root/'belief_variance_experiment/results'
    numerics = load_numerics(root)
    original = numerics['distribution_to_splat']
    model_names = ['deepseek-r1_8b', 'mistral_latest', 'qwen3_14b']
    provenance, cells, witnesses = [], [], []
    groups = defaultdict(dict)
    error_types = Counter()
    repeat_alignment = Counter(pairs_checked=0, mismatched_pairs=0)
    raw_inventory = Counter()

    for path in sorted((result_root/'raw').rglob('*.jsonl')):
        if path.name.startswith('._'): continue
        bucket = path.parent.name if path.parent != result_root/'raw' else 'flat'
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        raw_inventory[bucket+'_files'] += 1
        raw_inventory[bucket+'_rows'] += len(rows)
        raw_inventory[bucket+'_errors_or_empty'] += sum(
            not str(r.get('response', '')).strip() or str(r.get('response', '')).startswith('ERROR:') for r in rows)

    paths = [p for p in sorted((result_root/'embeddings').glob('*.npy')) if not p.name.startswith('._')]
    for path in paths:
        model = next((m for m in model_names if path.stem.startswith(m+'_')), None)
        stem = path.stem[len(model)+1:] if model else path.stem
        pid, raw_temp = stem.rsplit('_', 1)
        temp = float(raw_temp)
        raw_path = result_root/'raw'/model/(stem+'.jsonl') if model else result_root/'raw'/(stem+'.jsonl')
        arr = np.load(path, allow_pickle=False)
        rows = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()] if raw_path.exists() else []
        aligned = bool(rows) and len(rows) == len(arr) and all(
            r.get('prompt_id') == pid and float(r.get('temperature', -99)) == temp for r in rows)
        finite = bool(np.isfinite(arr).all())
        info = dict(cache=path.name, model=model or 'flat_unattributed', prompt_id=pid,
                    temperature=temp, embedding_rows=len(arr), raw_rows=len(rows),
                    alignment_checks_pass=aligned, finite=finite, cache_sha256=sha(path),
                    raw_sha256=sha(raw_path) if raw_path.exists() else None)
        provenance.append(info)
        # Only model-attributed cells may enter comparisons; don't combine models.
        if not model or not aligned or not finite: continue
        texts = [str(r.get('response', '')) for r in rows]
        valid = np.array([bool(t.strip()) and not t.startswith('ERROR:') for t in texts])
        for t, good in zip(texts, valid):
            if not good: error_types['empty' if not t.strip() else 'ERROR_prefix'] += 1
        # Duplicate identical texts ought to have identical embeddings. This is
        # a consistency check, not proof that every unique text is aligned.
        seen = {}
        for i, text in enumerate(texts):
            key = '' if text.startswith('ERROR:') else text
            if key in seen:
                repeat_alignment['pairs_checked'] += 1
                if not np.allclose(arr[i], arr[seen[key]], atol=1e-5, rtol=1e-5):
                    repeat_alignment['mismatched_pairs'] += 1
            else: seen[key] = i
        if valid.sum() < 5: continue
        before, _ = cell_metrics(arr, original)
        after, labels = cell_metrics(arr[valid], original)
        cell = dict(model=model, prompt_id=pid, temperature=temp, domain=rows[0]['domain'],
                    invalid_responses=int((~valid).sum()), before=before, after=after)
        cells.append(cell)
        groups[(model, pid)][temp] = (arr[valid], after, rows[0]['domain'])
        if temp == 1.0 and after['clusters'] >= 2:
            good_texts = np.array(texts)[valid]
            reps = []
            for k in sorted(set(labels) - {-1}):
                indices = np.flatnonzero(labels == k)
                reps.append(dict(cluster=int(k), size=len(indices),
                                 examples=list(dict.fromkeys(good_texts[indices]))[:3]))
            witnesses.append(dict(model=model, prompt_id=pid, clusters=reps))

    # Numerical counterexample executes the original conversion function.
    controls = {}
    for name, arr in [('identical', np.tile(np.eye(1, 384)[0], (30, 1))),
                      ('orthogonal_all_noise', np.eye(30, 384))]:
        controls[name] = cell_metrics(arr, original)[0]
    assert controls['orthogonal_all_noise']['clusters'] == 0
    assert controls['orthogonal_all_noise']['confidence'] > .999

    # Reproduce the original early-widening predictor against its OWN geometric
    # target. This is a diagnostic proxy, explicitly not contradiction accuracy.
    proxy = []
    for (model, pid), by_temp in sorted(groups.items()):
        if not all(t in by_temp for t in [0., .3, .7, 1., 1.5]): continue
        traj = numerics['build_trajectory'](pid, {t: v[0] for t, v in by_temp.items()}, by_temp[0.][2])
        early = [s for s in traj.primary_splats if s.created_at <= .7]
        state = numerics['extract_trajectory'](early[-1])
        future = any(by_temp[t][1]['clusters'] >= 2 for t in [1., 1.5])
        already = any(by_temp[t][1]['clusters'] >= 2 for t in [0., .3, .7])
        velocity = float(state.covariance_velocity) if state else 0.
        # Full-distribution entropy, not the per-cluster entropy=0 field.
        x = np.array([0., .3, .7])
        spread = np.array([by_temp[t][1]['spread'] for t in x])
        row = dict(model=model, prompt_id=pid, future_geometric_split=future,
                   already_split=already, original_prediction=bool(state and state.is_widening and velocity > .001),
                   scores=dict(original_covariance_velocity=velocity,
                               early_cosine_spread=by_temp[.7][1]['spread'],
                               early_cluster_entropy=by_temp[.7][1]['entropy'],
                               early_noise_singletons_entropy=by_temp[.7][1]['singleton_noise_entropy'],
                               cosine_spread_slope=float(np.polyfit(x, spread, 1)[0])),
                   timestamps_used_by_original_predictor=[s['timestamp'] for s in early[-1].trajectory])
        proxy.append(row)

    def proxy_summary(rows):
        y = np.array([r['future_geometric_split'] for r in rows], dtype=int)
        pred = np.array([r['original_prediction'] for r in rows], dtype=bool)
        out = dict(n=len(rows), positive=int(y.sum()), negative=int(len(y)-y.sum()),
                   tp=int(sum(pred & (y==1))), fp=int(sum(pred & (y==0))),
                   fn=int(sum(~pred & (y==1))), tn=int(sum(~pred & (y==0))))
        if len(set(y)) == 2:
            out['diagnostic_auroc'] = {k: round(float(roc_auc_score(y, [r['scores'][k] for r in rows])), 4) for k in rows[0]['scores']}
        else: out['diagnostic_auroc'] = None
        return out

    old = json.loads((result_root/'analysis/contradiction_classification.json').read_text())
    old_genuine = {pid: v for pid,v in old['per_prompt'].items() if v['classification'] == 'GENUINE_SPLIT'}
    comparisons = {
        'all_complete_groups': proxy_summary(proxy),
        'new_split_only_groups': proxy_summary([r for r in proxy if not r['already_split']]),
        'by_model': {m: proxy_summary([r for r in proxy if r['model'] == m]) for m in model_names},
    }
    matched_models = [r for r in provenance if r['model'] != 'flat_unattributed']
    flat = [r for r in provenance if r['model'] == 'flat_unattributed']
    summary = dict(
        scope='offline_cache_and_measurement_audit; no semantic prediction claim established',
        models_downloaded=0, model_calls=0,
        cache_files=len(paths), model_prefixed_cache_files=len(matched_models),
        model_prefixed_alignment_passes=sum(r['alignment_checks_pass'] for r in matched_models),
        flat_cache_files=len(flat), flat_alignment_passes=sum(r['alignment_checks_pass'] for r in flat),
        raw_inventory=dict(raw_inventory), duplicate_text_embedding_consistency=dict(repeat_alignment),
        analyzed_cells=len(cells), invalid_responses_in_attributed_cells=sum(r['invalid_responses'] for r in cells),
        excluded_attributed_cells_below_five_valid_responses=len(matched_models)-len(cells),
        multimodal_cells_before=sum(r['before']['clusters']>=2 for r in cells),
        multimodal_cells_after=sum(r['after']['clusters']>=2 for r in cells),
        lost_multimodality_after_error_removal=sum(r['before']['clusters']>=2 and r['after']['clusters']<2 for r in cells),
        clean_all_noise_cells=sum(r['after']['noise']==r['after']['n'] for r in cells),
        numerical_controls=controls, geometric_proxy_results=comparisons,
        old_genuine_split_count=len(old_genuine),
        old_genuine_split_with_empty_representative=sum(any(not s.strip() for c in v['clusters'] for s in c['representative_responses']) for v in old_genuine.values()),
        limitations=[
            'Historical embeddings lack row text hashes and encoder-version manifests; filename/count alignment is not proof.',
            'Old GENUINE_SPLIT labels are generated from geometric features and cannot independently validate those features.',
            'Proxy AUROCs predict future DBSCAN clustering across temperature, not semantic contradiction or temporal belief change.',
            'No learned thresholds or tuned classifiers; proxy figures are descriptive, not a held-out semantic benchmark.',
            'Noise-as-singletons entropy is a sensitivity analysis, not the published semantic-entropy method.',
        ],
        source_sha256={str(p.relative_to(root)):sha(p) for p in [root/'belief_variance_experiment/variance_to_splats.py',root/'personal_agent/contradiction/predictive.py',root/'belief_variance_experiment/llm_belief_analysis.py',root/'belief_variance_experiment/classify_contradictions.py']})
    for name, data in [('summary',summary), ('cache_provenance',provenance), ('cell_metrics',cells),
                       ('geometric_proxy_rows',proxy), ('multicluster_text_witnesses',witnesses),
                       ('previous_positive_examples',old_genuine)]:
        (args.output/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary,indent=2,allow_nan=False))


if __name__ == '__main__': main()

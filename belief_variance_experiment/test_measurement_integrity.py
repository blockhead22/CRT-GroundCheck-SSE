"""Offline regression tests. No model imports, downloads, or provider calls."""
import ast
from collections import defaultdict
from dataclasses import dataclass
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

if __package__:
    from . import embedding_cache as cache
    from .geometry_metrics import cluster_evidence, valid_embeddings
else:
    import embedding_cache as cache
    from geometry_metrics import cluster_evidence, valid_embeddings

SOURCE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('AETHER_LAB_REPO', SOURCE.parent))


def source_functions(path, names, namespace):
    tree = ast.parse(path.read_text())
    body = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)]
    body += [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    if len(body) != len(names) + 1:
        raise AssertionError('Missing production definition')
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec'), namespace)


def converter():
    # Import only the pure numerical locus file, bypassing app initializers.
    spec = importlib.util.spec_from_file_location('regression_locus', ROOT/'personal_agent/memory_subsystem/splats.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    namespace = dict(__name__=__name__, np=np, dataclass=dataclass, BeliefLocus=module.BeliefLocus,
                     DBSCAN=DBSCAN, cosine_distances=cosine_distances,
                     cluster_evidence=cluster_evidence, valid_embeddings=valid_embeddings)
    source_functions(SOURCE/'variance_to_splats.py', {'BeliefSplat','distribution_to_splat'}, namespace)
    return namespace['distribution_to_splat']


class GeometryTests(unittest.TestCase):
    def test_identical_and_all_noise_have_different_support(self):
        convert = converter()
        same = convert('same', np.tile(np.eye(1,384)[0], (30,1)), 1.)
        noise = convert('noise', np.eye(30,384), 1.)
        self.assertEqual(same.splat.alpha, 1.)
        self.assertEqual(noise.splat.alpha, 0.)
        self.assertEqual(noise.noise_fraction, 1.)
        self.assertAlmostEqual(noise.entropy, np.log2(30))

    def test_mixed_noise_reduces_support(self):
        clean = cluster_evidence([0]*10)
        mixed = cluster_evidence([0]*10 + [-1]*10)
        self.assertEqual(clean.support, 1.)
        self.assertEqual(mixed.support, .5)
        self.assertGreater(mixed.singleton_noise_entropy_bits, 0.)

    def test_empty_and_undersampled_do_not_get_certainty(self):
        self.assertEqual(cluster_evidence([]).support, 0.)
        self.assertEqual(converter()('small',np.eye(3,10),1.).splat.alpha,0.)
        for arr in [np.empty((0,10)), np.zeros((5,10)), np.full((5,10),np.nan)]:
            with self.assertRaises(ValueError): converter()('bad',arr,1.)

    def test_entropy_entry_point_no_longer_collapses_noise(self):
        ns=dict(__name__=__name__, np=np, DBSCAN=DBSCAN, cosine_distances=cosine_distances,
                cluster_evidence=cluster_evidence, valid_embeddings=valid_embeddings)
        source_functions(SOURCE/'analyze.py',{'semantic_entropy'},ns)
        entropy, clusters=ns['semantic_entropy'](np.eye(30,384))
        self.assertEqual(clusters,0)
        self.assertAlmostEqual(entropy,np.log2(30))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/'embeddings'/'m_pid_1.0.npy'
        self.raw=self.root/'raw'/'pid_1.0.jsonl'
        self.raw.parent.mkdir()
        self.records=[dict(prompt_id='pid',temperature=1.0,response=t,repetition=i)
                      for i,t in enumerate(['A','B','ERROR: timeout',''])]
        self.arr=np.eye(4,8,dtype=np.float32)
        self.encoder=dict(model_name='fake-test-encoder',artifact_sha256='a'*64)
        self.raw.write_text(''.join(json.dumps(r)+'\n' for r in self.records))

    def save(self): cache.save_cache(self.path,self.arr,self.records,self.encoder,self.raw)

    def test_roundtrip_preserves_source_rows(self):
        self.save()
        np.testing.assert_array_equal(cache.load_cache(self.path,self.records,'fake-test-encoder'),self.arr)
        receipts=json.loads(cache.manifest_path(self.path).read_text())['rows']
        self.assertEqual([r['valid'] for r in receipts],[True,True,False,False])

    def test_same_count_reordering_or_text_change_rejected(self):
        self.save()
        for records in [list(reversed(self.records)),[dict(r,response='C') for r in self.records]]:
            with self.assertRaises(cache.CacheIntegrityError): cache.load_cache(self.path,records)

    def test_source_change_and_embedding_corruption_rejected(self):
        self.save()
        self.raw.write_text(self.raw.read_text().replace('"A"','"C"'))
        with self.assertRaises(cache.CacheIntegrityError): cache.load_cache(self.path)
        self.raw.write_text(''.join(json.dumps(r)+'\n' for r in self.records))
        self.save()
        np.save(self.path,self.arr+1.)
        with self.assertRaises(cache.CacheIntegrityError): cache.load_cache(self.path)

    def test_wrong_encoder_and_missing_identity_rejected(self):
        self.save()
        with self.assertRaises(cache.CacheIntegrityError): cache.load_cache(self.path,model_name='different')
        p=cache.manifest_path(self.path)
        m=json.loads(p.read_text()); del m['encoder']['artifact_sha256']; p.write_text(json.dumps(m))
        with self.assertRaises(cache.CacheIntegrityError): cache.load_cache(self.path)

    def test_legacy_cache_refused_without_importing_models(self):
        self.path.parent.mkdir(); np.save(self.path,self.arr)
        with patch.dict(sys.modules,{'sentence_transformers':None}):
            with self.assertRaises(cache.CacheIntegrityError):
                cache.compute_verified_embeddings({'pid':{1.0:self.records}},self.path.parent,self.raw.parent,'fake-test-encoder',prefix='m_')

    def test_cache_only_path_filters_failures_without_model_runtime(self):
        self.save()
        with patch.dict(sys.modules,{'sentence_transformers':None}):
            result=cache.compute_verified_embeddings({'pid':{1.0:self.records}},self.path.parent,self.raw.parent,'fake-test-encoder',prefix='m_')
        np.testing.assert_array_equal(result['pid'][1.0], self.arr[:2])

    def test_different_encoder_revisions_cannot_be_combined(self):
        self.save()
        other_raw=self.raw.parent/'pid2_1.0.jsonl'
        other_records=[dict(r,prompt_id='pid2') for r in self.records]
        other_raw.write_text(''.join(json.dumps(r)+'\n' for r in other_records))
        other_path=self.path.parent/'m_pid2_1.0.npy'
        cache.save_cache(other_path,self.arr,other_records,
                         dict(model_name='fake-test-encoder',artifact_sha256='b'*64),other_raw)
        with patch.dict(sys.modules,{'sentence_transformers':None}):
            with self.assertRaisesRegex(cache.CacheIntegrityError,'Mixed encoder'):
                cache.compute_verified_embeddings({'pid':{1.0:self.records},'pid2':{1.0:other_records}},
                    self.path.parent,self.raw.parent,'fake-test-encoder',prefix='m_')

    def test_generation_is_local_only_and_writes_verifiable_receipts(self):
        from types import SimpleNamespace
        received={}
        arr=self.arr
        class InstalledEncoder:
            def __init__(self,name,**kwargs): received.update(name=name,**kwargs)
            def encode(self,texts,**kwargs):
                received['texts']=texts
                return arr
        fake=SimpleNamespace(SentenceTransformer=InstalledEncoder)
        with patch.dict(sys.modules,{'sentence_transformers':fake}), patch.object(cache,'fingerprint_encoder',return_value=self.encoder):
            result=cache.compute_verified_embeddings({'pid':{1.0:self.records}},self.path.parent,self.raw.parent,'fake-test-encoder',prefix='m_')
        self.assertIs(received['local_files_only'],True)
        self.assertEqual(received['texts'],['A','B','',''])
        np.testing.assert_array_equal(cache.load_cache(self.path),self.arr)
        np.testing.assert_array_equal(result['pid'][1.0],self.arr[:2])

    def test_missing_encoder_stops_without_download(self):
        with patch.dict(sys.modules,{'sentence_transformers':None}):
            with self.assertRaisesRegex(RuntimeError,'Stopped without downloading'):
                cache.compute_verified_embeddings({'pid':{1.0:self.records}},self.path.parent,self.raw.parent,'missing')

    def test_invalid_array_or_source_mapping_cannot_be_saved(self):
        for arr in [self.arr[:2], np.full((4,8),np.nan)]:
            with self.assertRaises(cache.CacheIntegrityError): cache.save_cache(self.path,arr,self.records,self.encoder,self.raw)
        with self.assertRaises(cache.CacheIntegrityError):
            cache.save_cache(self.path,self.arr,list(reversed(self.records)),self.encoder,self.raw)


if __name__=='__main__': unittest.main(verbosity=2)

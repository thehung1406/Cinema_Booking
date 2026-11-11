"""Fetch all four source corpora afresh; verify semantic inputs without host data.

Uses a temporary directory, no GPU, host cache, private annotations, or database.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'pipelines'))
from ml.data import read_jsonl
from reproduce_cinema_labels import semantic_sha


def main():
    expected=json.loads((ROOT/'pipelines/configs/four_vi_semantic_inputs.v1.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory(prefix='cinema-four-corpora-reproduction-') as temporary:
        output=Path(temporary)
        def run(script,*arguments):
            process=subprocess.run([sys.executable,str(ROOT/'scripts/ai'/script),*map(str,arguments)],cwd=ROOT,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            if process.returncode:raise RuntimeError(script+': '+process.stderr[-3000:])
        run('fetch_uts2017.py','--output',output/'uts2017-bank')
        run('fetch_public_reviews.py','shopee','--version','1','--output',output/'raw-shopee')
        run('prepare_four_datasets.py','shopee','--raw',output/'raw-shopee','--output',output/'shopee')
        run('prepare_four_datasets.py','visfd','--raw',output/'raw-visfd','--output',output/'uit-visfd-general')
        run('reproduce_cinema_labels.py','restore','--input',ROOT/'pipelines/configs/cinema_four_vi_labels.v1.json','--output',output/'cinema-silver')
        result={}
        for dataset,splits in expected.items():
            observed={name:semantic_sha(read_jsonl(output/dataset/(name+'.jsonl'))) for name in splits}
            if observed!=splits:raise ValueError('Recreated model inputs differ: '+dataset)
            result[dataset]=dict(semantic_sha256=observed,counts={name:len(read_jsonl(output/dataset/(name+'.jsonl'))) for name in splits})
        print(json.dumps(dict(all_four_reproduced=True,host_private_annotations_used=False,host_model_cache_used=False,datasets=result)))


if __name__=='__main__':main()

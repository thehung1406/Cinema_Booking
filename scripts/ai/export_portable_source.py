"""Copy only Git-visible source files, including pending changes, for a clean setup test."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',required=True)
    p.add_argument('--refresh',action='store_true',help='Update only untouched source from a previous test copy; private files stay local')
    args=p.parse_args()
    target=Path(args.output).resolve()
    if (target.exists() and not args.refresh) or not target.is_relative_to((ROOT/'.local').resolve()):
        raise ValueError('Use a new test copy directory inside .local; never overwrite another checkout')
    manifest_path=target.parent/'source-manifest.json'
    previous=json.loads(manifest_path.read_text())['files'] if args.refresh else {}
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
    copied={}
    for name in sorted(set(names)-{''}):
        source=(ROOT/name).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            continue
        if name.startswith(('.local/','.git/','.venv-ai-research/')) or Path(name).name in {'.env','.env.microservices'}:
            raise ValueError('Private/local path unexpectedly entered the Git-visible source list')
        destination=target/name
        if destination.exists() and args.refresh and hashlib.sha256(destination.read_bytes()).hexdigest()!=previous.get(name):
            raise ValueError('Test source was edited independently; choose a new copy instead of overwriting it')
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
        copied[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(dict(files=copied,git_metadata_copied=False,
        private_env_copied=False,model_cache_copied=False),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(files=len(copied),output=str(target),private_env_copied=False,model_cache_copied=False)))


if __name__=='__main__':
    main()

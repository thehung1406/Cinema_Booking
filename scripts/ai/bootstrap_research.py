"""Optional research environment, independent of the author's .local venvs."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--device',choices=['cpu','cu128'],default='cpu')
    args=p.parse_args()
    if sys.version_info[:2] not in {(3,11),(3,12)}:
        p.error('Use Python 3.11 or 3.12 for the pinned research libraries')
    destination=ROOT/'.venv-ai-research'
    if destination.exists():
        p.error('Research environment already exists; reuse it or choose a separate workspace, never overwrite it')
    venv.EnvBuilder(with_pip=True).create(destination)
    python=destination/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','torch==2.10.0','--index-url',f'https://download.pytorch.org/whl/{args.device}'],check=True)
    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'pipelines/requirements-research.txt'),
        '-e',str(ROOT/'packages/python-platform'),'-e',str(ROOT/'services/ai-service'),'-e',str(ROOT/'services/review-service')],check=True)
    print('Research environment ready at '+str(destination))
    print('Set PYTHONPATH to the repository root and pipelines. See docs/AI_PORTABLE_SETUP.md for data/PDF downloads and experiments.')


if __name__=='__main__':
    main()

"""Restore collected PDFs from tracked source URLs and SHA locks. Standard library."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]


def main():
    manifest=json.loads((ROOT/'pipelines/knowledge/sources.json').read_text(encoding='utf-8'))
    for source in manifest['sources']:
        if source['source_type']!='pdf':
            continue
        target=(ROOT/source['local_file']).resolve()
        if not target.is_relative_to((ROOT/'.local').resolve()):
            raise ValueError('PDF cache must remain inside the workspace .local directory')
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('Existing PDF differs from source lock; keep it and review separately')
            print(source['source_id']+': checksum verified')
            continue
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_suffix('.download')
        try:
            digest=hashlib.sha256()
            total=0
            with urlopen(source.get('download_mirror',source['source_url']),timeout=120) as response,temporary.open('wb') as stream:
                while block:=response.read(1024*1024):
                    total+=len(block)
                    if total>30_000_000:
                        raise ValueError('Unexpected PDF size')
                    digest.update(block)
                    stream.write(block)
            if digest.hexdigest()!=source['sha256'] or not temporary.read_bytes().startswith(b'%PDF-'):
                raise ValueError('Downloaded PDF differs from the locked source')
            temporary.replace(target)
            print(source['source_id']+': downloaded and checksum verified')
        finally:
            if temporary.exists():
                temporary.unlink()


if __name__=='__main__':
    main()

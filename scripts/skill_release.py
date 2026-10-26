"""Seal and verify portable Skill content; no connection or generation calls."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='release-manifest.json'


def content_files(root):
    root=Path(root)
    return sorted((p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and p.suffix!='.pyc' and (p.relative_to(root).parts[0] in ('scripts','references','examples','agents','assets')
                   or p.relative_to(root).as_posix() in ('SKILL.md','README.md'))),key=lambda p:p.relative_to(root).as_posix())


def fingerprint(root):
    root=Path(root);files={}
    for path in content_files(root):
        if path.is_symlink():raise ValueError('RELEASE_SYMLINK_UNSUPPORTED')
        rel=path.relative_to(root).as_posix();data=path.read_bytes()
        if rel in ('SKILL.md','agents/openai.yaml'):
            data=data.decode('utf-8').replace('detail-flow-starcanvas','detail-flow').encode('utf-8')
        files[rel]=hashlib.sha256(data).hexdigest()
    digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'content_sha256':digest,'files':files}


def verify(root,require_seal=False):
    root=Path(root).resolve();actual=fingerprint(root);path=root/MANIFEST
    if not path.exists():
        if require_seal:raise ValueError('RELEASE_MANIFEST_MISSING')
        return dict(actual,revision='development-unsealed',sealed=False)
    declared=json.loads(path.read_text(encoding='utf-8'))
    if declared.get('version')!=1 or not isinstance(declared.get('revision'),str):raise ValueError('RELEASE_MANIFEST_INVALID')
    if any(declared.get(k)!=actual[k] for k in ('content_sha256','files')):
        raise ValueError('RELEASE_CONTENT_MISMATCH: installed Skill differs from its release; finish the upgrade before execution')
    return dict(actual,revision=declared['revision'],sealed=True)


def verify_receipt(root,receipt):
    actual=verify(root,require_seal=True)
    ready=json.loads(Path(receipt).read_text(encoding='utf-8'))
    if Path(ready.get('skill_path','')).resolve()!=Path(root).resolve():raise ValueError('READY_SKILL_PATH_MISMATCH')
    if ready.get('skill_content_sha256')!=actual['content_sha256'] or ready.get('skill_revision')!=actual['revision']:
        raise ValueError('READY_RELEASE_MISMATCH: refresh the actual installed revision receipt')
    if ready.get('status')!='ready':raise ValueError('READY_CONNECTION_NOT_VERIFIED')
    return actual


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('seal','verify'))
    p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--revision');p.add_argument('--receipt',type=Path)
    a=p.parse_args()
    if a.command=='seal':
        if not a.revision:p.error('seal requires --revision')
        value=dict(version=1,revision=a.revision,**fingerprint(a.root))
        path=a.root/MANIFEST;temp=path.with_suffix('.json.tmp')
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
    value=verify_receipt(a.root,a.receipt) if a.receipt else verify(a.root,require_seal=True)
    print(json.dumps({k:v for k,v in value.items() if k!='files'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()

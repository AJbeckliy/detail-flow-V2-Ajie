"""Agent-operated local setup; never generates or prints connection secrets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from skill_release import content_files,verify as verify_release

ROOT=Path(__file__).resolve().parents[1]

def require(condition,message):
    if not condition:raise ValueError(message)

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('x',encoding='utf-8') as f:
        os.chmod(tmp,0o600)
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)

def read_connection(path,server='synmew-canvas'):
    path=Path(path)
    if path.suffix.lower()=='.toml':
        try:import tomllib
        except ImportError:
            try:import tomli as tomllib
            except ImportError:raise ValueError('TOML_READER_MISSING: use Python 3.11+ or an exported MCP JSON') from None
        data=tomllib.loads(path.read_text(encoding='utf-8-sig'))
        value=data.get('mcp_servers',{}).get(server)
    else:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        value=data.get('mcpServers',{}).get(server) if 'mcpServers' in data else data
    require(isinstance(value,dict),'CONNECTION_MISSING: selected source has no matching server')
    require(value.get('enabled') is not False and value.get('disabled') is not True,'CONNECTION_DISABLED: preserve disabled entries')
    require(value.get('type',value.get('transport','stdio'))=='stdio','STDIO_REQUIRED: export the local Starcanvas stdio connection')
    command=value.get('command','');args=value.get('args',[])
    require(isinstance(command,str) and Path(command).is_absolute() and Path(command).is_file(),'BRIDGE_MISSING: official executable path is missing')
    require(Path(command).name.lower() in ('synmewinfinitecanvas.exe','synmewinfinitecanvas') and args==['--mcp-server'],
            'UNSUPPORTED_BRIDGE: expected official SynMewInfiniteCanvas --mcp-server')
    env=value.get('env',{})
    require(isinstance(env,dict) and all(isinstance(k,str) and isinstance(v,(str,int)) for k,v in env.items()),'INVALID_ENV')
    require(all(str(env.get(k,os.environ.get(k,''))).strip() for k in ('SYNMEW_MCP_TOKEN','SYNMEW_MCP_PORT')),
            'PAIRING_REQUIRED: export the local connection from Starcanvas; do not paste tokens into chat')
    require(not any('${' in str(v) for v in env.values()),'UNEXPANDED_ENV: use actual local values or inherited environment')
    return {k:value[k] for k in ('command','args','env','cwd') if k in value}

def install_skill(target):
    target=Path(target).resolve()
    source_release=verify_release(ROOT)
    if target==ROOT:return {'action':'already_installed','path':str(target)}
    require(not target.is_relative_to(ROOT) and not ROOT.is_relative_to(target),'INVALID_SKILL_TARGET')
    files=content_files(ROOT)
    if (ROOT/'release-manifest.json').exists():files.append(ROOT/'release-manifest.json')
    require(not any(p.is_symlink() for p in ROOT.rglob('*')),'SYMLINK_SOURCE_UNSUPPORTED')
    require(not any(p.is_symlink() for p in [target,*target.parents]),'SYMLINK_TARGET_UNSUPPORTED')
    require(not target.exists() or not any(p.is_symlink() for p in target.rglob('*')),'SYMLINK_TARGET_UNSUPPORTED')
    changed=[p for p in files if not (target/p.relative_to(ROOT)).is_file() or p.read_bytes()!=(target/p.relative_to(ROOT)).read_bytes()]
    if not changed:return {'action':'unchanged','path':str(target)}
    backup=None
    if target.exists():
        # Sibling Skill directories are scanned too; never place SKILL.md backups there.
        backup_root=target.parent.parent/'skill-backups'
        require(not backup_root.resolve().is_relative_to(target.parent.resolve()),'BACKUP_MUST_BE_OUTSIDE_SKILL_SCAN_ROOT')
        require(not any(p.is_symlink() for p in [backup_root,*backup_root.parents]),'SYMLINK_BACKUP_UNSUPPORTED')
        backup_root.mkdir(parents=True,exist_ok=True)
        backup=backup_root/(target.name+'.backup-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
        shutil.copytree(target,backup)
    for p in changed:
        dest=target/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    require(all(p.read_bytes()==(target/p.relative_to(ROOT)).read_bytes() for p in files),'INSTALL_VERIFY_FAILED')
    require(verify_release(target)['content_sha256']==source_release['content_sha256'],'INSTALL_RELEASE_MISMATCH')
    return {'action':'installed','path':str(target),'files':len(files),'backup_path':str(backup) if backup else None}

def has_pillow(python):
    return subprocess.run([str(python),'-c','from PIL import Image; Image.new("RGB",(1,1))'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0

def runtime(state,fix):
    require(sys.version_info>=(3,10),'PYTHON_REQUIRED: use an existing Python 3.10+ runtime')
    local=state/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if local.exists() and has_pillow(local):return local
    if has_pillow(sys.executable):return Path(sys.executable)
    require(fix,'PILLOW_MISSING: rerun setup with --fix-deps; do not install browser test dependencies')
    if not local.exists():
        result=subprocess.run([sys.executable,'-m','venv',str(state/'venv')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        require(result.returncode==0,'VENV_FAILED: use the host managed Python with Pillow')
    result=subprocess.run([str(local),'-m','pip','install','--disable-pip-version-check','Pillow'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    require(result.returncode==0 and has_pillow(local),'DEPENDENCY_INSTALL_FAILED: verify package access or supply a managed Python with Pillow')
    return local

def probe(python,connection,skill_root=None):
    result=subprocess.run([str(python),'-X','utf8','-B',str((skill_root or ROOT)/'scripts/starcanvas_executor.py'),'--connection',str(connection),'doctor'],
                          capture_output=True,text=True,encoding='utf-8',timeout=120)
    require(result.returncode==0,'MCP_CHECK_FAILED: automatic readiness check did not succeed; inspect the actual bridge error and local connection configuration; never invent an MCP enable switch or trust step; no generation attempted')
    try:value=json.loads(result.stdout)
    except ValueError:raise ValueError('MCP_CHECK_FAILED: invalid doctor response') from None
    require(value.get('workspace_read') is True and value.get('required_tools_present') is True,'MCP_CAPABILITY_MISSING')
    return {'workspace_read':True,'required_tools_present':True,'paid_calls':0}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connection-source',type=Path,help='Existing trusted local JSON/TOML or official exported MCP JSON; never print its contents')
    p.add_argument('--server',default='synmew-canvas')
    p.add_argument('--state-dir',type=Path,default=Path.home()/'.detail-flow')
    p.add_argument('--install-to',type=Path,help='Host-verified Skill destination; do not guess client paths')
    p.add_argument('--fix-deps',action='store_true',help='Install missing Pillow into a private venv, never global Python')
    p.add_argument('--apply',action='store_true',help='Perform authorized installation/setup; otherwise inspect without writing')
    a=p.parse_args();state=a.state_dir.resolve();receipt=state/'ready.json'
    try:
        require(not state.is_relative_to(ROOT) and not ROOT.is_relative_to(state),'STATE_MUST_BE_OUTSIDE_SKILL')
        require(not any(x.is_symlink() for x in [state,*state.parents]),'SYMLINK_STATE_UNSUPPORTED')
        source=a.connection_source or state/'connection.json'
        require(source.is_file(),'CONNECTION_SOURCE_REQUIRED: inspect existing host tools/config first; otherwise ask only for the official local export')
        cfg=read_connection(source,a.server)
        if not a.apply:
            print(json.dumps({'status':'configuration_found','pillow_available':has_pillow(sys.executable),'applied':False,'live_connection_verified':False}));return 0
        state.mkdir(parents=True,exist_ok=True)
        write_json(receipt,{'status':'checking','generation_authorized':False})
        python=runtime(state,a.fix_deps)
        # Only the dedicated user-local connection is written; native client settings are untouched.
        cached=state/'connection.json'
        if cached.exists() and cached.resolve()!=source.resolve():
            old=json.loads(cached.read_text(encoding='utf-8-sig'))
            if old!=cfg:write_json(state/('connection.backup-'+uuid.uuid4().hex+'.json'),old)
        write_json(cached,cfg)
        installed=install_skill(a.install_to) if a.install_to else {'action':'use_current','path':str(ROOT)}
        skill=Path(installed['path'])
        release=verify_release(skill)
        check=probe(python,cached,skill_root=skill)
        value={'status':'ready','python':str(python),'skill_path':str(skill),'connection_path':str(cached),
               'skill_revision':release['revision'],'skill_content_sha256':release['content_sha256'],'release_sealed':release['sealed'],
               'executor':str(skill/'scripts/starcanvas_executor.py'),'transport':'direct_local_stdio',
               'native_client_registration':'not_required_for_executor','native_client_status':'optional_not_checked','next_action':'follow_user_task',
               'review_html_created':False,'browser_open_requested':False,
               'generation_authorized':False,'check':check,'installation':installed}
        write_json(receipt,value);print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    except Exception as exc:
        # Never echo subprocess output, raw config, arbitrary exception text or secrets.
        message=str(exc) if isinstance(exc,ValueError) and str(exc).split(':')[0].replace('_','').isupper() else 'SETUP_FAILED: input/runtime check failed; credentials omitted'
        if a.apply and receipt.exists():write_json(receipt,{'status':'blocked','reason':message,'generation_authorized':False})
        print(json.dumps({'status':'blocked','reason':message,'generation_authorized':False},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())

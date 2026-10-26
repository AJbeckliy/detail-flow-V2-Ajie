"""Bounded, read-only readiness probes and optional official Windows app startup."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from starcanvas_mcp import StdioMCP,ToolError,TransportError

def official_app(connection):
    command=connection.get('command','')
    p=Path(command)
    return p if (os.name=='nt' and p.is_absolute() and p.is_file()
                 and p.name.lower()=='synmewinfinitecanvas.exe'
                 and connection.get('args')==['--mcp-server']) else None

def app_running(app):
    # Never request CommandLine/Environment: those may contain pairing secrets.
    try:
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); @(Get-Process -Name SynMewInfiniteCanvas -ErrorAction SilentlyContinue | Select-Object Id,Path) | ConvertTo-Json -Compress"],
            capture_output=True,text=True,encoding='utf-8',timeout=8,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if r.returncode:return None
        values=json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(values,dict):values=[values]
        if not isinstance(values,list) or any(not isinstance(v,dict) or not isinstance(v.get('Path'),str) or not v['Path'] for v in values):return None
        if any(os.path.normcase(os.path.abspath(v['Path']))==os.path.normcase(str(app)) for v in values):return True
        # Another install with the same process name: avoid duplicate/single-instance conflicts.
        return None if values else False
    except (OSError,ValueError,subprocess.TimeoutExpired):return None

def launch_app(app):
    try:
        return subprocess.Popen([str(app)],cwd=str(app.parent),stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
    except OSError:raise TransportError('Starcanvas could not start; verify the installed app. No generation submitted') from None

@contextmanager
def startup_lock(app):
    import msvcrt
    key=hashlib.sha256(str(app).lower().encode()).hexdigest()[:20]
    path=Path(tempfile.gettempdir())/('detail-flow-startup-'+key+'.lock')
    with path.open('a+b') as f:
        if f.tell()==0:f.write(b'0');f.flush()
        f.seek(0)
        try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise TransportError('Another startup check is active; wait for it before reconnecting') from None
        try:yield
        finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)

def probe(connection,factory,rpc_timeout,deadline,clock):
    c=None
    try:
        def budget():
            remaining=deadline-clock()
            if remaining<=0:raise TransportError('Starcanvas readiness deadline reached')
            return min(rpc_timeout,5,remaining)
        c=factory(connection,timeout=budget())
        c.timeout=budget();c.resource('canvas://guide/workflow')
        c.timeout=budget();c.call('workspace_get_context',{})
        c.timeout=rpc_timeout
        return c
    except Exception:
        if c is not None:c.close()
        raise

@contextmanager
def ready_client(connection,rpc_timeout=45,wait_seconds=30,auto_start=True,factory=StdioMCP,
                 clock=time.monotonic,sleep=time.sleep):
    """Retries readiness reads only. Never wraps/retries paid calls inside the yield."""
    deadline=clock()+wait_seconds
    try:client=probe(connection,factory,rpc_timeout,deadline,clock)
    except (ToolError,TransportError,OSError):
        app=official_app(connection) if auto_start else None
        if app is None:raise TransportError('MCP unavailable; automatic startup requires a verified local Windows Starcanvas executable') from None
        with startup_lock(app):
            # Recheck under the OS lock: another installer may just have started the app.
            try:client=probe(connection,factory,rpc_timeout,deadline,clock)
            except (ToolError,TransportError,OSError):
                running=app_running(app)
                if running is None:raise TransportError('Cannot determine Starcanvas process state; preserved existing apps. Open the app and verify pairing') from None
                if not running:launch_app(app)  # At most once. Never terminate the desktop app.
                client=None
                while clock()<deadline:
                    sleep(min(1,max(0,deadline-clock())))
                    try:
                        client=probe(connection,factory,rpc_timeout,deadline,clock);break
                    except (ToolError,TransportError,OSError):pass
                if client is None:raise TransportError('Starcanvas MCP did not become ready in time; inspect the actual bridge error and connection configuration; no MCP enable switch should be assumed. No generation resubmitted') from None
    try:yield client
    finally:client.close()

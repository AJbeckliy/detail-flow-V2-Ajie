"""Host-neutral MCP stdio transport. No credential discovery or client configuration edits."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


class TransportError(RuntimeError):
    """A request may have reached the server; never automatically retry a mutation."""


class ToolError(RuntimeError):
    """An explicit server rejection; raw server text is not echoed into logs."""


def load_connection(path, server='synmew-canvas'):
    value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if 'mcpServers' in value:
        value=value['mcpServers'].get(server)
    if not isinstance(value,dict) or not isinstance(value.get('command'),str) or not value['command']:
        raise ValueError('Provide a local MCP stdio connection with command and args')
    if value.get('type',value.get('transport','stdio'))!='stdio':
        raise ValueError('This executor supports the local Starcanvas stdio server')
    args=value.get('args',[]);env=value.get('env',{})
    if not isinstance(args,list) or not all(isinstance(x,str) for x in args):
        raise ValueError('MCP args must be a string array')
    if not isinstance(env,dict) or not all(isinstance(k,str) and isinstance(v,(str,int)) for k,v in env.items()):
        raise ValueError('MCP env must contain scalar values')
    return {k:value[k] for k in ('command','args','env','cwd') if k in value}


class StdioMCP:
    def __init__(self, connection, timeout=45):
        self.timeout=timeout
        self.responses=queue.Queue()
        self.request_id=0
        self.lock=threading.Lock()
        env=dict(os.environ);env.update({k:str(v) for k,v in connection.get('env',{}).items()})
        try:
            self.process=subprocess.Popen([connection['command'],*connection.get('args',[])],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                env=env,cwd=connection.get('cwd'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        except OSError:
            raise TransportError('Cannot launch configured MCP server; connection details omitted') from None
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
        try:
            self.server=self.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},
                'clientInfo':{'name':'detail-flow-executor','version':'1.0.0'}})
            self._send({'jsonrpc':'2.0','method':'notifications/initialized'})
        except Exception:
            self.close();raise

    def _read(self):
        try:
            for line in iter(self.process.stdout.readline,b''):
                try:message=json.loads(line)
                except (ValueError,UnicodeError):continue
                if isinstance(message,dict):self.responses.put(message)
        finally:
            self.responses.put(None)

    def _send(self,message):
        try:
            self.process.stdin.write((json.dumps(message,ensure_ascii=False)+'\n').encode('utf-8'))
            self.process.stdin.flush()
        except (OSError,ValueError):
            raise TransportError('MCP connection closed during request; outcome may be unknown') from None

    def request(self,method,params):
        # Mutations are sequential; actual generations are submitted in one nodeIds call.
        with self.lock:
            self.request_id+=1;rid=self.request_id
            self._send({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
            deadline=time.monotonic()+self.timeout
            while time.monotonic()<deadline:
                try:reply=self.responses.get(timeout=max(.01,deadline-time.monotonic()))
                except queue.Empty:break
                if reply is None:raise TransportError('MCP server disconnected; request outcome may be unknown')
                if reply.get('id')!=rid:continue
                if 'error' in reply:raise ToolError(f'MCP {method} rejected the request')
                if not isinstance(reply.get('result'),dict):raise TransportError('Invalid MCP result envelope')
                return reply['result']
            raise TransportError(f'MCP {method} timed out; do not automatically resubmit')

    def call(self,name,args):
        result=self.request('tools/call',{'name':name,'arguments':args})
        if result.get('isError'):raise ToolError(f'{name} returned an error')
        text='\n'.join(c.get('text','') for c in result.get('content',[]) if c.get('type')=='text')
        try:payload=json.loads(text)
        except ValueError:
            payload=result.get('structuredContent')
        if not isinstance(payload,dict) or payload.get('ok') is not True:
            raise ToolError(f'{name} did not return a successful Starcanvas envelope')
        return payload

    def resource(self,uri):
        result=self.request('resources/read',{'uri':uri})
        text='\n'.join(c['text'] for c in result.get('contents',[]) if isinstance(c.get('text'),str))
        if not text:raise ToolError('Requested MCP resource is unavailable')
        return text

    def tools(self):
        items=[];cursor=None;seen=set()
        for _ in range(20):
            result=self.request('tools/list',{'cursor':cursor} if cursor else {})
            items.extend(result.get('tools',[]));cursor=result.get('nextCursor')
            if not cursor:return items
            if cursor in seen:raise ToolError('Repeated tools cursor')
            seen.add(cursor)
        raise ToolError('Tool listing exceeded pagination bound')

    def close(self):
        process=getattr(self,'process',None)
        if not process:return
        try:
            if process.stdin:process.stdin.close()
        except OSError:pass
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        reader=getattr(self,'reader',None)
        if reader:reader.join(timeout=1)
        if process.stdout:process.stdout.close()

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

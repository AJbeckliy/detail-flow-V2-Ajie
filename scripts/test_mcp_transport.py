import json
from pathlib import Path
import sys
import tempfile
import unittest
from starcanvas_mcp import StdioMCP, ToolError, TransportError, load_connection


SERVER=r'''
import json,sys,time
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r:continue
 method=r['method'];params=r.get('params',{})
 if method=='initialize':value={'serverInfo':{'name':'offline-fixture','version':'1'},'capabilities':{}}
 elif method=='resources/read':value={'contents':[{'text':'fixture guide'}]}
 elif method=='tools/list':
  value={'tools':[{'name':'second'}]} if params.get('cursor') else {'tools':[{'name':'first'}],'nextCursor':'next'}
 elif method=='tools/call':
  name=params['name']
  if name=='slow':time.sleep(2)
  if name=='error':value={'isError':True,'content':[{'type':'text','text':'SECRET-MUST-NOT-BE-LOGGED'}]}
  else:value={'content':[{'type':'text','text':json.dumps({'ok':True,'data':{'name':name},'meta':{}})}]}
 else:value={}
 print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':value}),flush=True)
'''


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-transport-'))
        self.server=self.root/'server.py';self.server.write_text(SERVER,encoding='utf-8')
        self.connection={'command':sys.executable,'args':['-u',str(self.server)]}

    def test_initialize_resource_pagination_and_tool_envelope(self):
        with StdioMCP(self.connection,timeout=2) as c:
            self.assertEqual(c.server['serverInfo']['name'],'offline-fixture')
            self.assertEqual(c.resource('fixture://guide'),'fixture guide')
            self.assertEqual([t['name'] for t in c.tools()],['first','second'])
            self.assertEqual(c.call('hello',{})['data'],{'name':'hello'})

    def test_timeout_is_explicit_and_does_not_retry(self):
        with StdioMCP(self.connection,timeout=10) as c:
            c.timeout=.5  # Measure a slow call, not platform-dependent process cold start.
            with self.assertRaises(TransportError):c.call('slow',{})

    def test_error_does_not_echo_server_secrets(self):
        with StdioMCP(self.connection,timeout=2) as c:
            with self.assertRaises(ToolError) as caught:c.call('error',{})
            self.assertNotIn('SECRET',str(caught.exception))

    def test_connection_load_is_explicit_and_accepts_export_shape(self):
        p=self.root/'connection.json';p.write_text(json.dumps({'mcpServers':{'synmew-canvas':self.connection}}),encoding='utf-8')
        self.assertEqual(load_connection(p),self.connection)
        p.write_text(json.dumps({'command':'x','args':'not-array'}),encoding='utf-8')
        with self.assertRaises(ValueError):load_connection(p)


if __name__=='__main__':unittest.main()

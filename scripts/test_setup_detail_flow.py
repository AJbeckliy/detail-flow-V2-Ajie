import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import setup_detail_flow as setup

class SetupTests(unittest.TestCase):
    def test_installation_never_opens_review_browser_or_creates_html(self):
        state=self.root/'quiet-state'
        args=['setup','--connection-source',str(self.source),'--state-dir',str(state),'--apply']
        with patch('sys.argv',args),patch.object(setup,'runtime',return_value=Path('python')),patch.object(setup,'probe',return_value={'paid_calls':0}),patch('webbrowser.open') as browser,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.main(),0)
        browser.assert_not_called()
        self.assertFalse(list(state.rglob('*.html')))
        receipt=json.loads((state/'ready.json').read_text(encoding='utf-8'))
        self.assertFalse(receipt['review_html_created']);self.assertFalse(receipt['browser_open_requested'])

    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='detail-setup-test-'))
        self.exe=self.root/'SynMewInfiniteCanvas.exe';self.exe.write_bytes(b'fixture never executed')
        self.config={'command':str(self.exe),'args':['--mcp-server'],'env':{'SYNMEW_MCP_TOKEN':'TEST-SECRET','SYNMEW_MCP_PORT':'123'}}
        self.source=self.root/'export.json';self.source.write_text(json.dumps({'mcpServers':{'synmew-canvas':self.config}}),encoding='utf8')
    def test_export_and_disabled_entry(self):
        self.assertEqual(setup.read_connection(self.source),self.config)
        self.config['enabled']=False;self.source.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'DISABLED'):setup.read_connection(self.source)
    def test_arbitrary_command_not_executed(self):
        self.config['args']=['-c','danger'];self.source.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_BRIDGE'):setup.read_connection(self.source)
    def test_preview_no_files_and_no_probe(self):
        state=self.root/'state'
        args=['setup','--connection-source',str(self.source),'--state-dir',str(state)]
        with patch('sys.argv',args),patch.object(setup,'probe') as probe,contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(setup.main(),0)
        self.assertFalse(state.exists());probe.assert_not_called();self.assertNotIn('TEST-SECRET',out.getvalue())
    def test_apply_reuse_and_failed_probe_clear_ready(self):
        state=self.root/'state';args=['setup','--connection-source',str(self.source),'--state-dir',str(state),'--apply']
        with patch('sys.argv',args),patch.object(setup,'runtime',return_value=Path('python')),patch.object(setup,'probe',return_value={'paid_calls':0}),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(setup.main(),0);self.assertEqual(setup.main(),0)
        self.assertNotIn('TEST-SECRET',out.getvalue());self.assertFalse(list(state.glob('connection.backup-*')))
        self.assertEqual(json.loads((state/'ready.json').read_text(encoding='utf-8'))['status'],'ready')
        with patch('sys.argv',args),patch.object(setup,'runtime',return_value=Path('python')),patch.object(setup,'probe',side_effect=RuntimeError('TEST-SECRET')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(setup.main(),2)
        self.assertNotIn('TEST-SECRET',out.getvalue());self.assertEqual(json.loads((state/'ready.json').read_text(encoding='utf-8'))['status'],'blocked')
    def test_install_preserves_prior_files_and_repeat_is_noop(self):
        source=self.root/'bundle';source.mkdir();(source/'SKILL.md').write_text('new')
        target=self.root/'installed';target.mkdir();(target/'SKILL.md').write_text('old');(target/'custom.txt').write_text('keep')
        with patch.object(setup,'ROOT',source):
            installed=setup.install_skill(target)
            self.assertEqual(installed['action'],'installed')
            self.assertEqual(setup.install_skill(target)['action'],'unchanged')
        self.assertEqual((target/'custom.txt').read_text(encoding='utf-8'),'keep')
        backup=Path(installed['backup_path'])
        self.assertFalse(backup.is_relative_to(target.parent))
        self.assertEqual((backup/'SKILL.md').read_text(encoding='utf-8'),'old')
        self.assertEqual(len(list(self.root.glob('installed.backup-*'))),0)
    def test_missing_pairing_is_explicit(self):
        self.config['env']['SYNMEW_MCP_TOKEN']='';self.source.write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError,'PAIRING_REQUIRED'):setup.read_connection(self.source)

if __name__=='__main__':unittest.main()

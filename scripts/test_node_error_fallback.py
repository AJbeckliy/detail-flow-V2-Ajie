"""Observed MCP split: frozen task is generic, export omits error, node has 503."""
import copy
import unittest
import test_master_fallback as fixtures
from master_fallback import run_chain

OBSERVED_ERROR='第三方服务返回异常状态码: 503, 响应: Model service unavailable. Try again later or choose another model.'


class NodeErrorFallbackTests(unittest.TestCase):
    def worker(self,error=OBSERVED_ERROR,change=None):
        f=fixtures.MasterFallbackTests().setup_worker(1,'作坊续跑后仍有错误行')
        original=f.server.call
        def call(name,args):
            if name=='canvas_get_node':
                f.server.calls.append((name,copy.deepcopy(args)))
                node=copy.deepcopy(f.server.nodes[args['nodeId']])
                node['rows'][0].update(status='error',error=error,result=[])
                if change:change(node)
                return {'ok':True,'data':{'node':node,'incoming':[],'outgoing':[]},'meta':{'projectId':f.server.project}}
            return original(name,args)
        f.server.call=call
        return f

    def test_real_row_error_shape_advances_when_export_has_no_error(self):
        f=self.worker()
        result=run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(result['status'],'complete_needs_review')
        self.assertEqual(len(f.server.submissions),2)
        self.assertTrue(list(f.folder.glob('fallback-node-error-*.json')))
        run_chain(f.worker,resume=True,max_wait=10,poll_interval=1)
        self.assertEqual(len(f.server.submissions),2)

    def test_account_errors_in_live_row_do_not_advance(self):
        for error in ('Upstream model service error: rate limit exceeded','503 余额不足'):
            with self.subTest(error=error):
                f=self.worker(error);run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
                self.assertEqual(len(f.server.submissions),1)

    def test_mismatched_live_row_or_inputs_or_result_cannot_authorize_fallback(self):
        changes=(lambda n:n.update(id='wrong-node'),
                 lambda n:n['rows'][0].update(id='wrong-row'),
                 lambda n:n['rows'][0].update(prompt='different request'),
                 lambda n:n['rows'][0].update(images=[]),
                 lambda n:n['rows'][0].update(result=['some output']),
                 lambda n:n['rows'][0].update(status='running'))
        for change in changes:
            with self.subTest(change=change):
                f=self.worker(change=change);run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
                self.assertEqual(len(f.server.submissions),1)

    def test_reused_workshop_does_not_borrow_another_attempt_error(self):
        f=self.worker();original=f.server.call
        def reused(name,args):
            result=original(name,args)
            if name=='task_list' and result['data']['items']:
                other=copy.deepcopy(result['data']['items'][0]);other['id']='other-attempt'
                result['data']['items'].append(other)
            return result
        f.server.call=reused
        run_chain(f.worker,execute=True,max_wait=10,poll_interval=1)
        self.assertEqual(len(f.server.submissions),1)


if __name__=='__main__':unittest.main()

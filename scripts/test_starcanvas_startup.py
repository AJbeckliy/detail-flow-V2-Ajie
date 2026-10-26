from contextlib import nullcontext
from pathlib import Path
import unittest
from unittest.mock import patch,Mock
import starcanvas_startup as startup
from starcanvas_mcp import TransportError

class StartupTests(unittest.TestCase):
    def setUp(self):
        self.client=Mock();self.now=0
    def clock(self):return self.now
    def sleep(self,n):self.now+=n
    def run_case(self,probe,process=False):
        return (patch.object(startup,'probe',side_effect=probe),
                patch.object(startup,'official_app',return_value=Path('C:/SynMewInfiniteCanvas.exe')),
                patch.object(startup,'startup_lock',return_value=nullcontext()),
                patch.object(startup,'app_running',return_value=process))
    def test_ready_connection_does_not_launch(self):
        with patch.object(startup,'probe',return_value=self.client),patch.object(startup,'launch_app') as launch:
            with startup.ready_client({}) as c:self.assertIs(c,self.client)
        launch.assert_not_called();self.client.close.assert_called_once()
    def test_closed_app_started_once_then_ready(self):
        a,b,c,d=self.run_case([TransportError(),TransportError(),TransportError(),self.client])
        with a,b,c,d,patch.object(startup,'launch_app') as launch:
            with startup.ready_client({},clock=self.clock,sleep=self.sleep) as client:self.assertIs(client,self.client)
        launch.assert_called_once()
    def test_already_running_is_not_relaunched(self):
        a,b,c,d=self.run_case([TransportError(),TransportError(),self.client],True)
        with a,b,c,d,patch.object(startup,'launch_app') as launch:
            with startup.ready_client({},clock=self.clock,sleep=self.sleep):pass
        launch.assert_not_called()
    def test_timeout_stops_without_restart_loop(self):
        a,b,c,d=self.run_case(TransportError())
        with a,b,c,d,patch.object(startup,'launch_app') as launch:
            with self.assertRaisesRegex(TransportError,'in time'):
                with startup.ready_client({},wait_seconds=3,clock=self.clock,sleep=self.sleep):pass
        launch.assert_called_once();self.assertEqual(self.now,3)
    def test_unknown_process_state_does_not_launch(self):
        a,b,c,d=self.run_case(TransportError(),None)
        with a,b,c,d,patch.object(startup,'launch_app') as launch:
            with self.assertRaisesRegex(TransportError,'process state'):
                with startup.ready_client({},clock=self.clock,sleep=self.sleep):pass
        launch.assert_not_called()
    def test_paid_call_failure_is_not_retried(self):
        with patch.object(startup,'probe',return_value=self.client) as probe:
            with self.assertRaises(TransportError):
                with startup.ready_client({}):raise TransportError('lost paid acknowledgement')
        probe.assert_called_once();self.client.close.assert_called_once()
    def test_probe_failure_closes_owned_bridge(self):
        self.client.resource.side_effect=TransportError()
        with self.assertRaises(TransportError):startup.probe({},lambda *a,**k:self.client,45,30,self.clock)
        self.client.close.assert_called_once()

if __name__=='__main__':unittest.main()

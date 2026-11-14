"""Offline tests, no real credentials or paid calls."""
import base64
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import image_api as api


def config(host='https://example.invalid/v1',model='user-image-model',protocol='images_sync_v1'):
    return dict(base_url=host,model=model,protocol=protocol,key_env='DETAIL_FLOW_API_KEY',
        paths=dict(check='models',generate='images/generations',edit='images/edits',upload='files/upload',status='image/generations/{id}'),
        check_kind='models',image_field='image[]',max_images=8,max_image_bytes=20000000,
        image_formats=['png','jpeg','webp'], parameters={'size':['1024x1536']},
        evidence=dict(source='https://example.invalid/docs',reference_images=True,model=model,notes='offline fixture'))


class GenericTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'DETAIL_FLOW_API_KEY':'test-secret-not-a-real-key'});self.env.start()
        self.c=config();self.payload={'prompt':'approved text','images':[],'parameters':{'size':'1024x1536'}}
    def tearDown(self):
        self.env.stop();self.tmp.cleanup()
    def receipt(self,c=None):
        c=c or self.c
        return dict(status='ready',config_hash=api.digest(c),key_hash=api.digest(api.key(c)))
    def test_two_arbitrary_hosts_and_models(self):
        for c in [self.c,config('https://another.invalid/custom','another-image')]:
            with patch.object(api,'request',return_value={'data':[{'id':c['model']}]}) as net:
                api.check(c,self.root/'ready.json');net.assert_called_once_with(c,'check')
                self.assertFalse(api.read(self.root/'ready.json')['generation_verified'])
                self.assertIn(c['base_url'],api.endpoint(c,'generate'))
    def test_unknown_protocol_no_network(self):
        self.c['protocol']='chat_images'
        with patch.object(api,'request') as net, self.assertRaises(ValueError):
            api.check(self.c,self.root/'ready.json')
        net.assert_not_called()
        self.assertEqual(api.read(self.root/'ready.json')['status'],'not_ready')
    def test_missing_model_stops(self):
        with patch.object(api,'request',return_value={'data':[{'id':'other'}]}),self.assertRaises(ValueError):
            api.check(self.c,self.root/'ready.json')
    def test_wrong_key_or_timeout_never_pass(self):
        for error in [TimeoutError(),api.urllib.error.HTTPError('https://example.invalid',401,'unauthorized',{},None)]:
            api.save(self.root/'ready.json',self.receipt())
            with patch.object(api,'request',side_effect=error),self.assertRaises(type(error)):
                api.check(self.c,self.root/'ready.json')
            self.assertEqual(api.read(self.root/'ready.json')['status'],'not_ready')
    def test_reference_evidence_required(self):
        self.c['evidence']['reference_images']=False
        with self.assertRaises(ValueError):api.validate(self.c)
    def test_modified_config_or_key_rejected(self):
        receipt=self.receipt();self.c['base_url']='https://changed.invalid'
        with self.assertRaises(ValueError):api.submit(self.c,receipt,self.payload,self.root/'run')
        self.c=config();os.environ['DETAIL_FLOW_API_KEY']='changed'
        with self.assertRaises(ValueError):api.submit(self.c,receipt,self.payload,self.root/'run')
    def test_dry_run_no_network(self):
        with patch.object(api,'request') as net:
            api.submit(self.c,self.receipt(),self.payload,self.root/'run')
            net.assert_not_called();self.assertFalse((self.root/'run').exists())
    def test_timeout_no_duplicate_submit(self):
        with patch.object(api,'request',side_effect=TimeoutError) as net:
            with self.assertRaises(TimeoutError):api.submit(self.c,self.receipt(),self.payload,self.root/'run',True)
            with self.assertRaises(FileExistsError):api.submit(self.c,self.receipt(),self.payload,self.root/'run',True)
            self.assertEqual(net.call_count,1)
            self.assertEqual(api.read(self.root/'run/state.json')['status'],'submission_uncertain')
    def test_sync_reference_and_base64_collection(self):
        image=self.root/'input.png';__import__('PIL.Image',fromlist=['Image']).new('RGB',(2,2)).save(image)
        self.payload['images']=[str(image)]
        with patch.object(api,'request',return_value={'data':[{'b64_json':base64.b64encode(image.read_bytes()).decode()}]}) as net:
            api.submit(self.c,self.receipt(),self.payload,self.root/'run',True)
            self.assertEqual(net.call_args.args[1],'edit')
            self.assertIn(b'name="image[]"',net.call_args.args[2])
        api.download(self.root/'run');api.download(self.root/'run')
        self.assertEqual((self.root/'run/original.png').read_bytes(),image.read_bytes())
    def test_async_submission_and_resume(self):
        c=config(protocol='images_async_v1')
        with patch.object(api,'request',return_value={'task_id':'task_1'}):
            api.submit(c,self.receipt(c),self.payload,self.root/'run',True)
        with patch.object(api,'request',return_value={'data':{'status':'IN_PROGRESS'}}) as net:
            self.assertEqual(api.status(self.root/'run'),'IN_PROGRESS')
            self.assertEqual(net.call_args.kwargs,{'task_id':'task_1'})
    def test_missing_key_and_model_override(self):
        p=dict(self.payload,model='override')
        with self.assertRaises(ValueError):api.submit(self.c,self.receipt(),p,self.root/'run')
        os.environ.pop('DETAIL_FLOW_API_KEY')
        with self.assertRaises(ValueError):api.key(self.c)
    def test_async_upload_order_and_failure_is_not_downloadable(self):
        c=config(protocol='images_async_v1')
        images=[]
        for index in range(2):
            p=self.root/('ref'+str(index)+'.png');__import__('PIL.Image',fromlist=['Image']).new('RGB',(2,2)).save(p);images.append(str(p))
        self.payload['images']=images
        with patch.object(api,'request',side_effect=[{'url':'https://media.invalid/first.png'},{'url':'https://media.invalid/second.png'},{'id':'task_2'}]) as net:
            api.submit(c,self.receipt(c),self.payload,self.root/'run',True)
            body=api.json.loads(net.call_args.args[2])
            self.assertEqual(body['images'],['https://media.invalid/first.png','https://media.invalid/second.png'])
        api.save(self.root/'run/query.json',{'data':{'status':'FAILURE'}})
        with self.assertRaises(ValueError):api.download(self.root/'run')
    def test_paths_and_parameters_cannot_override_credentials_or_model(self):
        self.c['paths']['edit']='https://another.invalid/images'
        with self.assertRaises(ValueError):api.validate(self.c)
    def test_account_business_failure_not_ready(self):
        self.c['check_kind']='account'
        for response in [{'code':401,'data':{'message':'invalid key'}}, {'success':False,'data':{'message':'failed'}}, {'code':1,'data':{'reason':'unauthorized'}}, {'code':200,'status':False,'data':{'reason':'unauthorized'}}]:
            with patch.object(api,'request',return_value=response),self.assertRaises(ValueError):
                api.check(self.c,self.root/'ready.json')
            self.assertEqual(api.read(self.root/'ready.json')['status'],'not_ready')
    def test_user_agent_is_explicit_and_validated(self):
        self.c['user_agent']='Provider-approved-client/1.0'
        with patch.object(api.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"data":[]}'
            api.request(self.c,'check')
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.get_header('User-agent'),self.c['user_agent'])
        self.c['user_agent']='bad\r\nheader'
        with self.assertRaises(ValueError):api.validate(self.c)
    def test_image_mime_and_collection_recovery(self):
        image=self.root/'input.png';raw=b'\x89PNG\r\n\x1a\nfixture';image.write_bytes(raw)
        body,_=api.multipart({},[('image',image)])
        self.assertIn(b'Content-Type: image/png',body)
        run=self.root/'run';run.mkdir()
        api.save(run/'config.json',self.c);api.save(run/'state.json',{'status':'SUCCESS'})
        api.save(run/'submission.json',{'data':[{'b64_json':base64.b64encode(raw).decode()}]})
        (run/'original.png').write_bytes(raw)
        api.download(run)
        self.assertTrue((run/'collection.json').exists())
    def test_async_terminal_state_is_saved(self):
        c=config(protocol='images_async_v1');run=self.root/'run';run.mkdir()
        api.save(run/'config.json',c);api.save(run/'state.json',{'status':'submitted','task_id':'test'})
        with patch.object(api,'request',return_value={'data':{'status':'FAILURE'}}):
            api.status(run)
        self.assertEqual(api.read(run/'state.json'),{'status':'FAILURE','task_id':'test'})
        self.c=config();self.c['parameters']['model']=['replacement']
        with self.assertRaises(ValueError):api.validate(self.c)


    def media_fixture(self, protocol, name, ua=None):
        c=config(protocol=protocol)
        if ua is not None:c['user_agent']=ua
        folder=self.root/name;folder.mkdir()
        api.save(folder/'config.json',c)
        api.save(folder/'state.json',{'status':'SUCCESS','task_id':'existing_task'})
        if protocol=='images_async_v1':
            api.save(folder/'query.json',{'data':{'status':'SUCCESS','result_url':'https://media.invalid/image.png'}})
        else:
            api.save(folder/'submission.json',{'data':[{'url':'https://media.invalid/image.png'}]})
        return folder

    def test_url_download_uses_client_id_without_key_and_is_idempotent(self):
        from io import BytesIO
        from PIL import Image
        buf=BytesIO();Image.new('RGB',(2,2)).save(buf,format='PNG');raw=buf.getvalue()
        for protocol in ('images_sync_v1','images_async_v1'):
            for ua in (None,'Configured-Client/2.0'):
                folder=self.media_fixture(protocol,protocol+str(ua is None),ua)
                with patch.object(api.urllib.request,'urlopen') as media, patch.object(api,'request') as provider:
                    media.return_value.__enter__.return_value.read.return_value=raw
                    api.download(folder);api.download(folder)
                    media.assert_called_once()
                    req=media.call_args.args[0]
                    self.assertEqual(req.get_method(),'GET')
                    self.assertEqual(dict(req.header_items()),{'User-agent':ua or 'DetailFlow/1.0'})
                    self.assertNotIn(os.environ['DETAIL_FLOW_API_KEY'],str(req.header_items()))
                    provider.assert_not_called()
                    self.assertEqual((folder/'original.png').read_bytes(),raw)

    def test_media_403_never_resubmits_or_changes_task(self):
        folder=self.media_fixture('images_async_v1','failed_download')
        before=(folder/'state.json').read_bytes()
        error=api.urllib.error.HTTPError('https://media.invalid/image.png',403,'Forbidden',{},None)
        with patch.object(api.urllib.request,'urlopen',side_effect=error) as media, patch.object(api,'request') as provider:
            with self.assertRaises(api.urllib.error.HTTPError):api.download(folder)
            media.assert_called_once();provider.assert_not_called()
        self.assertEqual((folder/'state.json').read_bytes(),before)
        self.assertFalse((folder/'collection.json').exists())
        self.assertFalse((folder/'original.png').exists())


if __name__=='__main__':unittest.main()

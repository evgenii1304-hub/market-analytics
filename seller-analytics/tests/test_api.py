import json
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import server

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.old_path=server.DB_PATH
        server.DB_PATH=str(Path(cls.temp.name)/'test.db')
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.url=f'http://127.0.0.1:{cls.http.server_port}'
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join()
        server.DB_PATH=cls.old_path;cls.temp.cleanup()
    def request(self,path,body=None,headers=None):
        headers=headers or {}
        data=json.dumps(body).encode() if body is not None else None
        if data:
            headers={'Content-Type':'application/json','X-CSRF-Token':server.CSRF,**headers}
        request=Request(self.url+path,data=data,headers=headers)
        try:
            with urlopen(request,timeout=5) as r:return r.status,r.read(),r.headers
        except HTTPError as r:return r.code,r.read(),r.headers
    def expense(self):
        return dict(mode='local',account_id='wb-1',day='2026-10-10',kind='overhead',
                    amount='123.45',note='Automated test',request_id=str(uuid.uuid4()))
    def test_static_and_empty_workspace(self):
        status,body,headers=self.request('/')
        self.assertEqual(status,200)
        self.assertIn(b'<html lang="ru">',body)
        self.assertIn('frame-ancestors',headers['Content-Security-Policy'])
        status,body,_=self.request('/api/state?mode=demo')
        self.assertEqual(json.loads(body)['total_entries'],0)
    def test_write_idempotency_and_mode_isolation(self):
        payload=self.expense()
        for _ in range(2):self.assertEqual(self.request('/api/expenses',payload)[0],200)
        state=json.loads(self.request('/api/state?mode=local&start=2026-10-01&end=2026-10-10')[1])
        matching=[r for r in state['entries'] if r['source_id']==payload['request_id']]
        self.assertEqual(len(matching),1);self.assertEqual(matching[0]['amount'],-12345)
        demo=json.loads(self.request('/api/state?mode=demo&start=2026-10-01&end=2026-10-10')[1])
        self.assertEqual(demo['total_entries'],0)
    def test_bad_period(self):
        self.assertEqual(self.request('/api/state?start=2026-10-10&end=2026-09-01')[0],400)
    def test_cross_origin_host_and_csrf(self):
        self.assertEqual(self.request('/api/state',headers={'Host':'evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/expenses',self.expense(),{'Origin':'https://evil.invalid'})[0],403)
        self.assertEqual(self.request('/api/expenses',self.expense(),{'X-CSRF-Token':'bad'})[0],403)
    def test_import_validation_atomicity(self):
        result=self.request('/api/costs/import',dict(mode='local',csv='sku;effective_from;cost_rub\nVALID;2026-09-01;10\nBAD;2026-09-02;-2'))
        self.assertEqual(result[0],400)
        result=json.loads(self.request('/api/state?mode=local')[1])
        self.assertFalse(any(c['sku']=='VALID' for c in result['cost_history']))
    def test_export_and_input_validation(self):
        result=self.request('/api/export?mode=demo')
        self.assertEqual(result[0],200)
        self.assertIn('text/csv',result[2]['Content-Type'])
        self.assertEqual(self.request('/api/expenses',[])[0],400)

if __name__=='__main__':unittest.main()

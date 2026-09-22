import http.client
import json
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest
from app import handler_for
from veitch.model import GroupModel


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(GroupModel.load()))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, content_type="application/json"):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body, {"Content-Type": content_type})
            response = connection.getresponse()
            return response.status, response.read(), response.getheader("Content-Type")
        finally:
            connection.close()

    def test_success(self):
        status, body, _ = self.request("POST", "/api/minimize", json.dumps({"function": "A*B+A*!B"}))
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(result["formula"], "A")
        self.assertIn("<svg", result["svg"])
        self.assertTrue(result["ml"]["enabled"])

    def test_bad_inputs(self):
        for body in ['{"function":"A+"}', '{}', '[]', 'null', '{', '{"function":42}']:
            self.assertEqual(self.request("POST", "/api/minimize", body)[0], 400)
        self.assertEqual(self.request("POST", "/api/minimize", "x" * 9000)[0], 413)
        self.assertEqual(self.request("POST", "/api/minimize", "{}", "text/plain")[0], 415)

    def test_assets_and_status(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertIn("javascript", self.request("GET", "/app.js")[2])
        self.assertTrue(json.loads(self.request("GET", "/api/status")[1])["model_ready"])
        self.assertEqual(self.request("GET", "/../app.py")[0], 404)

    def test_system_endpoint(self):
        status, body, _ = self.request('POST','/api/system',json.dumps({'variables':4,
            'functions':['0,2,4,6,10,12,14','2,3,10','0,1,2,3,9,11']}))
        self.assertEqual(status,200)
        result = json.loads(body)
        self.assertEqual(result['literal_count'],13)
        self.assertIn('<table',result['matrix_html'])
        self.assertIn('<svg', result['sheffer']['svg'])
        self.assertTrue(all(len(g['inputs']) >= 2 for g in result['sheffer']['gates']))
        self.assertTrue(all('formula' in o and 'formula_html' in o for o in result['sheffer']['outputs']))
        self.assertEqual(self.request('POST','/api/system',json.dumps({'variables':2,'functions':['4','']}))[0],400)

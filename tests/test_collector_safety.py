import unittest
from workforce_intelligence.collector import _validate_public_url

class CollectorSafetyTests(unittest.TestCase):
    def test_rejects_private_ip(self):
        with self.assertRaises(ValueError):
            _validate_public_url("http://127.0.0.1/report")

    def test_rejects_localhost(self):
        with self.assertRaises(ValueError):
            _validate_public_url("http://localhost/report")

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(ValueError):
            _validate_public_url("file:///etc/passwd")

    def test_rejects_dns_resolving_to_private_address(self):
        def fake_resolver(host, port, type=None):
            return [(None,None,None,None,("10.0.0.5",0))]
        with self.assertRaises(ValueError):
            _validate_public_url("https://example.com/report",resolver=fake_resolver)

if __name__=="__main__":
    unittest.main()

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse

from workforce_intelligence.collector import (
    _PinnedHTTPConnection,
    _PinnedHTTPSConnectionPool,
    _PinnedIPAdapter,
    _validate_public_url,
    collect_document,
)


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

    def test_rejects_url_credentials(self):
        with self.assertRaises(ValueError):
            _validate_public_url("https://user:pass@example.com/report")

    def test_rejects_dns_resolving_to_private_address(self):
        def fake_resolver(host, port, type=None):
            return [(None, None, None, None, ("10.0.0.5", 0))]
        with self.assertRaises(ValueError):
            _validate_public_url("https://example.com/report", resolver=fake_resolver)

    def test_rejects_mixed_public_and_private_dns_answers(self):
        def fake_resolver(host, port, type=None):
            return [
                (None, None, None, None, ("8.8.8.8", 0)),
                (None, None, None, None, ("192.168.1.8", 0)),
            ]
        with self.assertRaises(ValueError):
            _validate_public_url("https://example.com/report", resolver=fake_resolver)

    def test_adapter_pins_validated_dns_answer(self):
        def fake_resolver(host, port, type=None):
            return [(None, None, None, None, ("8.8.8.8", 0))]
        adapter = _PinnedIPAdapter(resolver=fake_resolver)
        pool = adapter.get_connection("https://example.com/report", proxies={})
        self.assertIsInstance(pool, _PinnedHTTPSConnectionPool)
        self.assertEqual(pool.conn_kw["pinned_ip"], "8.8.8.8")
        adapter.close()

    def test_re_resolved_private_address_is_rejected_before_pool_creation(self):
        answers = iter([
            [(None, None, None, None, ("8.8.8.8", 0))],
            [(None, None, None, None, ("127.0.0.1", 0))],
        ])
        def changing_resolver(host, port, type=None):
            return next(answers)
        adapter = _PinnedIPAdapter(resolver=changing_resolver)
        with self.assertRaises(ValueError):
            adapter.get_connection("https://example.com/report", proxies={})
        adapter.close()

    def test_adapter_rejects_proxy(self):
        from requests.exceptions import ProxyError
        resolver = lambda *a, **kw: [(None, None, None, None, ("8.8.8.8", 0))]
        adapter = _PinnedIPAdapter(resolver=resolver)
        with self.assertRaises(ProxyError):
            adapter.get_connection("https://example.com/report", proxies={"https": "http://proxy.local"})
        adapter.close()

    def test_custom_session_adapter_cannot_bypass_pinning(self):
        session = requests.Session()
        session.mount("https://example.com/", HTTPAdapter())
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "bypasses DNS-pinned collection"):
                collect_document("https://example.com/report", tmp, session=session)
        session.close()

    def test_adapter_pins_real_requests_transport_without_network(self):
        def fake_resolver(host, port, type=None):
            return [(None, None, None, None, ("8.8.8.8", 0))]
        session = requests.Session()
        session.trust_env = False
        adapter = _PinnedIPAdapter(resolver=fake_resolver)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        with patch.object(
            _PinnedHTTPSConnectionPool,
            "urlopen",
            return_value=HTTPResponse(
                body=b"ok", status=200, headers={"Content-Type": "text/plain"},
                preload_content=False,
            ),
        ) as mocked_urlopen:
            response = session.get("https://example.com/", timeout=2, stream=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mocked_urlopen.called)
            self.assertEqual(
                next(iter(adapter._pinned_pools.values())).conn_kw["pinned_ip"],
                "8.8.8.8",
            )
            response.close()
        session.close()

    def test_connection_uses_pinned_ip_not_hostname(self):
        connection = _PinnedHTTPConnection(
            host="example.com", port=80, pinned_ip="8.8.8.8", timeout=2,
        )
        fake_socket = object()
        with patch(
            "workforce_intelligence.collector.connection.create_connection",
            return_value=fake_socket,
        ) as connect:
            result = connection._new_conn()
        self.assertIs(result, fake_socket)
        self.assertEqual(connect.call_args.args[0], ("8.8.8.8", 80))
        self.assertEqual(connect.call_args.kwargs["source_address"], connection.source_address)
        self.assertEqual(connect.call_args.kwargs["socket_options"], connection.socket_options)


if __name__ == "__main__":
    unittest.main()

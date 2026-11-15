import unittest
from unittest.mock import Mock, patch
from workforce_intelligence.gemini_client import GeminiExtractor

class GeminiAdapterTests(unittest.TestCase):
    def test_mocked_gemini_response(self):
        client=Mock()
        client.models.generate_content.return_value=Mock(text='{"findings":[{"problem_type":"Labour shortage","description":"Vacancies in automotive manufacturing plants","supporting_quote":"shortage in automotive manufacturing plants","industry":"Automotive manufacturing"}]}')
        extractor=GeminiExtractor(api_key="test-key",client=client)
        rows=extractor.extract("The source reports a shortage in automotive manufacturing plants.",{"title":"Report","url":"https://example.org/report","industry":"Automotive manufacturing"})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["problem_type"],"Labour shortage")
        self.assertEqual(rows[0]["source_url"],"https://example.org/report")
        client.models.generate_content.assert_called_once()

    @patch("workforce_intelligence.gemini_client.time.sleep")
    def test_retries_transient_503_then_succeeds(self, sleep):
        client=Mock()
        client.models.generate_content.side_effect=[RuntimeError("503 UNAVAILABLE temporary"),Mock(text='{"findings":[]}')]
        extractor=GeminiExtractor(api_key="test-key",client=client,max_attempts=3,retry_delay=0)
        rows=extractor.extract("Manufacturing report text",{"title":"Report","url":"https://example.org/report","industry":"Manufacturing"})
        self.assertEqual(rows,[])
        self.assertEqual(client.models.generate_content.call_count,2)
        sleep.assert_called_once()

    def test_does_not_retry_non_transient_error(self):
        client=Mock()
        client.models.generate_content.side_effect=ValueError("invalid API key")
        extractor=GeminiExtractor(api_key="test-key",client=client,max_attempts=4,retry_delay=0)
        with self.assertRaises(ValueError):
            extractor.extract("Manufacturing report text",{"title":"Report","url":"https://example.org/report","industry":"Manufacturing"})
        self.assertEqual(client.models.generate_content.call_count,1)

if __name__=="__main__":
    unittest.main()

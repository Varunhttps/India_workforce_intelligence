import unittest
from unittest.mock import Mock
from workforce_intelligence.gemini_client import GeminiExtractor
class GeminiAdapterTests(unittest.TestCase):
 def test_mocked_gemini_response(self):
  client=Mock(); client.models.generate_content.return_value=Mock(text='{"findings":[{"problem_type":"Labour shortage","description":"Vacancies in plants","country":"Germany"}]}')
  extractor=GeminiExtractor(api_key="test-key",client=client)
  rows=extractor.extract("The source reports a shortage in German plants.",{"title":"Report","url":"https://example.org/report","industry":"Manufacturing"})
  self.assertEqual(rows[0]["problem_type"],"Labour shortage")
  self.assertEqual(rows[0]["source_url"],"https://example.org/report")
  client.models.generate_content.assert_called_once()
if __name__=="__main__": unittest.main()

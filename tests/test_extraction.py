import json
import unittest
from workforce_intelligence.extraction import parse_extraction_response,build_extraction_prompt
class ExtractionTests(unittest.TestCase):
 def test_source_metadata_overrides_model_attribution(self):
  metadata={"title":"Official report","url":"https://example.org/report"}
  response=json.dumps({"findings":[{"problem_type":"Skill shortage","description":"Shortage in plants","source_url":"https://wrong.example","country":"Germany","evidence":"ignored","confidence":0.9}]})
  row=parse_extraction_response(response,metadata)[0]
  self.assertEqual(row["source_url"],metadata["url"]); self.assertEqual(row["source_name"],metadata["title"])
  self.assertNotIn("evidence",row); self.assertNotIn("confidence",row)
 def test_incomplete_findings_dropped(self):
  self.assertEqual(parse_extraction_response('{"findings":[{"problem_type":"Shortage"}]}',{}),[])
 def test_search_country_is_not_claimed_as_fact(self):
  prompt=build_extraction_prompt("The report says nothing about country.",{"country_searched":"India"})
  self.assertIn("not proof of geography",prompt)
if __name__=="__main__": unittest.main()

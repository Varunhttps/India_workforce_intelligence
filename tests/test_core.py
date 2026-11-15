import unittest
from workforce_intelligence.research_modes import build_research_plan,MANUFACTURING,OTHER
from workforce_intelligence.records import normalize_finding,deduplicate_findings
class Modes(unittest.TestCase):
 def test_default_manufacturing(self): self.assertEqual(build_research_plan().industries,MANUFACTURING)
 def test_other(self): self.assertEqual(build_research_plan("Explore Other Industries").industries,OTHER)
 def test_all(self): self.assertEqual(set(build_research_plan("all").industries),set(MANUFACTURING+OTHER))
 def test_bad_mode(self):
  with self.assertRaises(ValueError): build_research_plan("India only")
class Records(unittest.TestCase):
 def test_search_country_not_inferred(self): self.assertIsNone(normalize_finding({"country_searched":"Germany"})["country"])
 def test_deduplicate(self):
  x={"problem_type":"Skill shortage","country":"Germany","source_url":"https://example.org/a","description":"Shortage"}
  self.assertEqual(len(deduplicate_findings([x,x])),1)
 def test_reject_bad_url(self):
  with self.assertRaises(ValueError): normalize_finding({"source_url":"javascript:alert(1)"})
if __name__=="__main__": unittest.main()

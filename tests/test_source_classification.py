import unittest
from workforce_intelligence.discovery import classify_source_domain

class SourceClassificationTests(unittest.TestCase):
    def test_government_domain(self):
        self.assertEqual(classify_source_domain("bls.gov"), "Government domain (heuristic)")
    def test_multilateral_domain(self):
        self.assertEqual(classify_source_domain("www.ilo.org"), "Intergovernmental / multilateral (heuristic)")
    def test_unknown_domain_is_not_endorsed(self):
        self.assertEqual(classify_source_domain("random-example.com"), "Other / unclassified")

if __name__=="__main__":
    unittest.main()

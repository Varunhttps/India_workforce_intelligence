import unittest

from workforce_intelligence.skill_trends import analyze_skill_trends


class SkillTrendTests(unittest.TestCase):
    def test_classifies_global_cross_industry_skill_signal(self):
        rows = [
            {"problem_type": "Data analytics skill gap", "description": "AI and data analytics skills needed",
             "industry": "Finance", "country": "Germany", "source_url": "https://a.example",
             "weeks_seen": ["2026-11-16"], "last_seen": "2026-11-18"},
            {"problem_type": "Data analytics skill shortage", "description": "Analytics",
             "industry": "Healthcare", "country": "Canada", "source_url": "https://b.example",
             "weeks_seen": ["2026-11-16"], "last_seen": "2026-11-18"},
        ]
        result = analyze_skill_trends(rows, reference_date="2026-11-21")
        skills = {r["skill"]: r for r in result}
        row = skills["Industrial AI, data & analytics"]
        self.assertEqual(row["source_count"], 2)
        self.assertEqual(row["industry_count"], 2)
        self.assertEqual(row["country_count"], 2)
        self.assertEqual(row["trend"], "Emerging signal")

    def test_manufacturing_aware_skill_tags(self):
        rows = [{"problem_type": "Robotics automation skills", "description": "PLC control systems",
                  "industry": "Automotive manufacturing", "country": "Japan",
                  "source_url": "https://example.com/a", "weeks_seen": ["2026-11-16"]}]
        result = analyze_skill_trends(rows, reference_date="2026-11-21")
        row = next(r for r in result if r["skill"] == "Industrial automation & robotics")
        self.assertEqual(row["manufacturing_records"], 1)

    def test_single_source_is_not_called_emerging(self):
        rows = [{"problem_type": "Cybersecurity skill shortage", "industry": "Technology",
                  "country": "United States", "source_url": "https://example.com",
                  "weeks_seen": ["2026-11-16"], "last_seen": "2026-11-18"}]
        row = next(r for r in analyze_skill_trends(rows, reference_date="2026-11-21")
                   if r["skill"] == "Cybersecurity")
        self.assertNotEqual(row["trend"], "Emerging signal")
        self.assertEqual(row["source_count"], 1)

    def test_persistent_signal_requires_multiple_observation_weeks(self):
        rows = [{"problem_type": "Maintenance skills shortage", "industry": "Manufacturing",
                  "source_url": "https://example.com/a", "weeks_seen": ["2026-10-26", "2026-11-02", "2026-11-09"]}]
        row = next(r for r in analyze_skill_trends(rows, reference_date="2026-11-21")
                   if r["skill"] == "Maintenance & reliability")
        self.assertEqual(row["trend"], "Persistent signal")

    def test_old_single_industry_signal_is_labeled_older_finding(self):
        rows = [{"problem_type": "Cybersecurity skill shortage", "industry": "Technology",
                 "source_url": "https://example.com", "weeks_seen": ["2026-08-10"],
                 "last_seen": "2026-08-10"}]
        row = next(r for r in analyze_skill_trends(rows, reference_date="2026-11-21")
                   if r["skill"] == "Cybersecurity")
        self.assertEqual(row["trend"], "Older finding")

    def test_no_keyword_match_returns_empty(self):
        rows = [{"problem_type": "General workforce concern", "industry": "Retail",
                  "description": "Unrelated", "source_url": "https://example.com"}]
        self.assertEqual(analyze_skill_trends(rows, reference_date="2026-11-21"), [])

    def test_duplicate_source_does_not_inflate_source_count(self):
        rows = [
            {"problem_type": "PLC automation skills", "industry": "Manufacturing",
             "source_url": "https://example.com/a", "country": "Germany",
             "weeks_seen": ["2026-11-16"]},
            {"problem_type": "Robotics automation skills", "industry": "Manufacturing",
             "source_url": "https://example.com/a", "country": "Germany",
             "weeks_seen": ["2026-11-16"]},
        ]
        row = next(r for r in analyze_skill_trends(rows, reference_date="2026-11-21")
                   if r["skill"] == "Industrial automation & robotics")
        self.assertEqual(row["source_count"], 1)


if __name__ == "__main__":
    unittest.main()

import unittest

from workforce_intelligence.evidence_integrity import _url_key, audit_evidence_integrity


class EvidenceIntegrityTests(unittest.TestCase):
    def test_clean_records_normalize_tracking_fragments_and_ids(self):
        research = [{"Research ID": "RES-1", "Source ID": "src-1", "Source URL": "https://example.com/report"}]
        register = [{"Source ID": "SRC-1", "Source URL": "https://EXAMPLE.com/report/?utm_source=x#page", "Related Research IDs": "res-1"}]
        opportunity = [{"Opportunity ID": "OP-1", "Related Research IDs": "RES-1", "Supporting Source URLs": "https://example.com/report?utm_campaign=abc"}]
        result = audit_evidence_integrity(research, register, opportunity)
        self.assertEqual(result["warning_count"], 0)
        self.assertEqual(result["info_count"], 0)

    def test_missing_id_and_invalid_url_are_counted(self):
        result = audit_evidence_integrity([{"Source URL": "not a URL"}], [], [])
        metrics = result["metrics"]
        self.assertEqual(metrics["findings_missing_research_id"], 1)
        self.assertEqual(metrics["findings_invalid_source_url"], 1)
        self.assertEqual(metrics["findings_urls_not_in_source_register"], 0)
        self.assertEqual(result["warning_count"], 2)

    def test_duplicate_research_ids_and_duplicate_source_urls_detected(self):
        research = [{"Research ID": "RES-1", "Source URL": "https://example.com/a"}, {"Research ID": "res-1", "Source URL": "https://example.com/b"}]
        register = [{"Source ID": "SRC-1", "Source URL": "https://example.com/a", "Related Research IDs": "RES-1"}, {"Source ID": "SRC-2", "Source URL": "https://example.com/a/", "Related Research IDs": "RES-1"}]
        result = audit_evidence_integrity(research, register)
        self.assertEqual(result["metrics"]["duplicate_research_ids"], 1)
        self.assertEqual(result["metrics"]["duplicate_source_register_urls"], 1)

    def test_research_url_not_registered_and_source_id_mismatch(self):
        research = [{"Research ID": "RES-1", "Source ID": "SRC-WRONG", "Source URL": "https://example.com/a"}, {"Research ID": "RES-2", "Source ID": "", "Source URL": "https://example.com/b"}]
        register = [{"Source ID": "SRC-1", "Source URL": "https://example.com/a", "Related Research IDs": "RES-1"}]
        result = audit_evidence_integrity(research, register)
        metrics = result["metrics"]
        self.assertEqual(metrics["findings_source_id_mismatch"], 1)
        self.assertEqual(metrics["findings_urls_not_in_source_register"], 1)
        self.assertEqual(metrics["findings_missing_source_id"], 0)

    def test_register_link_mismatch_and_unknown_references_are_flagged(self):
        research = [{"Research ID": "RES-1", "Source ID": "SRC-1", "Source URL": "https://example.com/a"}]
        register = [{"Source ID": "SRC-1", "Source URL": "https://example.com/a", "Related Research IDs": "RES-1, RES-GHOST"}, {"Source ID": "SRC-2", "Source URL": "https://example.com/unused", "Related Research IDs": ""}, {"Source ID": "SRC-1", "Source URL": "https://example.com/other", "Related Research IDs": "RES-1"}]
        opportunities = [{"Opportunity ID": "OP-1", "Related Research IDs": "RES-1, RES-GHOST", "Supporting Source URLs": "https://example.com/ghost"}]
        result = audit_evidence_integrity(research, register, opportunities)
        metrics = result["metrics"]
        self.assertEqual(metrics["source_register_unknown_research_ids"], 1)
        self.assertEqual(metrics["source_register_unlinked"], 1)
        self.assertEqual(metrics["source_register_link_mismatch"], 1)
        self.assertEqual(metrics["duplicate_source_ids"], 1)
        self.assertEqual(metrics["opportunity_unknown_research_ids"], 1)
        self.assertEqual(metrics["opportunity_urls_not_in_source_register"], 1)
        self.assertEqual(metrics["opportunity_research_source_mismatch"], 1)
        self.assertGreater(result["info_count"], 0)

    def test_source_register_missing_and_invalid_urls(self):
        result = audit_evidence_integrity([], [{"Source ID": "S1", "Source URL": ""}, {"Source ID": "S2", "Source URL": "ftp://example.com/a"}])
        self.assertEqual(result["metrics"]["source_register_missing_urls"], 1)
        self.assertEqual(result["metrics"]["source_register_invalid_urls"], 1)

    def test_missing_source_id_on_registered_finding(self):
        research = [{"Research ID": "RES-1", "Source ID": "", "Source URL": "https://example.com/a"}]
        register = [{"Source ID": "SRC-1", "Source URL": "https://example.com/a", "Related Research IDs": "RES-1"}]
        result = audit_evidence_integrity(research, register)
        self.assertEqual(result["metrics"]["findings_missing_source_id"], 1)

    def test_dataframe_like_inputs_are_supported(self):
        class FrameLike:
            def to_dict(self, orient):
                if orient != "records":
                    raise AssertionError("records orientation required")
                return [{"Research ID": "RES-1", "Source URL": "https://example.com/a"}]
        result = audit_evidence_integrity(FrameLike(), [], [])
        self.assertEqual(result["warning_count"], 1)

    def test_detail_list_is_capped(self):
        rows = [{"Research ID": f"RES-{i}", "Source URL": f"https://example.com/{i}"} for i in range(60)]
        result = audit_evidence_integrity(rows, [])
        self.assertEqual(len(result["issues"]), 50)
        self.assertTrue(result["details_truncated"])
        self.assertGreater(result["total_issue_details"], 50)

    def test_commas_inside_single_source_url_are_preserved(self):
        url = "https://example.com/report?q=one,two"
        research = [{"Research ID": "RES-1", "Source ID": "SRC-1", "Source URL": url}]
        register = [{"Source ID": "SRC-1", "Source URL": url, "Related Research IDs": "RES-1"}]
        opportunities = [{"Opportunity ID": "OP-1", "Related Research IDs": "RES-1", "Supporting Source URLs": url}]
        result = audit_evidence_integrity(research, register, opportunities)
        self.assertEqual(result["warning_count"], 0)

    def test_multiple_urls_split_at_url_boundaries(self):
        url_a = "https://example.com/a"
        url_b = "https://example.com/b"
        research = [
            {"Research ID": "RES-1", "Source ID": "SRC-1", "Source URL": url_a},
            {"Research ID": "RES-2", "Source ID": "SRC-2", "Source URL": url_b},
        ]
        register = [
            {"Source ID": "SRC-1", "Source URL": url_a, "Related Research IDs": "RES-1"},
            {"Source ID": "SRC-2", "Source URL": url_b, "Related Research IDs": "RES-2"},
        ]
        opportunity = [{"Opportunity ID": "OP-1", "Related Research IDs": "RES-1, RES-2", "Supporting Source URLs": f"{url_a}, {url_b}"}]
        result = audit_evidence_integrity(research, register, opportunity)
        self.assertEqual(result["warning_count"], 0)

    def test_public_url_validation_rejects_local_and_private_hosts(self):
        rows = [
            {"Research ID": "R-LOCAL", "Source URL": "http://localhost/report"},
            {"Research ID": "R-LOOPBACK", "Source URL": "http://127.0.0.1/report"},
            {"Research ID": "R-PRIVATE", "Source URL": "http://192.168.1.20/report"},
            {"Research ID": "R-INTRANET", "Source URL": "http://intranet/report"},
            {"Research ID": "R-IPV6", "Source URL": "http://[::1]/report"},
            {"Research ID": "R-PUBLIC", "Source URL": "https://example.com/report"},
            {"Research ID": "R-PUBLIC-IP", "Source URL": "http://8.8.8.8/report"},
        ]
        result = audit_evidence_integrity(rows, [])
        self.assertEqual(result["metrics"]["findings_invalid_source_url"], 5)

    def test_duplicate_source_ids_are_detected_even_for_same_url(self):
        url = "https://example.com/report"
        research = [{"Research ID": "RES-1", "Source URL": url}]
        register = [
            {"Source ID": "SRC-1", "Source URL": url, "Related Research IDs": "RES-1"},
            {"Source ID": "src-1", "Source URL": url, "Related Research IDs": "RES-1"},
        ]
        result = audit_evidence_integrity(research, register)
        self.assertEqual(result["metrics"]["duplicate_source_ids"], 1)
        self.assertEqual(result["metrics"]["duplicate_source_register_urls"], 1)

    def test_public_ipv6_url_key_keeps_brackets(self):
        url = "https://[2606:4700:4700::1111]/report"
        self.assertEqual(_url_key(url), url)

    def test_empty_inputs_are_safe(self):
        result = audit_evidence_integrity(None, None, None)
        self.assertEqual(result["warning_count"], 0)
        self.assertEqual(result["info_count"], 0)
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()

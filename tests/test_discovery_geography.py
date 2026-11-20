import unittest

from workforce_intelligence.discovery import discover_sources


class FakeResponse:
    def __init__(self, url):
        self.url = url

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": [{
            "url": self.url,
            "title": "Workforce report",
            "content": "Public workforce research",
            "score": 0.9,
            "published_date": "2026-10-01",
        }]}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append(json)
        index = len(self.calls)
        return FakeResponse(f"https://example{index}.org/report")


class MultiCountryDiscoveryTests(unittest.TestCase):
    def test_comma_separated_countries_create_targeted_searches(self):
        session = FakeSession()
        results = discover_sources(
            ["Manufacturing"], api_key="test-key",
            country="India, Germany", max_results=1, session=session,
        )
        self.assertEqual(len(session.calls), 4)  # web + LinkedIn for each country
        self.assertEqual({row["country_searched"] for row in results}, {"India", "Germany"})


if __name__ == "__main__":
    unittest.main()

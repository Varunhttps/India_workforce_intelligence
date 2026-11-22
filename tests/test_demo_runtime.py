"""Runtime smoke test for the credential-free offline Streamlit demo."""
from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class OfflineDemoRuntimeSmokeTests(unittest.TestCase):
    def test_demo_renders_without_runtime_exceptions(self):
        demo_path = Path(__file__).resolve().parents[1] / "frontend" / "demo.py"
        app = AppTest.from_file(str(demo_path)).run()
        self.assertEqual(
            len(app.exception),
            0,
            "Offline demo should execute without Streamlit runtime errors: "
            + "; ".join(str(exc) for exc in app.exception),
        )


if __name__ == "__main__":
    unittest.main()

import ast
import unittest
from pathlib import Path

from frontend.private_access import (
    REQUIRED_AUTH_KEYS,
    is_email_allowed,
    missing_auth_keys,
    parse_allowed_emails,
)


class PrivateAccessConfigTests(unittest.TestCase):
    def test_allowlist_normalizes_case_and_whitespace(self):
        self.assertEqual(
            parse_allowed_emails([" Owner@example.com ", "MANAGER@example.com", ""]),
            {"owner@example.com", "manager@example.com"},
        )
        self.assertEqual(
            parse_allowed_emails("Owner@example.com, manager@example.com ,"),
            {"owner@example.com", "manager@example.com"},
        )

    def test_missing_or_invalid_allowlist_fails_closed(self):
        for configured in (None, 123, [], "", " , "):
            with self.subTest(configured=configured):
                self.assertEqual(parse_allowed_emails(configured), set())

    def test_missing_oidc_keys_are_reported(self):
        self.assertEqual(
            missing_auth_keys({"client_id": "id"}),
            sorted(REQUIRED_AUTH_KEYS - {"client_id"}),
        )
        self.assertEqual(missing_auth_keys(None), sorted(REQUIRED_AUTH_KEYS))

    def test_complete_oidc_config_has_no_missing_keys(self):
        self.assertEqual(missing_auth_keys({key: "configured" for key in REQUIRED_AUTH_KEYS}), [])

    def test_allowlist_requires_exact_email_match(self):
        allowed = parse_allowed_emails(["Manager@example.com"])
        self.assertTrue(is_email_allowed(" manager@EXAMPLE.com ", allowed))
        self.assertFalse(is_email_allowed("manager2@example.com", allowed))
        self.assertFalse(is_email_allowed("", allowed))
        self.assertFalse(is_email_allowed(None, allowed))

    def test_dashboard_auth_gate_is_unconditional_and_has_no_env_bypass(self):
        app_path = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(app_path))
        self.assertNotIn("REQUIRE_AUTH", source)
        self.assertTrue(
            any(
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "_require_auth"
                for node in tree.body
            ),
            "The private-access gate must be called at module startup.",
        )


if __name__ == "__main__":
    unittest.main()

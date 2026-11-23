# Deployment readiness checklist

## Streamlit configuration
- [ ] Deploy from the repository root and use `streamlit run frontend/app.py` as the app entry point.
- [ ] Add `GOOGLE_SHEET_ID` for the workbook that contains the six dashboard tabs.
- [ ] Add `GOOGLE_SERVICE_ACCOUNT_JSON` as a secret; share the spreadsheet with the service-account email.
- [ ] Add `ALLOWED_EMAILS` as a comma-separated list of approved Google sign-in email addresses.
- [ ] Configure Streamlit Google OIDC sign-in using the app's `st.login("google")` flow and `[auth]` settings.
- [ ] Add `GITHUB_TOKEN` only if users should be allowed to dispatch research runs from the dashboard. Restrict it to the repository and Actions workflow dispatch permission where possible.

## Research workflow
- [ ] Verify GitHub Actions secrets for research providers and Sheets publication are configured.
- [ ] Run a manual workflow dispatch in `manufacturing`, `other_industries`, and `all_industries` modes.
- [ ] Verify the workbook refresh and persistent history update.
- [ ] Confirm source links, country attribution, weekly trend tables, and opportunity tabs update correctly.

## Security

- [ ] Review the public-source collector's URL validation before public deployment. The security PR adds IP-pinned HTTP(S) connections after validating all DNS answers, disables environment proxies, rejects explicit proxies, and revalidates every redirect. This mitigates DNS-rebinding SSRF, but external integration behavior still requires CI and security review; keep the research-triggering app behind the configured allowlist and do not expose it as an unrestricted public service.
- [ ] Keep real secrets out of repository files and commit history.
- [ ] Confirm the hosted dashboard always enforces Google OIDC plus a non-empty allowlist; no `REQUIRE_AUTH` bypass is supported. Use `frontend/demo.py` for offline no-login presentations.
- [ ] Review the allowlist before inviting users.
- [ ] Do not expose the research dispatch token to client-side code or logs.
- [ ] Rotate credentials if they are ever committed or exposed.

## Release smoke test
- [ ] Verify the Research run health panel shows the latest run and freshness, and gracefully reports unavailable status if the GitHub API is rate-limited or unreachable.
- [ ] CI tests pass on the release commit.
- [ ] Dashboard imports/AST smoke test passes, including Streamlit authentication API version compatibility.
- [ ] Sign-in and allowlist behavior tested with an approved and an unapproved account.
- [ ] Empty/unconfigured data states render safely.
- [ ] Research dispatch reports failure clearly and links to GitHub Actions.
- [ ] No PR is merged unless CI is green and the change is safe.
- [ ] Verify the actual hosted URL, HTTPS, access gate and allowlist before sharing it.
- [ ] Verify app can read the configured Google Sheet without exposing service-account credentials.
- [ ] Verify the research-dispatch token has only required repository/Actions permissions and can be revoked.

## Known limitations
- Workforce signal rankings are heuristic screening aids, not validated labor-market estimates.
- Country attribution is included only when supported by source text.
- Weekly evidence volume reflects research coverage, not necessarily changes in workforce severity.

## Demo readiness
- [ ] Prepare a small, representative dataset with clearly attributed public sources; do not use fabricated findings as if they were real.
- [ ] Test the dashboard with a full dataset, empty sheets, missing optional columns, and a stale-data scenario.
- [ ] Confirm all charts and tables have understandable labels and that heuristics are visibly described as signals, not verified severity.
- [ ] Create a short demo walkthrough: research scope selection → source register → findings → weekly changes → country/skill coverage → manager actions → caveats.
- [ ] Keep a demo account and spreadsheet separate from personal or production data.
- [ ] Record the date/time of the latest successful research run and refresh before presenting.

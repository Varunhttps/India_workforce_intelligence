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
- [ ] Keep real secrets out of repository files and commit history.
- [ ] Leave authentication enabled for hosted deployment (`REQUIRE_AUTH=true`).
- [ ] Review the allowlist before inviting users.
- [ ] Do not expose the research dispatch token to client-side code or logs.
- [ ] Rotate credentials if they are ever committed or exposed.

## Release smoke test
- [ ] CI tests pass on the release commit.
- [ ] Dashboard imports/AST smoke test passes.
- [ ] Sign-in and allowlist behavior tested with an approved and an unapproved account.
- [ ] Empty/unconfigured data states render safely.
- [ ] Research dispatch reports failure clearly and links to GitHub Actions.
- [ ] No PR is merged without explicit owner approval.

## Known limitations
- Workforce signal rankings are heuristic screening aids, not validated labor-market estimates.
- Country attribution is included only when supported by source text.
- Weekly evidence volume reflects research coverage, not necessarily changes in workforce severity.

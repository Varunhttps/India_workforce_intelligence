# Streamlit Cloud deployment guide

This repository is prepared for a private hosted dashboard, but the hosting account,
OAuth credentials, spreadsheet credentials, and allowlisted users must be supplied by
the owner. Do not deploy with authentication disabled.

## 1. Create the app

1. Sign in to Streamlit Community Cloud and connect your GitHub account.
2. Choose **New app** and select this repository.
3. Set branch to `main`.
4. Set the app file to `frontend/app.py` (not `frontend/demo.py`).
5. Deploy. The initial boot may show a configuration message until secrets are entered.

## 2. Configure secrets

In the Streamlit app settings, open **Secrets** and add the following TOML. Replace
all placeholders. Keep this configuration in Streamlit's secret store only; do
not commit it.

```toml
ALLOWED_EMAILS = ["your-google-account@example.com"]
GOOGLE_SHEET_ID = "YOUR_SPREADSHEET_ID"
GOOGLE_SERVICE_ACCOUNT_JSON = '{"type":"service_account", ...}'
# Optional: only if dashboard users should trigger research runs:
GITHUB_TOKEN = "YOUR_RESTRICTED_TOKEN"

[auth]
redirect_uri = "https://YOUR-APP-NAME.streamlit.app"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "YOUR_GOOGLE_OAUTH_CLIENT_ID"
client_secret = "YOUR_GOOGLE_OAUTH_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

For the service-account JSON, paste the entire JSON as a single quoted string as
shown in `.streamlit/secrets.toml.example`. Share the target spreadsheet with
the service-account email as Editor. Verify the spreadsheet contains the six tabs
listed in the app's `SHEET_NAMES`.

## 3. Configure Google OAuth

1. In Google Cloud Console, create/select the project and configure the OAuth consent
   screen (use the appropriate user type for your account setup).
2. Create an OAuth client of type **Web application**.
3. Add the Streamlit app's exact hosted URL to **Authorized JavaScript origins**.
4. Add the same URL plus `/oauth2callback` to **Authorized redirect URIs**.
5. Copy the OAuth Client ID and Client Secret into the `[auth]` section above.
6. After Streamlit assigns the final app URL, update `redirect_uri` and the Google
   OAuth redirect URI to match exactly; then reboot/redeploy the app.

## 4. Keep access private

- `ALLOWED_EMAILS` must list only intended accounts, in lowercase.
- Keep authentication enabled; do not set `REQUIRE_AUTH=false* in hosted settings.
- Do not commit `secrets.toml`, service-account keys, OAuth client secrets, or tokens.
- Prefer no `GITHUB_TOKEN` unless dashboard-triggered research is needed. If enabled,
  use a fine-grained token scoped to this repository with only Actions workflow
  dispatch permission. Never paste it into the repository or browser-visible code.
- The research dispatcher can trigger external research and writes to the workbook;
  keep this capability restricted to trusted users.

## 5. Verify the release

Before sharing the hosted link:

- Test sign-in with an allowlisted Google account.
- Test an unallowlisted account and confirm it is blocked.
- Confirm the dashboard reads the intended spreadsheet and all six tabs.
- Confirm empty-sheet and missing-data states are understandable.
- Confirm the research button is absent/disabled if no restricted token is configured,
  and if configured, dispatch a controlled manual run and verify the workflow status.
- Check HTTPS, app logs, and the visible app URL.
- Review the final allowlist and rotate any credential that was exposed.

## Current deployment blocker

Hosting creation, OAuth client creation, and private credentials require actions in the
owner's Streamlit/Google accounts. These cannot safely be completed from repository
access alone. The app must remain private until those owner-side steps are done.

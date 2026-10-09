# Softreg stock monitor

Reads all publicly listed products in the Gmail Softreg category and each product's vendor list. It does not sign in, purchase accounts, or change listings. Uses Python 3.12 and Playwright Chromium; no paid API or AI service.

## Run

`pip install -r requirements.txt`

`python -m playwright install chromium`

`python monitor.py`

Observations are keyed by product ID and partner ID. `state/latest.json` holds the latest complete baseline; `state/report.json` holds the latest comparison and errors; `state/history.jsonl` retains comparisons. Missing/error responses never count as zero stock. A stock decrease does not prove a sale. The catalog can change during a scan, so observations are not an atomic snapshot.

## GitHub deployment

1. Create a public repository and upload these files, preserving `.github/workflows/monitor.yml`.
2. Enable Actions and run **Softreg stock monitor → Run workflow** to verify cloud access.
3. After the cloud test succeeds, enable a schedule requesting runs at minute 7 and 37 every hour, including while your computer is off. GitHub can delay or skip scheduled jobs; it does not guarantee exact 30-minute intervals.
4. Use only standard Ubuntu runners. Public-repository standard runner compute is free under current GitHub pricing. This workflow uses no paid APIs, artifacts, or caches. Review GitHub's current terms and pricing before enabling.
5. All code, stored public-market observations, and run logs in this public repository are public. Do not add credentials or private business data.
6. Reports are stored in GitHub; this version has no Telegram integration. Enable GitHub Actions failure notifications for failures. An additional notification channel must be configured for stock-change alerts.

GitHub may disable scheduled workflows in inactive public repositories after 60 days. Verify scheduled runs periodically. The local test does not establish that AccsMarket will allow GitHub-hosted requests. If access fails, the run must be investigated; it must not bypass a CAPTCHA or other access restriction.

Sources: https://docs.github.com/en/billing/concepts/product-billing/github-actions and https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

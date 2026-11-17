# Shopee Affiliate → Threads Posting Agent

An end-to-end automated agent that generates product ideas, fetches high-converting Malaysian Shopee products (with affiliate links), writes authentic Bahasa Melayu / Manglish Threads copy, and publishes the post + affiliate link reply via the **Meta Threads Graph API** — all orchestrated by **LangGraph** and running on **GitHub Actions**.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        LangGraph Pipeline                     │
│                                                              │
│  idea_generator → shopee_fetcher → copywriter → guardrail    │
│        (niche)      (product)        (copy)    (validate)    │
│                                                │ pass │ fail │
│                                                ▼      ▼      │
│                                      threads_publisher ← retry│
│                                                │             │
│                                          history_logger       │
└──────────────────────────────────────────────────────────────┘
```

## Project Structure

```
posting-agent/
├── .github/workflows/
│   ├── autopost.yml          # Scheduled & manual posting trigger
│   └── refresh_token.yml     # 45-day Threads token refresh
├── data/
│   └── posted_history.json   # Tracks posted items (prevents duplicates)
├── src/
│   ├── __init__.py
│   ├── state.py              # LangGraph state definition
│   ├── nodes.py              # All pipeline nodes
│   ├── graph.py              # StateGraph wiring & compilation
│   └── tools/
│       ├── __init__.py
│       ├── shopee_client.py  # Shopee Open API + Tavily fallback
│       └── threads_client.py # Meta Threads Graph API client
├── main.py                   # Entrypoint (supports --dry-run)
├── requirements.txt
├── .env.example
└── README.md
```

## Prerequisites

- Python 3.11+
- A GitHub repository (this project is already linked to one)
- A Meta (Facebook) Developer account
- A Shopee Affiliate Malaysia account
- A Google AI Studio API key (Gemini)
- A Tavily API key

---

## 🛠️ Complete Setup Guide

Follow these steps in order. Every manual configuration, credential, and permission is listed below.

### Step 1 — Meta Developer & Threads API

1. **Create a Meta App**
   - Go to [developers.facebook.com](https://developers.facebook.com) and log in.
   - Click **My Apps → Create App**.
   - Choose **Business** type (or "Other" → "None" if you don't have a business).
   - Name it (e.g., `threads-poster`) and click **Create**.

2. **Add the Threads API use case**
   - In your app, go to **App Settings → Add Use Case** (or "Add Product").
   - Select **Threads API** and click **Set up**.
   - This adds the `threads_basic`, `threads_content_publish`, and `threads_manage_replies` permissions.

3. **Add your Threads account as a tester**
   - Go to **App Roles → Roles**.
   - Under **Threads Accounts**, add your Threads handle (e.g., `@yourhandle`).
   - Accept the invitation from your Threads account notification.

4. **Get your `THREADS_USER_ID`**
   - Go to **App Settings → Threads API**.
   - Find your Threads account and copy its **ID** (a numeric string like `12345678901234567`).
   - Alternatively, call: `https://graph.threads.net/v1.0/me?fields=id,username&access_token=TOKEN`.

5. **Obtain the 60-day `THREADS_ACCESS_TOKEN`**
   - Generate a short-lived token via **App Settings → Threads API → Generate token**.
   - Exchange it for a long-lived (60-day) token:
     ```
     GET https://graph.threads.net/access_token?
       grant_type=th_exchange_token&
       client_secret=APP_SECRET&
       access_token=SHORT_LIVED_TOKEN
     ```
   - The response contains `access_token` (60-day) and `refresh_token`.
   - Save both.

6. **Verify permissions**
   - Call: `https://graph.threads.net/v1.0/{THREADS_USER_ID}?fields=id,username,threads_basic,threads_content_publish,threads_manage_replies&access_token=TOKEN`.
   - Confirm all three permission fields return `true`.

### Step 2 — Shopee Affiliate Portal

1. Go to the **Shopee Affiliate Malaysia** dashboard: [affiliate.shopee.com.my](https://affiliate.shopee.com.my).
2. Log in and apply for **Open API access** under **API & Integration** (approval can take a few days).
3. Once approved, find your credentials:
   - **App ID** (`SHOPEE_APP_ID`)
   - **App Secret** (`SHOPEE_APP_SECRET`)
4. If approval is **pending**, the system automatically falls back to **Tavily Search** mode (`site:shopee.com.my`) + the `AFFILIATE_LINK_TEMPLATE` wrapper — so you can still test end-to-end.

### Step 3 — LLM & Search Keys

- **Gemini**: Get a `GEMINI_API_KEY` from [aistudio.google.com](https://aistudio.google.com) → "Get API Key".
- **Tavily**: Sign up at [tavily.com](https://tavily.com) and copy your `TAVILY_API_KEY`.

### Step 4 — GitHub Repository Settings

1. **Enable read/write workflow permissions**
   - Go to **Settings → Actions → General → Workflow permissions**.
   - Select **Read and write permissions**.
   - This lets the bot auto-commit `data/posted_history.json`.

2. **Add GitHub Actions Secrets**
   - Go to **Settings → Secrets and variables → Actions → New repository secret**.
   - Add each of these:

   | Secret Name | Value |
   |---|---|
   | `THREADS_USER_ID` | Your Threads numeric user ID |
   | `THREADS_ACCESS_TOKEN` | 60-day token from Step 1.5 |
   | `THREADS_REFRESH_TOKEN` | Refresh token (optional; kept for reference) |
   | `SHOPEE_APP_ID` | Shopee Open API App ID |
   | `SHOPEE_APP_SECRET` | Shopee Open API App Secret |
   | `GEMINI_API_KEY` | Gemini API key |
   | `TAVILY_API_KEY` | Tavily API key |
   | `AFFILIATE_LINK_TEMPLATE` | (optional) e.g. `https://shopee.com.my/product/affiliate/{item_id}` |
   | `GH_PAT` | Fine-grained PAT with Secrets write (see below) |

3. **Generate a `GH_PAT` (Fine-grained Personal Access Token)**
   - Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   - Repository access: **Only select repositories** → choose this repo.
   - Permissions:
     - **Actions** → Read and write (optional, for triggering workflows)
     - **Contents** → Read and write (so the bot can commit history)
     - **Secrets** → Read and write (**required** for `gh secret set`)
   - Generate and copy the token into the `GH_PAT` secret.

### Step 5 — Testing Instructions

1. **Local dry-run** (recommended first):
   ```bash
   cd D:\personal-project\posting-agent
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   pip install -r requirements.txt
   copy .env.example .env        # then fill in GEMINI_API_KEY + TAVILY_API_KEY
   python main.py --dry-run
   ```
   This runs the full pipeline (idea → fetch → copy → guardrail) and prints the exact main post, reply post, image URL, and product details — **without** publishing or modifying history.

2. **Manual GitHub trigger**:
   - Go to **Actions → Auto Post to Threads → Run workflow**.
   - Set `dry_run` to `true` to test, or leave `false` to publish for real.

3. **Scheduled runs**:
   - `autopost.yml` runs at **12:30 PM MYT** and **8:30 PM MYT** daily.
   - `refresh_token.yml` runs every **45 days** to refresh the Threads token.

## Local Development Notes

- All external API calls are wrapped with clear error handling and logging.
- The pipeline auto-skip posted `item_id`s by reading `data/posted_history.json`.
- `--dry-run` never writes to history, so you can test repeatedly.

## License

MIT

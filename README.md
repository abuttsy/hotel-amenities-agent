# Hotel Facilities Notion Sync

This suite automates the synchronization of facilities between a "Facilities" database and a "View all hotels" database in Notion by scraping hotel websites.

## Setup Instructions

### 1. Environment Variables
The following environment variables are **required** for the script and server to run. You must set these in your hosting provider's dashboard (e.g., Railway Variables or Render Env Vars).

| Variable | Description |
| --- | --- |
| `NOTION_TOKEN` | Your Notion Integration Token |
| `HOTELS_DB_ID` | The ID of the "View all hotels" database |
| `FACILITIES_DB_ID` | The ID of the "Facilities" database |
| `EMAIL_PASSWORD` | Gmail App Password for `ultimatefamilyhotels@gmail.com` |

### 2. Deployment

#### Option A: Railway (Fastest)
1. Connect your repo to Railway.
2. The `Procfile` will automatically define two services:
   - `web`: The FastAPI worker for the Notion Agent.
   - `worker`: The batch synchronization script.
3. **Important**: Go to the "Variables" tab in Railway and add the 4 variables listed above.

#### Option B: Render
1. Connect your repo to Render.
2. Create a **Web Service** for `worker_server.py`.
3. Create a **Background Worker** or **Cron Job** for `sync_hotel_facilities.py`.
4. Add the environment variables in the Render dashboard.

## Local Development
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the sync script:
   ```bash
   python3 sync_hotel_facilities.py
   ```
3. Run the worker server:
   ```bash
   python3 worker_server.py
   ```

## Tool Contract for Notion Agent
- **Discovery URL**: `https://<your-domain>/.well-known/notion-tools.json`
- **Tool Name**: `discover_facilities_for_hotel`
- **Input**: `website_url`, `facilities`
- **Output**: `matched_facilities`, `evidence`

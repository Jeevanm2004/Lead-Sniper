# The Lead Sniper (n8n Workflow Automation)

An automated high-value lead detection, enrichment, and AI pitch generation pipeline for GitHub repositories.

---

## 📁 Project Structure

```text
lead_sniper/
├── lead_sniper_workflow.json   # Ready-to-import n8n workflow file
├── LOGIC_LOG.md                # Rate-limit handling & architectural decisions
├── test_lead_sniper.py         # Local Python pipeline verifier / tester
├── screenshots/                # Verified execution proof & alert card
├── .env.example                # Example environment credentials
└── README.md                   # Setup and usage guide
```

---

## 🚀 How to Run the n8n Workflow

### Step 1: Open n8n
If you don't have n8n running, launch it directly in your terminal with one command:
```bash
npx n8n
```
Or open [n8n Cloud](https://app.n8n.cloud) in your browser.

Navigate to `http://localhost:5678`.

---

### Step 2: Import the Workflow
1. In the n8n web interface, click **Workflows** in the sidebar.
2. In the top-right corner, click the **`...`** (Options menu) $\rightarrow$ **Import from File**.
3. Select `lead_sniper_workflow.json` from this folder.
4. The complete visual pipeline will appear on your canvas!

---

### Step 3: Configure Your Variables
Double-click the **Config & Credentials** node (the 3rd box in the flow):
* `REPO_OWNER`: Target GitHub username/org (e.g., `fastapi`)
* `REPO_NAME`: Target repository name (e.g., `fastapi`)
* `GITHUB_TOKEN`: Your GitHub Personal Access Token (for 5,000 req/hr rate limit)
* `GEMINI_API_KEY`: Your Google Gemini API Key
* `DISCORD_WEBHOOK_URL`: Your Discord Webhook URL

Click **Save**.

---

### Step 4: Test & Verify
1. Click the big **"Test workflow"** button at the bottom of the screen.
2. Watch each node light up with a **green checkmark**:
   * It fetches recent stargazers from the target repository.
   * Enriches their profile (`/users/{username}`).
   * Evaluates the condition: `followers > 100 OR public_repos > 50`.
   * Calls Gemini to generate the 1-sentence sales pitch.
   * Sends the rich embed card straight to your Discord channel!

---

## 🧪 Optional: Run Local Python Simulator
You can also run the pipeline directly via terminal to verify your API credentials and Discord webhook:

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Add your GEMINI_API_KEY and DISCORD_WEBHOOK_URL to .env

# 3. Run the verifier
python3 test_lead_sniper.py
```

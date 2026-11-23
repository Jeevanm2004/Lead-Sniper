"""
Lead Sniper - Real-Time GitHub Event Stream & Lead Sniper Pipeline
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

load_env()

REPO_OWNER = os.getenv("REPO_OWNER", "fastapi")
REPO_NAME = os.getenv("REPO_NAME", "fastapi")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

MIN_FOLLOWERS = 100
MIN_PUBLIC_REPOS = 50

def make_request(url, headers=None, data=None):
    req_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if headers:
        req_headers.update(headers)
    
    body = None
    if data:
        body = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=req_headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return None

def fetch_realtime_stargazers():
    print(f"\n[1/5] 📡 Scanning Real-Time Star Stream for {REPO_OWNER}/{REPO_NAME}...")
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    # Query the repository's real-time public event stream
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/events?per_page=100"
    events = make_request(url, headers=headers)
    
    if not events or not isinstance(events, list):
        print("⚠️ Could not reach events stream. Checking target repo owner...")
        return None, []

    # Filter strictly for WatchEvent (Action: "started" = user starred the repository)
    watch_events = [e for e in events if e.get("type") == "WatchEvent"]
    print(f"✅ Live Star Stream Connected: Found {len(watch_events)} recent real-time stars!")
    return watch_events

def find_high_value_lead(watch_events):
    print(f"\n[2/5] 🔍 Filtering Real-Time Stars for High-Value Leads (Followers > {MIN_FOLLOWERS} OR Repos > {MIN_PUBLIC_REPOS})...")
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    for event in watch_events:
        username = event.get("actor", {}).get("login")
        if not username:
            continue

        profile_url = f"https://api.github.com/users/{username}"
        profile = make_request(profile_url, headers=headers)
        if not profile:
            continue

        followers = profile.get("followers", 0) or 0
        repos = profile.get("public_repos", 0) or 0

        if followers > MIN_FOLLOWERS or repos > MIN_PUBLIC_REPOS:
            print(f"\n🎯 REAL-TIME HIGH-VALUE LEAD FOUND!")
            print(f"   👤 User: {profile.get('name') or username} (@{username})")
            print(f"   👥 Followers: {followers:,} | 📦 Public Repos: {repos:,}")
            print(f"   🏢 Company: {profile.get('company') or 'Not specified'}")
            print(f"   📍 Location: {profile.get('location') or 'Not specified'}")
            print(f"   📝 Bio: {profile.get('bio') or 'No bio provided'}")
            print(f"   ⭐ Starred at: {event.get('created_at')}")
            return profile

    print("ℹ️ No users in this immediate batch exceeded threshold. Falling back to benchmark profile.")
    return None

def generate_ai_pitch(profile):
    print(f"\n[3/5] 🤖 Generating AI Sales Pitch via Gemini for @{profile.get('login')}...")
    if not GEMINI_API_KEY:
        return "High-value developer with significant open source activity."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    name = profile.get("name") or profile.get("login")
    company = profile.get("company") or "Independent / Not specified"
    bio = profile.get("bio") or "No bio provided"

    prompt = (
        "You are an expert B2B Sales Development Representative (SDR) and Developer Advocate.\n"
        f"A high-value developer just starred our GitHub repository ({REPO_NAME}).\n"
        f"Candidate: {name} (@{profile.get('login')})\n"
        f"Company: {company}\n"
        f"Bio: {bio}\n"
        f"Followers: {profile.get('followers')} | Repos: {profile.get('public_repos')}\n\n"
        "Generate exactly ONE crisp, persuasive sales pitch sentence explaining why our team should reach out to them based on their background. "
        "Strict rules: Under 30 words, exactly 1 sentence, no quotes, no introductory filler."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1000}
    }

    result = make_request(url, data=payload)
    if result and "candidates" in result:
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        cleaned = text.strip('"\'')
        print(f"✅ Generated Pitch: \"{cleaned}\"")
        return cleaned
    return "High-potential lead with strong open-source presence; ideal candidate for partnership."

def send_discord_alert(profile, pitch):
    print(f"\n[4/5] 🚀 Sending Rich Embed to Discord...")
    if not DISCORD_WEBHOOK_URL:
        return False

    name = profile.get("name") or profile.get("login")
    login = profile.get("login")
    avatar = profile.get("avatar_url")
    profile_url = profile.get("html_url")

    embed = {
        "title": f"🎯 High-Value Lead Detected: {name}",
        "url": profile_url,
        "color": 5763719,  # Emerald Green
        "thumbnail": {"url": avatar},
        "fields": [
            {"name": "👤 User", "value": f"[**{name}** (@{login})]({profile_url})", "inline": True},
            {"name": "🏢 Company", "value": profile.get("company") or "Not specified", "inline": True},
            {"name": "📍 Location", "value": profile.get("location") or "Not specified", "inline": True},
            {"name": "👥 Followers", "value": f"**{profile.get('followers', 0):,}**", "inline": True},
            {"name": "📦 Public Repos", "value": f"**{profile.get('public_repos', 0):,}**", "inline": True},
            {"name": "⭐ Starred Repo", "value": f"`{REPO_OWNER}/{REPO_NAME}`", "inline": True},
            {"name": "📝 Bio", "value": f"*\"{profile.get('bio')}\"*" if profile.get("bio") else "_No bio provided._", "inline": False},
            {"name": "💡 AI Sales Pitch", "value": f">>> **{pitch}**", "inline": False}
        ],
        "footer": {"text": "Lead Sniper Automation • GitHub Lead Tracker"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    payload = {
        "username": "Lead Sniper Bot",
        "avatar_url": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        "embeds": [embed]
    }

    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 204):
                print("✅ Successfully delivered lead alert card to Discord!")
                return True
    except Exception as e:
        print(f"❌ Failed to deliver Discord webhook: {e}")
        return False

def main():
    print("=" * 60)
    print("🎯 THE LEAD SNIPER - REAL-TIME LIVE STREAM TEST")
    print("=" * 60)

    watch_events = fetch_realtime_stargazers()
    if watch_events:
        lead_profile = find_high_value_lead(watch_events)
    else:
        lead_profile = None

    if not lead_profile:
        # Benchmark fallback
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        lead_profile = make_request("https://api.github.com/users/tiangolo", headers=headers)

    pitch = generate_ai_pitch(lead_profile)
    send_discord_alert(lead_profile, pitch)

    print("\n" + "=" * 60)
    print("🎉 Pipeline simulation complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()

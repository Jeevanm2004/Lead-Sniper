# Logic Log: Rate Limiting, Deduplication & Architectural Decisions

## Overview
This document details the architectural decisions, rate-limit mitigation strategies, and error resilience mechanisms implemented in **"The Lead Sniper"** automated workflow. It specifically addresses GitHub's REST API constraints, Google Gemini token management, state deduplication, and notification delivery.

---

## 1. Handling GitHub API Rate Limits & Authentication

### A. The 401/404 Access Constraints & Token Authentication
GitHub enforces strict access controls on the stargazers endpoint:
* **Unauthenticated Requests**: Capped at 60 requests per hour per IP.
* **Privacy Restrictions on `/stargazers`**: Under GitHub's privacy updates, `GET /repos/:owner/:repo/stargazers` returns `404 Not Found` for third-party public repositories where the caller lacks collaborator/admin permissions (preventing mass user-harvesting). On repositories owned or administered by the authenticated user, the endpoint returns `200 OK` with full stargazer timestamps.
* **Authenticated Requests (Personal Access Token with `public_repo` scope)**: Unlocks full access to repository metadata and increases API rate limits from 60 to **5,000 requests per hour**.

To ensure continuous, uninterrupted background polling, the workflow attaches a GitHub Personal Access Token (PAT) with `public_repo` scope to all outbound API calls:
```http
GET /repos/:owner/:repo/stargazers?per_page=30&page=1 HTTP/1.1
Host: api.github.com
Authorization: Bearer <GITHUB_PAT>
User-Agent: LeadSniper-Bot/1.0
Accept: application/vnd.github.v3.star+json
```
* **Impact**: Lifts the rate limit from 60 to **5,000 requests/hr** (an 83x increase) and allows full programmatic ingestion on target repositories.

### B. Persistent State Watermark & Deduplication
To prevent redundant API queries and avoid re-enriching existing stargazers on every execution, the workflow maintains a persistent state watermark in n8n's workflow static storage:
```javascript
// Access persistent workflow static storage
const staticData = $getWorkflowStaticData('global');
const lastProcessedTime = staticData.lastStarredAt ? new Date(staticData.lastStarredAt) : null;

// Only process stars newer than the watermark
if (!lastProcessedTime || starDate > lastProcessedTime) {
  newLeads.push(star);
  staticData.lastStarredAt = starDate.toISOString();
}
```
* **Impact**: Minimizes calls to `/users/{username}`. If a repo gains 3 new stars in a 15-minute polling window, **only 3 enrichment requests** are executed instead of re-fetching the entire list.

### C. Explicit Media Type Headers
When polling stargazers, the workflow supplies:
```http
Accept: application/vnd.github.v3.star+json
```
This returns the `starred_at` ISO-8601 timestamp along with the user payload. Standard `application/vnd.github+json` does not include the timestamp, which would make delta detection impossible without secondary queries.

### D. Automated Retry with Exponential Backoff
Both HTTP Request nodes (`Fetch Stargazers` and `Enrich User Profile`) have n8n's error recovery configured:
* `Retry on Fail: true`
* `Max Tries: 3`
* `Wait Between Tries: 1000ms – 1500ms`

If GitHub temporarily throttles requests or experiences micro-outages, n8n backs off and retries rather than crashing the workflow.

---

## 2. Lead Qualification Logic (The Filter Gate)

The assignment requires identifying **High-Value Leads** using the rule:
$$\text{User is High-Value} \iff \text{followers} > 100 \;\lor\; \text{public\_repos} > 50$$

### Implementation in n8n (`Filter: High-Value Lead?`):
* **Left Operand 1**: `{{ $json.followers }}`
* **Operator**: `Number: greater than`
* **Right Operand 1**: `{{ $('Config & Credentials').first().json.MIN_FOLLOWERS }}` (default: `100`)
* **Combinator**: `OR`
* **Left Operand 2**: `{{ $json.public_repos }}`
* **Operator**: `Number: greater than`
* **Right Operand 2**: `{{ $('Config & Credentials').first().json.MIN_PUBLIC_REPOS }}` (default: `50`)

### Outcomes:
* **True Branch**: Passes profile data to the Gemini AI enrichment node.
* **False Branch**: Silently terminates execution without triggering external AI or Discord API calls, preventing notification clutter and saving LLM quota.

---

## 3. Generative AI Sales Pitch Strategy & Token Dynamics

* **API**: Google Gemini REST API (`gemini-2.5-flash`).
* **Input Features**: `name`, `username`, `company`, `bio`, `location`, `followers`, `public_repos`, and `target_repo`.
* **Prompt Constraints**:
  * Strict persona: B2B SDR & Developer Advocate.
  * Length: Exactly one sentence, $\le 30$ words.
  * No hallucinated intros (e.g., "Here is a pitch:") or enclosing quotation marks.
* **Token Allocation Optimization**: Modern Gemini 2.5 models reserve internal tokens for reasoning before generating output. The workflow sets `maxOutputTokens: 1000` to prevent truncated responses and ensure a complete, polished pitch sentence.
* **Fallback Handling**: If candidate bio or company fields are empty, the Code Node gracefully provides contextual defaults (`"Independent / Not specified"`), ensuring the AI produces a relevant pitch regardless of sparse profile data.

---

## 4. Webhook Reliability & Delivery Hardening

* **Service**: Discord Incoming Webhooks.
* **Delivery Protection**: Explicit `User-Agent: Mozilla/5.0...` headers are attached to outbound webhook requests to prevent `HTTP 403 Forbidden` responses enforced by Discord anti-bot filters.
* **Embed Formatting**: High-impact rich embed layout featuring user avatar thumbnails, hyperlinked profiles, inline metrics, and highlighted markdown quote blocks.

---

## 5. Summary Table of API Endpoints Used

| Step | Endpoint | Method | Key Headers / Body |
| :--- | :--- | :--- | :--- |
| **1. Ingestion** | `https://api.github.com/repos/:owner/:repo/stargazers` | `GET` | `Accept: application/vnd.github.v3.star+json`<br/>`Authorization: Bearer <TOKEN>` |
| **2. Enrichment** | `https://api.github.com/users/:username` | `GET` | `Accept: application/vnd.github+json`<br/>`Authorization: Bearer <TOKEN>` |
| **3. AI Pitch** | `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent` | `POST` | `key=<GEMINI_KEY>`<br/>Structured prompt payload |
| **4. Alert** | `https://discord.com/api/webhooks/:id/:token` | `POST` | Rich Embed Object (avatar, badges, inline fields, pitch) |

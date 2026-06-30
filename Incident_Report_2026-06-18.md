# Incident Report — Race & Run! WhatsApp Bot Outage
**Date of incident:** 2026-06-18
**Status:** Resolved (Twilio account upgraded mid-event)

## 1. Overview

During the live "Race & Run!" event on 2026-06-18, teams progressively stopped receiving messages from the WhatsApp bot, escalating from a single slow-response complaint to a complete outage affecting every team simultaneously. Root cause was a Twilio account-level daily messaging cap, compounded by a secondary media-fetch issue.

## 2. Timeline of Symptoms

| Stage | Symptom | 
|---|---|
| 1 | Individual teams reported station replies were slow to arrive after sending a correct answer. |
| 2 | Initial hypothesis (hosting cold-start) was ruled out — user confirmed the Render hosting plan was already paid, so the app was not spinning down between requests. |
| 3 | Alternative hypotheses considered: Twilio WhatsApp Sandbox rate-limiting, and/or blocking synchronous Twilio SDK calls inside the single-worker async server causing requests to queue when multiple teams texted at once. |
| 4 | Symptom escalated: **all teams** stopped receiving any messages at the same time — pointed to an account-wide failure rather than a per-team or server-load issue. |
| 5 | Twilio Console → Monitor → Logs → Messaging showed repeated errors clustered around 05:58–06:02 UTC on 2026-06-18. |

## 3. Root Causes Identified

### 3.1 Twilio Error 63038 — "Account exceeded the daily messages limit" (primary cause)
- Twilio blocks **all** further outbound messages account-wide once the daily/rolling-24-hour send cap is hit.
- This explains why every team lost messages at once rather than just one.
- Trial Twilio accounts are capped at 50 messages/day; the WhatsApp Sandbox additionally enforces its own stricter volume limits independent of account billing status, since Sandbox is intended for dev/testing rather than production-scale events.
- User believed the account was already upgraded out of trial — this needed direct verification in the Twilio Console (trial accounts still show an "Upgrade" banner if the upgrade was not fully completed).

### 3.2 Twilio Error 11200 — "HTTP retrieval failure" (secondary, related issue)
- Logged alongside the 63038 errors.
- Most likely cause: Twilio attempting to fetch a clue/chain station image (`clue_media_url` / `chain_media_url`) that no longer exists.
- Consistent with a previously identified issue: Render's ephemeral filesystem wipes uploaded station images on every redeploy unless a persistent disk is attached, so images uploaded before a redeploy return 404 when Twilio tries to fetch them.

## 4. Resolution

1. Verified Twilio account trial/upgrade status in the Console and completed the account upgrade (added/confirmed payment method) to lift the trial-tier daily cap.
2. Confirmed via a test send + Twilio message log that messages began delivering again post-upgrade.
3. Flagged that if 63038 recurred immediately after upgrading, that would indicate a Sandbox-specific cap (not trial-related) requiring a Twilio support-driven limit increase or migration off Sandbox to a verified WhatsApp Business sender.
4. For mid-event continuity while waiting on the fix, recommended a manual fallback (team leaders relaying clues via phone call/SMS, or a shared posted clue sheet) so the race could continue without depending on the bot.

## 5. Outstanding / Preventive Follow-ups

- **Sandbox is not production-grade.** For future events, migrate off the Twilio WhatsApp Sandbox to a registered WhatsApp Business sender to avoid both the 72-hour sandbox session expiry and Sandbox-specific volume caps. This requires Meta/WhatsApp approval and should be started well ahead of the next event, not during one.
- **Re-upload station images after every Render redeploy**, or attach a Render persistent disk, so `clue_media_url` / `chain_media_url` links don't silently 404 mid-event (root cause of the 11200 errors).
- **Confirm Twilio account tier before each event**, not just once — re-check the Console for any "Upgrade"/trial banner a day or two before race day.
- Consider whether the bot's per-team message volume (clue + station + hint + status + leaderboard, etc.) can be trimmed for large events, since total volume across many teams contributed to hitting the daily cap.

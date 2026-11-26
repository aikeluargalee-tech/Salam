# salam-trigger — start a Salam packet run without a GitHub login

A Cloudflare Worker that holds a GitHub token privately and exposes a plain URL you can call from
a phone, a laptop, a cloud browser (Gemini Task), or `curl`. No GitHub login, no token in the URL,
no page reload needed.

## Why this exists

```
GitHub's own cron      best-effort. Measured on this repo: 1 `schedule` run in ~12 hours
                       against a 4-hourly cron that should have produced 3.
A local cron           works, but only while the machine is awake — the log shows a two-hour
                       hole (11:37 → 13:37Z) where the PC was asleep.
A cloud browser        cannot log into github.com to press "Run workflow".
```

So the reliable trigger is something always-on that holds the credential on your behalf. That is
what this Worker is. It is free (100k requests/day on Cloudflare's free plan).

## What it does on a call

```
1. reads the published packet from raw.githubusercontent and computes its age
2. if the packet is already fresh (default ≤ 8 min)  → returns "no run needed", costs nothing
3. else if inside the cooldown                       → returns "cooldown", with retry_in_s
4. else POSTs to the workflow_dispatch API           → returns "run queued"
```

Every response is JSON and includes `packet_age_min`, so a caller can decide on its own.

## Deploy (one time, ~10 minutes)

```bash
# 1. install wrangler
npm i -g wrangler && wrangler login

# 2. create the KV namespace that holds the cooldown
cd infra/trigger-worker
wrangler kv namespace create SALAM_KV
#    copy the id it prints into wrangler.toml

# 3. create a FINE-GRained GitHub token — nothing more than this:
#    Settings → Developer settings → Personal access tokens → Fine-grained
#      Repository access:  Only select repositories → aikeluargalee-tech/Salam
#      Permissions:        Actions → Read and write      (that is the only one)
#      Expiry:             90 days
export GH_TOKEN=github_pat_xxx

# 4. store the two secrets
wrangler secret put GH_TOKEN
wrangler secret put TRIGGER_SECRET      # any long random string, e.g.  openssl rand -hex 24

# 5. deploy
wrangler deploy
#    → https://salam-trigger.<your-subdomain>.workers.dev
```

## Use

```bash
# private route (short cooldown) — you, your phone, Gemini Task
curl "https://salam-trigger.YOURS.workers.dev/s/YOUR_TRIGGER_SECRET"

# public route (5-minute cooldown) — safe to wire a button to, or share
curl "https://salam-trigger.YOURS.workers.dev/"
```

Typical answer when it fires:

```json
{
 "ok": true,
 "triggered": true,
 "packet_age_min": 47,
 "note": "run queued. The packet lands in ~40-90 s; raw.githubusercontent serves it within a few minutes and GitHub Pages within ~10. Poll the raw URL, not the Pages URL.",
 "raw": "https://raw.githubusercontent.com/aikeluargalee-tech/Salam/master/SALAM_DATA_HUB.json",
 "run": "https://github.com/aikeluargalee-tech/Salam/actions"
}
```

And when it declines:

```json
{ "ok": true, "triggered": false, "reason": "packet already fresh", "packet_age_min": 3, "retry_in_s": 0 }
```

## Notes

- **Poll `raw`, not Pages.** The Pages CDN serves a ~10-minute-old copy; `raw.githubusercontent`
  is a few minutes behind the repo and is what the dashboard itself reads.
- **Cooldowns are the abuse control.** 90 s private / 300 s public, plus the "already fresh"
  short-circuit, so a caller that hammers the endpoint cannot generate a run storm.
- **Rotate the token when it expires** (90 days): `wrangler secret put GH_TOKEN`.
- **Blast radius is one repo and one permission.** The token can dispatch workflows on Salam and
  do nothing else — it cannot read code, push commits, or touch another repository.

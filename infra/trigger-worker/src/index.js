/**
 * Salam packet trigger — a tiny Cloudflare Worker.
 *
 * Why this exists: GitHub's `schedule` cron is best-effort (this repo saw 1 run in 12 hours
 * against a 4-hourly cron), and a cloud browser cannot log into github.com to press "Run workflow".
 * This endpoint lets anything that can make a GET request — a browser, a phone, Gemini Task, a
 * curl in a shell — start a run, without ever holding a GitHub credential itself.
 *
 * Routes
 *   GET /s/<TRIGGER_SECRET>   private, short cooldown — for you and your tools
 *   GET /                     public, long cooldown — safe to put a button on a public page
 *
 * The GitHub token lives only in the Worker's secret store. It is never sent to the caller and
 * never appears in a URL.
 */

const RAW = 'https://raw.githubusercontent.com/%REPO%/master/SALAM_DATA_HUB.json';

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 1), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });
}

function cors(res) {
  const h = new Headers(res.headers);
  h.set('access-control-allow-origin', '*');
  h.set('access-control-allow-methods', 'GET, OPTIONS');
  h.set('access-control-allow-headers', 'content-type');
  return new Response(res.body, { status: res.status, headers: h });
}

/** Age of the published packet in minutes, or null when the mirror is unreachable. */
async function packetAgeMinutes(repo) {
  try {
    // Cloudflare's edge caches raw.githubusercontent responses, and `cacheTtl: 0` is not a valid
    // value (valid range starts at 1), so it was ignored and the Worker read a ~20-minute-old copy
    // while the page read the fresh one — the button then said "packet 21 min old" next to a badge
    // saying "0 min old". A unique query string defeats the edge cache; GitHub raw ignores it.
    const url = RAW.replace('%REPO%', repo) + '?cb=' + Date.now() + Math.random().toString(36).slice(2, 8);
    const r = await fetch(url, { cf: { cacheTtl: 1 } });
    if (!r.ok) return null;
    const j = await r.json();
    if (!j.generated_at_utc) return null;
    return Math.max(0, Math.round((Date.now() - Date.parse(j.generated_at_utc)) / 60000));
  } catch {
    return null;
  }
}

async function dispatch(env, ref) {
  const res = await fetch(
    `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
    {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'content-type': 'application/json',
        'user-agent': 'salam-trigger-worker',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify({ ref }),
    },
  );
  return { ok: res.status === 204, status: res.status, text: res.status === 204 ? '' : await res.text() };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'OPTIONS') return cors(new Response(null, { status: 204 }));
    if (request.method !== 'GET' && request.method !== 'POST') {
      return cors(json({ ok: false, error: 'GET only' }, 405));
    }

    const isPrivate = env.TRIGGER_SECRET && url.pathname === `/s/${env.TRIGGER_SECRET}`;
    const isPublic = url.pathname === '/' || url.pathname === '/trigger';
    if (!isPrivate && !isPublic) return cors(json({ ok: false, error: 'not found' }, 404));

    const cooldownS = Number(isPrivate ? env.COOLDOWN_S || 90 : env.PUBLIC_COOLDOWN_S || 300);
    const now = Date.now();
    const last = Number((await env.SALAM_KV.get('last_dispatch')) || 0);
    const age = await packetAgeMinutes(env.REPO);

    // A caller asking "is it already fresh?" should not pay for a run.
    const freshEnough = age !== null && age <= Number(env.FRESH_MIN || 8);
    if (now - last < cooldownS * 1000 || freshEnough) {
      const reason = freshEnough ? 'packet already fresh' : 'cooldown';
      const retry = freshEnough ? 0 : Math.ceil((cooldownS * 1000 - (now - last)) / 1000);
      return cors(json({
        ok: true, triggered: false, reason, packet_age_min: age, retry_in_s: retry,
        hint: 're-read https://raw.githubusercontent.com/' + env.REPO + '/master/SALAM_DATA_HUB.json',
      }));
    }

    const out = await dispatch(env, env.REF || 'master');
    if (!out.ok) {
      return cors(json({ ok: false, error: 'github refused the dispatch', status: out.status,
                         body: out.text.slice(0, 400), packet_age_min: age }, 502));
    }

    await env.SALAM_KV.put('last_dispatch', String(now), { expirationTtl: 3600 });
    return cors(json({
      ok: true, triggered: true, packet_age_min: age,
      note: 'run queued. The packet lands in ~40-90 s; raw.githubusercontent serves it within a few '
          + 'minutes and GitHub Pages within ~10. Poll the raw URL, not the Pages URL.',
      raw: 'https://raw.githubusercontent.com/' + env.REPO + '/master/SALAM_DATA_HUB.json',
      run: `https://github.com/${env.REPO}/actions`,
    }));
  },
};

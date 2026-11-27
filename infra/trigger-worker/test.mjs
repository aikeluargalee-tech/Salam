import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import worker from './src/index.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const toml = fs.readFileSync(path.join(here, 'wrangler.toml'), 'utf8');

function makeKV(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    async get(k) { return store.has(k) ? store.get(k) : null; },
    async put(k, v) { store.set(k, String(v)); },
    async delete(k) { store.delete(k); },
    _store: store,
  };
}

function makeEnv(kv, overrides = {}) {
  return {
    REPO: 'aikeluargalee-tech/Salam',
    WORKFLOW: 'salam.yml',
    REF: 'master',
    COOLDOWN_S: '90',
    PUBLIC_COOLDOWN_S: '300',
    FRESH_MIN: '8',
    MAX_STALE_MIN: '180',
    SALAM_KV: kv,
    GH_TOKEN: 'test-pat',
    TRIGGER_SECRET: 'test-secret',
    ...overrides,
  };
}

function mockFetch({ ageMin = 35, ghStatus = 204, ghBody = '', calls = [] } = {}) {
  const stamp = new Date(Date.now() - ageMin * 60_000).toISOString().slice(0, 19) + 'Z';
  globalThis.fetch = async (url, init = {}) => {
    const u = String(url);
    calls.push({ url: u, method: init.method || 'GET', body: init.body });
    if (u.startsWith('https://raw.githubusercontent.com/')) {
      return new Response(JSON.stringify({ generated_at_utc: stamp }), { status: 200 });
    }
    if (u.includes('/dispatches')) {
      return new Response(ghStatus === 204 ? null : ghBody, { status: ghStatus });
    }
    return new Response('ok', { status: 200 });
  };
}

const fails = [];
async function runTest(name, fn) {
  try {
    await fn();
    console.log(`  PASS  ${name}`);
  } catch (err) {
    console.log(`  FAIL  ${name}  (${err.message})`);
    fails.push(name);
  }
}

await runTest('wrangler.toml defines */30 cron trigger and 180m MAX_STALE_MIN', async () => {
  assert.match(toml, /\[triggers\]/);
  assert.match(toml, /crons\s*=\s*\[\s*"\*\/30 \* \* \* \*"\s*\]/);
  assert.match(toml, /MAX_STALE_MIN\s*=\s*"180"/);
});

await runTest('worker exports a scheduled() handler', async () => {
  assert.equal(typeof worker.scheduled, 'function');
});

await runTest('scheduled() dispatches when packet is stale and updates KV', async () => {
  assert.equal(typeof worker.scheduled, 'function');
  const kv = makeKV({ last_error: 'HTTP 401' });
  const calls = [];
  mockFetch({ ageMin: 35, ghStatus: 204, calls });
  await worker.scheduled({}, makeEnv(kv), {});
  assert.equal(calls.some((c) => c.url.includes('/dispatches')), true);
  assert.ok(await kv.get('last_dispatch'));
  assert.equal(await kv.get('last_error'), null);
});

await runTest('scheduled() skips dispatch when packet is fresh (<= FRESH_MIN)', async () => {
  assert.equal(typeof worker.scheduled, 'function');
  const kv = makeKV();
  const calls = [];
  mockFetch({ ageMin: 3, ghStatus: 204, calls });
  await worker.scheduled({}, makeEnv(kv), {});
  assert.equal(calls.some((c) => c.url.includes('/dispatches')), false);
});

await runTest('scheduled() records last_error in KV on GitHub 401', async () => {
  assert.equal(typeof worker.scheduled, 'function');
  const kv = makeKV();
  const calls = [];
  mockFetch({ ageMin: 40, ghStatus: 401, ghBody: 'Bad credentials', calls });
  await worker.scheduled({}, makeEnv(kv), {});
  const err = await kv.get('last_error');
  assert.ok(err && err.includes('401'), `expected 401 in last_error, got ${err}`);
});

await runTest('GET /health returns 200 when packet <= 180m and no error', async () => {
  const kv = makeKV();
  mockFetch({ ageMin: 20 });
  const res = await worker.fetch(new Request('https://example.workers.dev/health'), makeEnv(kv));
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.stale, false);
});

await runTest('GET /health returns 503 when packet > 180m (3h dead-man threshold)', async () => {
  const kv = makeKV();
  mockFetch({ ageMin: 185 });
  const res = await worker.fetch(new Request('https://example.workers.dev/health'), makeEnv(kv));
  assert.equal(res.status, 503);
  const body = await res.json();
  assert.equal(body.ok, false);
  assert.equal(body.stale, true);
});

await runTest('GET /health returns 503 when last_error is recorded in KV', async () => {
  const kv = makeKV({ last_error: 'HTTP 401: Bad credentials' });
  mockFetch({ ageMin: 10 });
  const res = await worker.fetch(new Request('https://example.workers.dev/health'), makeEnv(kv));
  assert.equal(res.status, 503);
  const body = await res.json();
  assert.equal(body.ok, false);
  assert.match(String(body.last_error), /401/);
});

console.log(`\n${fails.length ? `${fails.length} FAILED` : 'ALL PASS'}`);
process.exit(fails.length ? 1 : 0);

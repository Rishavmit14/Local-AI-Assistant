import assert from 'node:assert/strict';
import { createServer as createHttpServer, request as httpRequest } from 'node:http';
import { chmodSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { test } from 'node:test';
import { createLocalUiServer } from './local-ui.mjs';

function listen(server, port = 0) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server.address().port));
  });
}

function close(server) {
  return new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
}

function getWithHost(port, host) {
  return new Promise((resolve, reject) => {
    const request = httpRequest({ hostname: '127.0.0.1', port, path: '/', headers: { host } }, response => {
      response.resume();
      response.on('end', () => resolve(response.statusCode));
    });
    request.on('error', reject);
    request.end();
  });
}

async function availablePort() {
  const probe = createHttpServer();
  const port = await listen(probe);
  await close(probe);
  return port;
}

test('built loopback UI serves static assets and preserves the exact Owner proxy boundary', async () => {
  const root = mkdtempSync(join(tmpdir(), 'friday-ui-'));
  chmodSync(root, 0o700);
  const dist = join(root, 'dist');
  mkdirSync(join(dist, 'assets'), { recursive: true });
  writeFileSync(join(dist, 'index.html'), '<!doctype html><title>Friday candidate</title>');
  writeFileSync(join(dist, 'assets', 'app.js'), 'globalThis.friday = true;');
  const capability = randomBytes(32).toString('hex');
  const capabilityFile = join(root, 'owner-capability.json');
  writeFileSync(capabilityFile, JSON.stringify({ version: 1, uid: process.getuid(), installation: root, capability }), { mode: 0o600 });

  const upstreamRequests = [];
  const apiServer = createHttpServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    upstreamRequests.push({ method: request.method, url: request.url, headers: request.headers, body: Buffer.concat(chunks).toString() });
    response.writeHead(200, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ ok: true }));
  });
  let uiServer;
  try {
    const apiPort = await listen(apiServer);
    const uiPort = await availablePort();
    const env = {
      LOCAL_AI_OWNER_TRUST_MODE: 'local_single_user',
      LOCAL_AI_OWNER_CAPABILITY_FILE: capabilityFile,
      LOCAL_AI_OWNER_INSTALLATION: root,
      LOCAL_AI_OWNER_UI_ORIGIN: `http://127.0.0.1:${uiPort}`,
      VITE_FRIDAY_API_ORIGIN: `http://127.0.0.1:${apiPort}`,
    };
    uiServer = createLocalUiServer({ distDir: dist, port: uiPort, env });
    await listen(uiServer, uiPort);
    const origin = env.LOCAL_AI_OWNER_UI_ORIGIN;

    const page = await fetch(`${origin}/`);
    assert.equal(page.status, 200);
    assert.match(await page.text(), /Friday candidate/);
    assert.equal(page.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(await getWithHost(uiPort, 'attacker.invalid'), 421);
    assert.equal((await fetch(`${origin}/assets/app.js`)).headers.get('content-type'), 'text/javascript; charset=utf-8');
    const deepLink = await fetch(`${origin}/workspace`, { headers: { accept: 'text/html' } });
    assert.match(await deepLink.text(), /Friday candidate/);
    assert.equal((await fetch(`${origin}/%2e%2e%2foutside`)).status, 404);
    assert.equal((await fetch(`${origin}/assets/app.js`, { method: 'POST' })).status, 405);

    const health = await fetch(`${origin}/health`, { headers: {
      authorization: 'Bearer local-test-token', cookie: 'friday_session=local-test', 'x-csrf-token': 'csrf-test',
      'x-friday-local-owner': 'forged-capability', 'x-forwarded-for': '203.0.113.50',
    } });
    assert.deepEqual(await health.json(), { ok: true });
    assert.equal(upstreamRequests.at(-1).url, '/health');
    assert.equal(upstreamRequests.at(-1).headers.authorization, 'Bearer local-test-token');
    assert.equal(upstreamRequests.at(-1).headers.cookie, 'friday_session=local-test');
    assert.equal(upstreamRequests.at(-1).headers['x-csrf-token'], 'csrf-test');
    assert.equal(upstreamRequests.at(-1).headers['x-forwarded-for'], undefined);
    assert.equal(upstreamRequests.at(-1).headers['x-friday-local-owner'], undefined);

    await fetch(`${origin}/api/v1/project-execution/restore`, {
      method: 'POST', headers: {
        origin, 'content-type': 'application/json', 'x-friday-local-owner': 'forged-capability',
      }, body: JSON.stringify({ recovery_id: 'candidate-fixture' }),
    });
    assert.equal(upstreamRequests.at(-1).headers['x-friday-local-owner'], capability);
    assert.equal(upstreamRequests.at(-1).body, '{"recovery_id":"candidate-fixture"}');

    await fetch(`${origin}/api/v1/project-execution/restore`, {
      method: 'POST', headers: {
        origin: 'http://attacker.invalid', 'content-type': 'application/json', 'x-friday-local-owner': 'forged-capability',
      }, body: '{}',
    });
    assert.equal(upstreamRequests.at(-1).headers['x-friday-local-owner'], undefined);
    await fetch(`${origin}/api/v1/objectives/example/execute`, {
      method: 'POST', headers: { origin, 'x-friday-local-owner': 'forged-capability' }, body: '{}',
    });
    assert.equal(upstreamRequests.at(-1).headers['x-friday-local-owner'], undefined);
  } finally {
    if (uiServer?.listening) await close(uiServer);
    if (apiServer.listening) await close(apiServer);
    rmSync(root, { recursive: true, force: true });
  }
});

test('built loopback UI rejects non-loopback origins and mismatched ports', () => {
  const root = mkdtempSync(join(tmpdir(), 'friday-ui-config-'));
  chmodSync(root, 0o700);
  const dist = join(root, 'dist');
  mkdirSync(dist);
  writeFileSync(join(dist, 'index.html'), '<!doctype html>');
  try {
    assert.throws(() => createLocalUiServer({ distDir: dist, port: 5193, env: {
      LOCAL_AI_OWNER_UI_ORIGIN: 'http://0.0.0.0:5193', VITE_FRIDAY_API_ORIGIN: 'http://127.0.0.1:8765',
    } }), /exact loopback HTTP origin/);
    assert.throws(() => createLocalUiServer({ distDir: dist, port: 5193, env: {
      LOCAL_AI_OWNER_UI_ORIGIN: 'http://127.0.0.1:5192', VITE_FRIDAY_API_ORIGIN: 'http://127.0.0.1:8765',
    } }), /origin port must match/);
    assert.throws(() => createLocalUiServer({ distDir: dist, port: 5193, env: {
      LOCAL_AI_OWNER_UI_ORIGIN: 'http://127.0.0.1:5193', VITE_FRIDAY_API_ORIGIN: 'http://192.0.2.8:8765',
    } }), /exact loopback HTTP origin/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { test } from 'node:test';
import { localOwnerBridge } from './local-owner.mjs';

test('private bridge supplies capability only for exact local restoration', () => {
  const root = mkdtempSync(join(tmpdir(), 'friday-owner-'));
  try {
    const filename = join(root, 'owner.json');
    const capability = randomBytes(32).toString('hex');
    writeFileSync(filename, JSON.stringify({ version: 1, uid: process.getuid(), installation: root, capability }), { mode: 0o600 });
    const bridge = localOwnerBridge({ LOCAL_AI_OWNER_TRUST_MODE: 'local_single_user',
      LOCAL_AI_OWNER_CAPABILITY_FILE: filename, LOCAL_AI_OWNER_INSTALLATION: root,
      LOCAL_AI_OWNER_UI_ORIGIN: 'http://127.0.0.1:5191', VITE_FRIDAY_API_ORIGIN: 'http://127.0.0.1:8766' });
    let handler;
    bridge.configure({ on: (_, callback) => { handler = callback; } });
    const original = { method: 'POST', url: '/api/v1/project-execution/restore',
      socket: { remoteAddress: '127.0.0.1' }, headers: { origin: 'http://127.0.0.1:5191', host: '127.0.0.1:5191' } };
    for (const [request, allowed] of [
      [original, true],
      [{ ...original, socket: { remoteAddress: '192.0.2.1' } }, false],
      [{ ...original, headers: { ...original.headers, origin: 'https://attacker.invalid' } }, false],
      [{ ...original, headers: { ...original.headers, host: 'attacker.invalid' } }, false],
      [{ ...original, url: '/api/v1/project-execution/restore?token=bad' }, false],
      [{ ...original, method: 'GET' }, false],
      [{ ...original, url: '/api/v1/objectives/example/execute' }, false],
    ]) {
      const outgoing = { 'x-friday-local-owner': 'attacker-header' };
      handler({ removeHeader: name => delete outgoing[name], setHeader: (name, value) => { outgoing[name] = value; } }, request);
      assert.equal(outgoing['x-friday-local-owner'], allowed ? capability : undefined);
    }
    rmSync(filename);
    let sent = false;
    handler({ removeHeader() {}, setHeader() { sent = true; } }, original);
    assert.equal(sent, false);
    assert.throws(() => bridge.plugin.configureServer({ config: { server: { host: '0.0.0.0' } } }));
  } finally { rmSync(root, { recursive: true }); }
});

test('interactive mode never installs the bridge', () => {
  assert.equal(localOwnerBridge({}), undefined);
  assert.throws(() => localOwnerBridge({ LOCAL_AI_OWNER_TRUST_MODE: 'multi_user' }));
});

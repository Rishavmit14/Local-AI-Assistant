// Server-only bridge. This file must never be imported by frontend/src.
import { constants, closeSync, fstatSync, lstatSync, openSync, readFileSync, realpathSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

export function localOwnerBridge(env = process.env) {
  const mode = env.LOCAL_AI_OWNER_TRUST_MODE ?? 'interactive';
  if (!['interactive', 'local_single_user'].includes(mode)) throw new Error('Unsupported owner trust mode');
  if (mode === 'interactive') return undefined;
  const filename = env.LOCAL_AI_OWNER_CAPABILITY_FILE;
  const installation = env.LOCAL_AI_OWNER_INSTALLATION;
  const origin = env.LOCAL_AI_OWNER_UI_ORIGIN;
  const target = env.VITE_FRIDAY_API_ORIGIN;
  for (const value of [origin, target]) {
    const url = new URL(value);
    if (!['127.0.0.1', 'localhost'].includes(url.hostname) || url.protocol !== 'http:' || url.origin !== value)
      throw new Error('Local owner bridge requires exact loopback HTTP origins');
  }
  if (!filename || !installation) throw new Error('Local owner bridge configuration missing');
  const readCapability = () => {
    const parent = dirname(resolve(filename));
    const info = lstatSync(parent);
    if (realpathSync(parent) !== parent || info.uid !== process.getuid() || (info.mode & 0o777) !== 0o700)
      throw new Error('Local owner directory must be private');
    const fd = openSync(filename, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    try {
      const file = fstatSync(fd);
      if (!file.isFile() || file.uid !== process.getuid() || (file.mode & 0o777) !== 0o600 || file.nlink !== 1 || file.size > 4096)
        throw new Error('Local owner capability must be private');
      const value = JSON.parse(readFileSync(fd, 'utf8'));
      if (value.version !== 1 || value.uid !== process.getuid() || value.installation !== realpathSync(installation)
          || !/^[a-f0-9]{64}$/.test(value.capability)) throw new Error('Invalid installation capability');
      return value.capability;
    } finally { closeSync(fd); }
  };
  readCapability();
  return {
    configure(proxy) {
      proxy.on('proxyReq', (proxyReq, req) => {
        proxyReq.removeHeader('x-friday-local-owner');
        if (req.method !== 'POST' || req.url !== '/api/v1/project-execution/restore') return;
        if (!['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress)
            || req.headers.origin !== origin || req.headers.host !== new URL(origin).host) return;
        try { proxyReq.setHeader('x-friday-local-owner', readCapability()); }
        catch { /* Revoked or invalid local credentials fail closed at the API. */ }
      });
    },
    plugin: {
      name: 'friday-local-owner-boundary',
      configureServer(server) {
        if (server.config.server.host !== '127.0.0.1') throw new Error('Local owner UI must bind loopback');
      },
    },
  };
}

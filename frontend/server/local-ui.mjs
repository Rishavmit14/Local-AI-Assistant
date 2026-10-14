import { createReadStream, realpathSync, statSync } from 'node:fs';
import { createServer, request as proxyRequest } from 'node:http';
import { extname, isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { localOwnerBridge } from './local-owner.mjs';

const CONTENT_TYPES = new Map([
  ['.css', 'text/css; charset=utf-8'], ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'], ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'], ['.map', 'application/json; charset=utf-8'],
  ['.png', 'image/png'], ['.svg', 'image/svg+xml'], ['.ttf', 'font/ttf'],
  ['.txt', 'text/plain; charset=utf-8'], ['.wasm', 'application/wasm'],
  ['.webp', 'image/webp'], ['.woff', 'font/woff'], ['.woff2', 'font/woff2'],
]);
const REQUEST_HOP_HEADERS = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'proxy-connection', 'te', 'trailer', 'transfer-encoding', 'upgrade',
]);
const RESPONSE_HOP_HEADERS = new Set([...REQUEST_HOP_HEADERS, 'host']);

function exactLoopbackOrigin(value, fallback, label) {
  const text = value ?? fallback;
  const url = new URL(text);
  if (!['127.0.0.1', 'localhost'].includes(url.hostname) || url.protocol !== 'http:' || url.origin !== text)
    throw new Error(`${label} must be an exact loopback HTTP origin`);
  return url;
}

function loopback(address) {
  return ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(address);
}

function sendText(response, status, text, extraHeaders = {}) {
  const body = Buffer.from(text);
  response.writeHead(status, {
    'Content-Length': String(body.byteLength),
    'Content-Type': 'text/plain; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    ...extraHeaders,
  });
  response.end(body);
}

function requestPath(request, origin) {
  if (typeof request.url !== 'string' || !request.url.startsWith('/') || request.url.startsWith('//')) return undefined;
  let url;
  try { url = new URL(request.url, origin); } catch { return undefined; }
  if (url.origin !== origin.origin) return undefined;
  return url;
}

function containedPath(root, pathname) {
  let decoded;
  try { decoded = decodeURIComponent(pathname); } catch { return undefined; }
  if (decoded.includes('\0') || decoded.includes('\\') || decoded.split('/').some(segment => segment.startsWith('.'))) return undefined;
  const candidate = resolve(root, `.${decoded}`);
  const unresolved = relative(root, candidate);
  if (unresolved === '..' || unresolved.startsWith(`..${sep}`) || isAbsolute(unresolved)) return undefined;
  try {
    const actual = realpathSync(candidate);
    const rel = relative(root, actual);
    if (rel === '..' || rel.startsWith(`..${sep}`) || isAbsolute(rel)) return undefined;
    if (!statSync(actual).isFile()) return undefined;
    return actual;
  } catch { return undefined; }
}

function outgoingHeaders(request, apiOrigin, bridge) {
  const blocked = new Set(REQUEST_HOP_HEADERS);
  for (const token of String(request.headers.connection ?? '').split(',')) {
    if (token.trim()) blocked.add(token.trim().toLowerCase());
  }
  const headers = {};
  for (const [name, value] of Object.entries(request.headers)) {
    const key = name.toLowerCase();
    if (value === undefined || blocked.has(key) || key === 'host' || key === 'forwarded'
        || key.startsWith('x-forwarded-') || key === 'x-real-ip' || key === 'x-friday-local-owner') continue;
    headers[key] = value;
  }
  headers.host = apiOrigin.host;
  bridge?.authorizeProxyRequest({
    removeHeader(name) { delete headers[name.toLowerCase()]; },
    setHeader(name, value) { headers[name.toLowerCase()] = value; },
  }, request);
  return headers;
}

function proxyApi(request, response, url, apiOrigin, bridge) {
  const pathname = url.pathname;
  if (!(pathname === '/api' || pathname.startsWith('/api/') || pathname === '/health' || pathname.startsWith('/health/'))) {
    sendText(response, 404, 'Not found');
    return;
  }
  const target = new URL(apiOrigin);
  target.pathname = pathname;
  target.search = url.search;
  const upstream = proxyRequest(target, {
    method: request.method,
    headers: outgoingHeaders(request, apiOrigin, bridge),
  }, upstreamResponse => {
    const headers = {};
    for (const [name, value] of Object.entries(upstreamResponse.headers)) {
      if (value !== undefined && !RESPONSE_HOP_HEADERS.has(name.toLowerCase())) headers[name] = value;
    }
    response.writeHead(upstreamResponse.statusCode ?? 502, headers);
    upstreamResponse.pipe(response);
  });
  upstream.on('error', () => {
    if (!response.headersSent) sendText(response, 502, 'Friday API is unavailable');
    else response.destroy();
  });
  request.on('aborted', () => upstream.destroy());
  response.on('close', () => { if (!response.writableEnded) upstream.destroy(); });
  request.pipe(upstream);
}

export function createLocalUiServer({
  distDir = resolve('dist'),
  port = Number(process.env.FRIDAY_UI_PORT ?? 5193),
  env = process.env,
} = {}) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('FRIDAY_UI_PORT must be a valid TCP port');
  const uiOrigin = exactLoopbackOrigin(env.LOCAL_AI_OWNER_UI_ORIGIN, `http://127.0.0.1:${port}`, 'Owner UI origin');
  if (Number(uiOrigin.port || 80) !== port) throw new Error('Owner UI origin port must match FRIDAY_UI_PORT');
  const apiOrigin = exactLoopbackOrigin(env.VITE_FRIDAY_API_ORIGIN, 'http://127.0.0.1:8765', 'Friday API origin');
  const root = realpathSync(resolve(distDir));
  const indexFile = containedPath(root, '/index.html');
  if (!indexFile) throw new Error('Frontend build directory must contain a regular index.html');
  const bridge = localOwnerBridge(env);

  return createServer((request, response) => {
    if (!loopback(request.socket.remoteAddress)) {
      sendText(response, 403, 'Loopback clients only');
      return;
    }
    if (request.headers.host !== uiOrigin.host) {
      sendText(response, 421, 'Unexpected UI host');
      return;
    }
    const url = requestPath(request, uiOrigin);
    if (!url) {
      sendText(response, 400, 'Invalid request target');
      return;
    }
    if (url.pathname === '/api' || url.pathname.startsWith('/api/')
        || url.pathname === '/health' || url.pathname.startsWith('/health/')) {
      proxyApi(request, response, url, apiOrigin, bridge);
      return;
    }
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      sendText(response, 405, 'Static UI accepts GET and HEAD requests only', { Allow: 'GET, HEAD' });
      return;
    }
    let pathname = url.pathname;
    let file = containedPath(root, pathname);
    if (!file && (pathname === '/' || request.headers.accept?.includes('text/html') && !extname(pathname))) {
      pathname = '/index.html';
      file = indexFile;
    }
    if (!file) {
      sendText(response, 404, 'Not found');
      return;
    }
    const size = statSync(file).size;
    const cacheControl = pathname === '/index.html' ? 'no-cache' : 'public, max-age=0, must-revalidate';
    response.writeHead(200, {
      'Cache-Control': cacheControl,
      'Content-Length': String(size),
      'Content-Type': CONTENT_TYPES.get(extname(file).toLowerCase()) ?? 'application/octet-stream',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'same-origin',
    });
    if (request.method === 'HEAD') response.end();
    else {
      const stream = createReadStream(file);
      stream.on('error', () => {
        if (!response.headersSent) sendText(response, 404, 'Not found');
        else response.destroy();
      });
      stream.pipe(response);
    }
  });
}

const entry = process.argv[1] ? resolve(process.argv[1]) : '';
if (entry === fileURLToPath(import.meta.url)) {
  const server = createLocalUiServer();
  server.listen(Number(process.env.FRIDAY_UI_PORT ?? 5193), '127.0.0.1', () => {
    console.log(`Friday UI listening at http://127.0.0.1:${server.address().port}`);
  });
  const close = () => server.close(() => process.exit(0));
  process.once('SIGTERM', close);
  process.once('SIGINT', close);
}

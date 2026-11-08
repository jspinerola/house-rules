// Metro serves the bundle over `expo start --tunnel`; this middleware also forwards
// /brain/* to the brain so the phone reaches it through the same tunnel.
const http = require('http');
const https = require('https');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
const target = new URL(process.env.BRAIN_URL || 'http://localhost:8000');
const PREFIX = '/brain/';

function proxy(req, res) {
  const client = target.protocol === 'https:' ? https : http;
  const headers = { ...req.headers, host: target.host };
  const upstream = client.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: req.url.slice(PREFIX.length - 1),
      headers,
    },
    (up) => {
      res.writeHead(up.statusCode || 502, up.headers);
      up.pipe(res);
    },
  );
  upstream.on('error', (err) => {
    console.error(`[brain proxy] ${req.method} ${req.url} -> ${target.origin}: ${err.code || err.message}`);
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ error: `brain unreachable at ${target.origin}: ${err.code || err.message}` }));
  });
  req.pipe(upstream);
}

const previous = config.server.enhanceMiddleware;
config.server.enhanceMiddleware = (middleware, server) => {
  const inner = previous ? previous(middleware, server) : middleware;
  return (req, res, next) => (req.url && req.url.startsWith(PREFIX) ? proxy(req, res) : inner(req, res, next));
};

module.exports = config;

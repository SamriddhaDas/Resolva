/**
 * Lightweight Node.js dev server for the static frontend.
 * Proxies /api/* to the Python FastAPI backend (default http://localhost:8000).
 *
 * Run:
 *   node server.js            # serves on :3000, proxies to :8000
 *   PORT=4000 API=http://localhost:9000 node server.js
 *
 * Zero-dependency — uses only Node built-ins.
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const { URL } = require("url");

const PORT = parseInt(process.env.PORT || "3000", 10);
const API = process.env.API || "http://localhost:8000";
const ROOT = path.resolve(__dirname, "..", "frontend");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js":   "application/javascript; charset=utf-8",
  ".css":  "text/css; charset=utf-8",
  ".svg":  "image/svg+xml",
  ".png":  "image/png",
  ".ico":  "image/x-icon",
  ".json": "application/json",
};

function proxy(req, res) {
  const target = new URL(req.url, API);
  const opts = {
    method: req.method,
    headers: { ...req.headers, host: target.host },
  };
  const upstream = http.request(target, opts, (up) => {
    res.writeHead(up.statusCode || 502, up.headers);
    up.pipe(res);
  });
  upstream.on("error", (e) => {
    res.writeHead(502, { "content-type": "text/plain" });
    res.end("Backend unreachable: " + e.message);
  });
  req.pipe(upstream);
}

function serveStatic(req, res) {
  let urlPath = decodeURIComponent(req.url.split("?")[0]);
  if (urlPath === "/") urlPath = "/index.html";
  // strip leading / and prevent traversal
  const safe = path
    .normalize(urlPath)
    .replace(/^([/\\])+/, "");
  const filePath = path.join(ROOT, safe);
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403); res.end("Forbidden"); return;
  }
  fs.stat(filePath, (err, st) => {
    if (err || !st.isFile()) {
      // SPA-ish fallback: serve index.html for unknown routes
      const fb = path.join(ROOT, "index.html");
      fs.readFile(fb, (e, data) => {
        if (e) { res.writeHead(404); res.end("Not Found"); return; }
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        res.end(data);
      });
      return;
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, { "content-type": MIME[ext] || "application/octet-stream" });
    fs.createReadStream(filePath).pipe(res);
  });
}

http.createServer((req, res) => {
  if (req.url.startsWith("/api/")) return proxy(req, res);
  return serveStatic(req, res);
}).listen(PORT, () => {
  console.log(`▶ Frontend  : http://localhost:${PORT}`);
  console.log(`▶ Proxying  : /api/* → ${API}`);
});

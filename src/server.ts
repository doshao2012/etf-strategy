import { createServer, IncomingMessage, ServerResponse } from 'http';
import { parse as parseUrl } from 'url';
import next from 'next';

const dev = process.env.COZE_PROJECT_ENV !== 'PROD';
const hostname = process.env.HOSTNAME || 'localhost';
const port = parseInt(process.env.PORT || '5000', 10);

// Backend server URL
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:3000';

// Create Next.js app
const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

// Proxy handler for API requests
function proxyRequest(
  req: IncomingMessage,
  res: ServerResponse,
  pathname: string
): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = new URL(pathname, BACKEND_URL);
    
    const options = {
      hostname: url.hostname,
      port: url.port || (url.protocol === 'https:' ? 443 : 80),
      path: url.pathname + url.search,
      method: req.method || 'GET',
      headers: {
        ...req.headers,
        host: url.host,
      },
    };

    const proxyReq = require('http').request(options, (proxyRes: IncomingMessage) => {
      // Handle CORS headers
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
      
      if (proxyRes.statusCode) {
        res.statusCode = proxyRes.statusCode;
      }
      
      // Copy headers from proxy response
      Object.entries(proxyRes.headers).forEach(([key, value]) => {
        if (value) {
          res.setHeader(key, value);
        }
      });
      
      proxyRes.pipe(res, { end: true });
      proxyRes.on('end', resolve);
      proxyRes.on('error', reject);
    });

    proxyReq.on('error', (err: Error) => {
      console.error('Proxy request error:', err);
      res.statusCode = 502;
      res.end(JSON.stringify({ error: 'Bad gateway', message: err.message }));
      reject(err);
    });

    // Pipe request body if present
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      req.pipe(proxyReq, { end: true });
    } else {
      proxyReq.end();
    }
  });
}

app.prepare().then(() => {
  const server = createServer(async (req, res) => {
    try {
      const parsedUrl = parseUrl(req.url!, true);
      const pathname = parsedUrl.pathname || '';

      // Proxy API requests to backend
      if (pathname.startsWith('/api/')) {
        await proxyRequest(req, res, pathname + (parsedUrl.search || ''));
        return;
      }

      // Proxy /strategy/* requests to backend
      if (pathname.startsWith('/strategy/')) {
        await proxyRequest(req, res, pathname + (parsedUrl.search || ''));
        return;
      }

      await handle(req, res, parsedUrl);
    } catch (err) {
      console.error('Error occurred handling', req.url, err);
      res.statusCode = 500;
      res.end('Internal server error');
    }
  });

  server.once('error', (err) => {
    console.error(err);
    process.exit(1);
  });

  server.listen(port, () => {
    console.log(
      `> Server listening at http://${hostname}:${port} as ${
        dev ? 'development' : process.env.COZE_PROJECT_ENV
      }`,
    );
    if (dev) {
      console.log(`> Backend proxy: ${BACKEND_URL}`);
    }
  });
});

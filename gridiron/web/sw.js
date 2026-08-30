/*
 * The app shell, and nothing else.
 *
 * THIS WORKER MUST NEVER CACHE A RESPONSE FROM /api/. That is not a performance
 * preference, it is the same rule as every other one here: a forecaster that
 * shows yesterday's probabilities as though they were today's is lying, and it
 * is lying in the one way this project exists to prevent. A calibration figure
 * served from a cache has no N you can trust, a slate served from a cache may
 * be a slate whose games have finished, and neither carries any sign that it is
 * stale.
 *
 * So: the shell (HTML, CSS, JS, icons) is cached so the app opens instantly and
 * survives a flaky connection. Data is ALWAYS fetched from the network. When
 * the network is gone, the app says it is offline. It does not guess.
 *
 * `tools/guards/plant.py` plants a data-caching worker and asserts the audit
 * catches it by name.
 */

const SHELL_CACHE = 'gridiron-shell-v1';

const SHELL = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/icon.svg',
  '/static/manifest.webmanifest'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((n) => n !== SHELL_CACHE).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Never our business: another origin, or a verb that changes something.
  if (url.origin !== self.location.origin || event.request.method !== 'GET') {
    return;
  }

  // DATA IS NEVER CACHED AND NEVER SERVED FROM A CACHE. Not on failure, not as
  // a fallback, not "just this once". The request goes to the network and its
  // failure is allowed to reach the page, which is what makes the page able to
  // say "offline" honestly instead of rendering a number nobody can date.
  if (url.pathname.startsWith('/api/') ||
      url.pathname.startsWith('/auth/') ||
      url.pathname === '/login') {
    return;
  }

  // The shell: cache first, because it does not change between deploys and a
  // stale stylesheet cannot misinform anybody about a forecast.
  event.respondWith(
    caches.match(event.request).then((hit) => hit || fetch(event.request))
  );
});

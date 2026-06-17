// Service worker for the Royal Himalayans Progressive Web App.
// It caches important pages and static assets so the site can load offline.

const CACHE_NAME = 'royal-himalayans-v1';

// Files stored during installation. Add new images/CSS/JS here if they must work offline.
const ASSETS = [
    '/',
    '/services',
    '/about',
    '/contact',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/manifest.json',
    '/static/img/icons/logo.png',
    '/static/img/icons/icon-192.png',
    '/static/img/icons/icon-512.png',
    '/static/img/icons/android-head-units.png',
    '/static/img/icons/apple-carplay.png',
    '/static/img/icons/android-auto.png',
    '/static/img/icons/dash-cams.png',
    '/static/img/icons/parking-sensors.png'
];

// Install event: open the cache and store the core PWA assets.
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

// Activate event: remove old caches when the cache name/version changes.
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        ))
    );
    self.clients.claim();
});

// Fetch event: use cached files first, then fall back to the network.
self.addEventListener('fetch', (event) => {
    // Only cache GET requests. POST requests, such as booking forms, must go to the server.
    if (event.request.method !== 'GET') return;

    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) return cachedResponse;

            return fetch(event.request)
                .then((networkResponse) => {
                    // Save a copy of successful network responses for future offline use.
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                    return networkResponse;
                })
                .catch(() => {
                    // If the user is navigating while offline, show the cached homepage.
                    if (event.request.mode === 'navigate') {
                        return caches.match('/');
                    }
                    return new Response('Offline', { status: 503, statusText: 'Offline' });
                });
        })
    );
});

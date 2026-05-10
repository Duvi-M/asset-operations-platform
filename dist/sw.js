const STATIC_CACHE = 'sgoi-static-v1'
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/manifest.webmanifest',
  '/icons/icon-192.svg',
  '/icons/icon-512.svg',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  )
  self.clients.claim()
})

self.addEventListener('fetch', (event) => {
  const { request } = event

  if (request.method !== 'GET') {
    return
  }

  const url = new URL(request.url)
  const isSameOrigin = url.origin === self.location.origin

  if (!isSameOrigin) {
    return
  }

  if (
    url.pathname.startsWith('/api') ||
    url.pathname.includes('/pdf') ||
    url.pathname.includes('/qr')
  ) {
    event.respondWith(fetch(request))
    return
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => {
        const cachedApp = await caches.match('/index.html')
        return cachedApp || caches.match('/offline.html')
      })
    )
    return
  }

  const destination = request.destination
  const isStaticAsset =
    destination === 'style' ||
    destination === 'script' ||
    destination === 'font' ||
    destination === 'image' ||
    destination === 'manifest'

  if (!isStaticAsset) {
    return
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      const networkFetch = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone()
            caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy))
          }
          return response
        })
        .catch(() => cached)

      return cached || networkFetch
    })
  )
})

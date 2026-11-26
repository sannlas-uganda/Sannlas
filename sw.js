self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());

// OneSignal Worker - Keep this!
importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js");

// --- SANNLAS CUSTOM PUSH (VAPID) ---
self.addEventListener('push', function(event) {
  let data = {};
  try { data = event.data.json(); } catch(e) { data = {title:'Sannlas', body: event.data.text()}; }
  // Don't double-show if it's from OneSignal
  if (data.custom && data.custom.i) return;
  const options = {
    body: data.body || 'New order!',
    icon: '/static/icon.png',
    badge: '/static/icon.png',
    data: { url: data.url || '/' },
    vibrate: [200, 100, 200]
  };
  event.waitUntil(self.registration.showNotification(data.title || '🔔 Sannlas - New Order!', options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url || '/'));
});

self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => self.clients.claim());

// OneSignal Worker - IMPORTANT for notification icon like Facebook f
importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js");

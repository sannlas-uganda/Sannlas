// --- SANNLAS MERGED WORKER: OneSignal + User-to-User ---
importScripts('https://cdn.onesignal.com/sdks/web/v16/OneSignalSDKWorker.js');

self.addEventListener('push', function(e){
  // If it's OneSignal, let OneSignal handle it
  if(e.data && e.data.text().includes('onesignal')) return;
  // Our User-to-User push
  try{
    let data = e.data.json();
    e.waitUntil(self.registration.showNotification(data.title, {body: data.body, icon: '/icon-192.png', data: {url: data.url||'/my-shop'}}));
  }catch(err){}
});
self.addEventListener('notificationclick', function(e){
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data.url || '/my-shop'));
});

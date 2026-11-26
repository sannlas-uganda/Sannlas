// --- SANNLAS MERGED WORKER: OneSignal + User-to-User ---
importScripts('https://cdn.onesignal.com/sdks/web/v16/OneSignalSDKWorker.js');

self.addEventListener('push', function(e){
  // READ ONCE ONLY!
  let text = '';
  try { text = e.data.text(); } catch(err){ return; }
  
  // If it's OneSignal, let OneSignal handle it
  if(text.includes('onesignal') || text.includes('custom')) return;

  // Our User-to-User push
  try{
    let data = JSON.parse(text);
    if(!data.title) return;
    e.waitUntil(
      self.registration.showNotification(data.title, {
        body: data.body || 'You have a new order!',
        icon: '/icon-192.png',
        badge: '/icon-192.png',
        vibrate: [200, 100, 200],
        requireInteraction: true, // STAYS ON TOP until tapped!
        tag: 'sannlas-order',
        renotify: true,
        data: { url: data.url || '/my-shop' }
      })
    );
  }catch(err){ console.log('Push parse fail', err); }
});

self.addEventListener('notificationclick', function(e){
  e.notification.close();
  let url = (e.notification.data && e.notification.data.url) || '/my-shop';
  e.waitUntil(
    clients.matchAll({type:'window', includeUncontrolled:true}).then(function(list){
      for(let c of list){ if(c.url.includes(url) && 'focus' in c) return c.focus(); }
      if(clients.openWindow) return clients.openWindow(url);
    })
  );
});

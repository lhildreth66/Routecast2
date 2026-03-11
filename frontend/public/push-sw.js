/* Routecast Web Push Service Worker */
self.addEventListener('push', (event) => {
  const data = (() => {
    try {
      return event.data ? event.data.json() : {};
    } catch (e) {
      return { title: 'Routecast Alert', body: event.data ? event.data.text() : 'Weather update' };
    }
  })();

  const title = data.title || 'Routecast Alert';
  const body = data.body || 'Weather update on your route';
  const options = {
    body,
    data: data.data || {},
    badge: data.badge,
    icon: data.icon || '/favicon.png',
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(url);
      }
    })
  );
});

// N2 단어장 서비스 워커 — 앱 파일을 저장해 두고 오프라인에서도 열리게 한다.
const CACHE = 'n2tango-261021-9a18ad4';
const FONTS = 'n2tango-fonts-2';   // 2: 글꼴 CSS를 CORS로 받는다(옛 불투명 저장본은 activate에서 지운다)
const SHELL = ['./index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];
const NAV_WAIT = 3000;   // 페이지를 이만큼 기다려도 안 오면 저장본을 보여 준다

self.addEventListener('install', e => {
  // HTTP 캐시를 거치지 않고 받아야 새 버전 이름으로 옛 파일이 저장되지 않는다
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload' })))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('n2tango-') && k !== CACHE && k !== FONTS).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;            // Gemini API(POST)는 건드리지 않는다
  const url = new URL(req.url);

  if (url.origin === location.origin) {
    if (req.mode === 'navigate') {             // 페이지: 새 버전 먼저, 늦거나 오프라인이면 저장본
      let saving = Promise.resolve();
      // HTTP 캐시(Pages max-age 600초)를 거치지 않고 서버에 새 버전을 묻는다. 리다이렉트는 브라우저에 그대로 넘긴다
      const net = fetch(req.url, { cache: 'no-cache', redirect: 'manual' }).then(res => {
        if (res.ok && (res.headers.get('content-type') || '').startsWith('text/html')) {
          const copy = res.clone();
          saving = caches.open(CACHE).then(c => c.put('./index.html', copy));
        }
        return res;
      });
      e.waitUntil(net.then(() => saving).catch(() => {}));
      const saved = () => caches.match('./index.html');
      const late = new Promise(r => setTimeout(r, NAV_WAIT)).then(saved);
      e.respondWith(
        Promise.race([net, late])
          .then(res => !res ? net : res.ok || res.type === 'opaqueredirect' ? res : saved().then(hit => hit || res))
          .catch(() => saved().then(hit => hit || Response.error()))
      );
      return;
    }
    e.respondWith(caches.match(req).then(hit => hit || fetch(req)));
    return;
  }

  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {   // 글꼴: 저장본 먼저, 뒤에서 갱신
    let saving = Promise.resolve();
    const net = fetch(req).then(res => {
      if (res.ok) { const copy = res.clone(); saving = caches.open(FONTS).then(c => c.put(req, copy)); }
      return res;
    });
    e.waitUntil(net.then(() => saving).catch(() => {}));
    e.respondWith(caches.open(FONTS).then(c => c.match(req)).then(hit => hit || net));
  }
});

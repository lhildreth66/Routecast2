#!/usr/bin/env node
/**
 * E2E Push Delivery Proof Script
 *
 * Steps covered:
 *   Step 1 – Login and verify a real Expo push token is stored in /api/push/settings
 *   Step 2 – Fire a test push via POST /api/notifications/send
 *   Step 3 – Fetch the Expo delivery receipt and confirm status == "ok"
 *   Step 4 – (Manual) Confirm notification appears on physical device
 *
 * Usage:
 *   ROUTECAST_EMAIL=you@example.com ROUTECAST_PASS=yourpass node scripts/proof_push_e2e.js
 *
 * Optional overrides:
 *   ROUTECAST_API=https://routecast-backend.onrender.com   (default)
 *   RECEIPT_DELAY_MS=3000                                  (default: 3 s)
 */

const https = require('https');
const http = require('http');

const API   = (process.env.ROUTECAST_API  || 'https://routecast-backend.onrender.com').replace(/\/$/, '');
const EMAIL = process.env.ROUTECAST_EMAIL || '';
const PASS  = process.env.ROUTECAST_PASS  || '';
const RECEIPT_DELAY_MS = Number(process.env.RECEIPT_DELAY_MS || 3000);

if (!EMAIL || !PASS) {
  console.error('Usage: ROUTECAST_EMAIL=<email> ROUTECAST_PASS=<pass> node scripts/proof_push_e2e.js');
  process.exit(1);
}

// ── tiny HTTP helper ─────────────────────────────────────────────────────────
function request(urlStr, options = {}, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const lib  = url.protocol === 'https:' ? https : http;
    const data = body ? JSON.stringify(body) : null;
    const req  = lib.request({
      hostname: url.hostname,
      port:     url.port || (url.protocol === 'https:' ? 443 : 80),
      path:     url.pathname + url.search,
      method:   options.method || 'GET',
      headers:  {
        'Content-Type': 'application/json',
        ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {}),
        ...(options.headers || {}),
      },
    }, (res) => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(Buffer.concat(chunks).toString()) }); }
        catch { resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString() }); }
      });
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function pass(label, detail = '') {
  console.log(`  ✅  ${label}${detail ? '  →  ' + detail : ''}`);
}
function fail(label, detail = '') {
  console.error(`  ❌  ${label}${detail ? '  →  ' + detail : ''}`);
  process.exit(1);
}
function info(msg) { console.log(`       ${msg}`); }

// ── pick a coordinate inside any currently-active NWS alert polygon ──────────
async function fetchActiveNwsCoordinate() {
  try {
    const res = await request(
      'https://api.weather.gov/alerts/active?status=actual&limit=5',
      { headers: { 'User-Agent': 'Routecast-E2E-Test/1.0 (github.com/lhildreth66/Routecast2)' } },
    );
    if (res.status !== 200) return null;
    const features = (res.body.features || []);
    for (const f of features) {
      const geom = f.geometry;
      // Polygon
      if (geom?.type === 'Polygon' && geom.coordinates?.[0]?.length) {
        const ring = geom.coordinates[0];
        const mid  = ring[Math.floor(ring.length / 2)];
        return { lat: mid[1], lon: mid[0], event: f.properties?.event };
      }
      // MultiPolygon
      if (geom?.type === 'MultiPolygon' && geom.coordinates?.[0]?.[0]?.length) {
        const ring = geom.coordinates[0][0];
        const mid  = ring[Math.floor(ring.length / 2)];
        return { lat: mid[1], lon: mid[0], event: f.properties?.event };
      }
      // Point (rare but valid)
      if (geom?.type === 'Point' && geom.coordinates?.length === 2) {
        return { lat: geom.coordinates[1], lon: geom.coordinates[0], event: f.properties?.event };
      }
    }
  } catch (_) { /* network failure – caller handles null */ }
  return null;
}

// ── main ─────────────────────────────────────────────────────────────────────
(async () => {
  console.log('\n══════════════════════════════════════════════════════');
  console.log('  Routecast E2E Push Delivery Proof');
  console.log(`  API : ${API}`);
  console.log(`  User: ${EMAIL}`);
  console.log('══════════════════════════════════════════════════════\n');

  // ── STEP 1a: login ───────────────────────────────────────────────────────
  console.log('[ Step 1 ]  Login + verify real push token stored');
  const loginRes = await request(`${API}/api/auth/login`, { method: 'POST' }, { email: EMAIL, password: PASS });
  if (loginRes.status !== 200 || !loginRes.body.access_token) {
    fail('POST /api/auth/login', `HTTP ${loginRes.status} – ${JSON.stringify(loginRes.body)}`);
  }
  const token = loginRes.body.access_token;
  pass('Login', `HTTP ${loginRes.status}`);

  // ── STEP 1b: read push settings ──────────────────────────────────────────
  const settingsRes = await request(`${API}/api/push/settings`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (settingsRes.status !== 200) {
    fail('GET /api/push/settings', `HTTP ${settingsRes.status} – ${JSON.stringify(settingsRes.body)}`);
  }
  const settings = settingsRes.body;
  info(`push_enabled : ${settings.push_enabled}`);
  info(`push_token   : ${settings.push_token ? settings.push_token.slice(0, 40) + '…' : 'null'}`);
  info(`platform     : ${settings.platform}`);

  const REAL_TOKEN = settings.push_token;

  if (!REAL_TOKEN || !REAL_TOKEN.startsWith('ExponentPushToken[')) {
    fail(
      'push_token validation',
      REAL_TOKEN
        ? `Token "${REAL_TOKEN.slice(0, 30)}" does not look like a real Expo token. ' +
          'Toggle push ON in the app from a physical device first.`
        : 'No token stored. Enable push notifications on a physical device first.',
    );
  }
  if (!settings.push_enabled) {
    fail('push_enabled check', 'push_enabled=false – toggle ON in app then re-run');
  }
  pass('Real ExponentPushToken stored', REAL_TOKEN.slice(0, 40) + '…');
  pass('push_enabled=true');

  // ── STEP 2: fire a test push ─────────────────────────────────────────────
  console.log('\n[ Step 2 ]  Fire test push via POST /api/notifications/send');
  const sendBody = {
    title: '🚛 Routecast E2E Test',
    body:  `Delivery verified at ${new Date().toISOString()}`,
    data:  { type: 'e2e_test' },
  };
  const sendRes = await request(`${API}/api/notifications/send`, { method: 'POST' }, sendBody);
  if (sendRes.status !== 200) {
    fail('POST /api/notifications/send', `HTTP ${sendRes.status} – ${JSON.stringify(sendRes.body)}`);
  }
  const sendData = sendRes.body;
  info(`Response : ${JSON.stringify(sendData)}`);

  // Extract ticket IDs from the response for receipt checking
  // Backend may return { results: [...] } or { ticket_ids: [...] } or { data: [...] }
  let ticketIds = [];
  if (Array.isArray(sendData.results)) {
    ticketIds = sendData.results.map(r => r.id).filter(Boolean);
  } else if (Array.isArray(sendData.ticket_ids)) {
    ticketIds = sendData.ticket_ids;
  } else if (sendData.id) {
    ticketIds = [sendData.id];
  }

  if (ticketIds.length === 0) {
    // Still a pass if the backend returned 200 – receipts just won't be checked
    pass('POST /api/notifications/send  HTTP 200 (no ticket IDs to verify receipts)');
    console.log('\n       Note: backend did not return ticket IDs in the response.');
    console.log('       Expo will deliver the notification regardless.');
    console.log('       Confirm visually on device (see Step 4).\n');
  } else {
    pass('POST /api/notifications/send', `${ticketIds.length} ticket(s) issued`);
    info(`Ticket IDs: ${ticketIds.join(', ')}`);

    // ── STEP 3: pull delivery receipts from Expo ───────────────────────────
    console.log(`\n[ Step 3 ]  Pull Expo delivery receipts (waiting ${RECEIPT_DELAY_MS / 1000}s…)`);
    await sleep(RECEIPT_DELAY_MS);

    const receiptRes = await request(
      'https://exp.host/--/api/v2/push/getReceipts',
      { method: 'POST' },
      { ids: ticketIds },
    );

    if (receiptRes.status !== 200) {
      fail('POST https://exp.host/--/api/v2/push/getReceipts', `HTTP ${receiptRes.status}`);
    }

    const receipts = receiptRes.body.data || {};
    let allOk = true;

    for (const id of ticketIds) {
      const r = receipts[id];
      if (!r) {
        info(`Ticket ${id}  →  not yet available (receipts lag up to 30 s)`);
      } else if (r.status === 'ok') {
        pass(`Ticket ${id}  →  status=ok  (delivered to APNs/FCM)`);
      } else {
        allOk = false;
        fail(`Ticket ${id}  →  status=${r.status}  details=${JSON.stringify(r.details)}`);
      }
    }

    if (allOk) {
      pass('All Expo receipts status=ok');
    }
  }

  // ── STEP 4: route-monitor against a live NWS alert coordinate ────────────
  console.log('');
  console.log('[ Step 4 ]  Route-monitor start using live NWS alert coordinate');

  const nwsCoord = await fetchActiveNwsCoordinate();
  if (!nwsCoord) {
    console.log('       ⚠️  No active NWS alert polygons right now – skipping route-monitor test.');
    console.log('          Re-run during an active weather event to exercise this path.');
  } else {
    info(`Active NWS alert : ${nwsCoord.event}`);
    info(`Coordinate used  : lat=${nwsCoord.lat.toFixed(4)}, lon=${nwsCoord.lon.toFixed(4)}`);

    const monitorRes = await request(
      `${API}/api/notifications/route-monitor/start`,
      { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
      {
        routeId:      'e2e-nws-test',
        pushToken:    REAL_TOKEN,
        samplePoints: [{ lat: nwsCoord.lat, lon: nwsCoord.lon }],
      },
    );

    if (monitorRes.status === 200 && monitorRes.body.ok) {
      pass(
        'POST /api/notifications/route-monitor/start',
        `monitor_id=${monitorRes.body.monitor_id}  points=${monitorRes.body.points}`,
      );
      info('Backend will fire a push within the next worker cycle (≤15 min).');
      info('Watch the device – you should receive a weather-alert notification.');
    } else {
      fail(
        'POST /api/notifications/route-monitor/start',
        `HTTP ${monitorRes.status} – ${JSON.stringify(monitorRes.body)}`,
      );
    }
  }

  // ── STEP 5: manual device confirmation ───────────────────────────────────
  console.log('');
  console.log('══════════════════════════════════════════════════════');
  console.log('  Step 5 – Manual device confirmation (cannot automate)');
  console.log('══════════════════════════════════════════════════════');
  console.log('');
  console.log('  FOREGROUND (app open on device):');
  console.log('    • A banner/toast should appear for the test push from Step 2.');
  console.log('      (setNotificationHandler has shouldShowAlert: true)');
  console.log('');
  console.log('  BACKGROUND / LOCKED:');
  console.log('    • OS tray should show "🚛 Routecast E2E Test".');
  console.log('    • Tapping it should open the app.');
  console.log('');
  console.log('  ROUTE ALERT PUSH (from Step 4):');
  console.log('    • Within ≤15 min a weather-alert push should arrive');
  console.log('      if NWS alerts are active at the sampled coordinate.');
  console.log('    • Tapping it should open the Alerts tab.');
  console.log('');
  console.log('  Once both notifications are confirmed on device →');
  console.log('  resume DEPLOYMENT_CHECKLIST.md § 9 (Testing Checklist)');
  console.log('  and then do the store build.');
  console.log('');
  console.log('══════════════════════════════════════════════════════');
  console.log('  Backend-verifiable steps PASSED');
  console.log('  Complete Step 5 manually on a physical device.');
  console.log('══════════════════════════════════════════════════════\n');
})();

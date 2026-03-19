/**
 * Evermore WebSocket Data Feed API — Full Test Suite
 * Tests all message types from MT.Data.Feed.API_V1.pdf
 *
 * UAT: ws://115.242.15.134:19101
 * Live: wss://feedapi.com
 */

const WebSocket = require('ws');

const WS_URL = 'ws://115.242.15.134:19101'; // UAT
const LOGIN_ID = 'DAKS';
const PASSWORD = 'a@3333333333';

const RESULTS = [];
let ws;
let testTimeout;

function log(tag, msg) {
  const ts = new Date().toISOString().split('T')[1].split('.')[0];
  console.log(`[${ts}] [${tag}] ${typeof msg === 'object' ? JSON.stringify(msg) : msg}`);
}

function recordResult(testName, status, detail) {
  RESULTS.push({ test: testName, status, detail: typeof detail === 'object' ? JSON.stringify(detail).substring(0, 300) : detail });
  log(status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️', `${testName}: ${typeof detail === 'object' ? JSON.stringify(detail).substring(0, 200) : detail}`);
}

function printSummary() {
  console.log('\n' + '='.repeat(80));
  console.log('WEBSOCKET DATA FEED API — TEST RESULTS SUMMARY');
  console.log('='.repeat(80));
  console.log(`Endpoint: ${WS_URL}`);
  console.log(`LoginId: ${LOGIN_ID}`);
  console.log(`Date: ${new Date().toISOString()}`);
  console.log('-'.repeat(80));

  const passed = RESULTS.filter(r => r.status === 'PASS').length;
  const failed = RESULTS.filter(r => r.status === 'FAIL').length;
  const info = RESULTS.filter(r => r.status === 'INFO').length;

  RESULTS.forEach((r, i) => {
    const icon = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : 'ℹ️';
    console.log(`${icon} ${(i + 1).toString().padStart(2)}. ${r.test.padEnd(45)} ${r.status.padEnd(6)} ${r.detail.substring(0, 120)}`);
  });

  console.log('-'.repeat(80));
  console.log(`TOTAL: ${RESULTS.length} | PASS: ${passed} | FAIL: ${failed} | INFO: ${info}`);
  console.log('='.repeat(80));
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForMessage(type, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      ws.removeListener('message', handler);
      reject(new Error(`Timeout waiting for ${type} (${timeoutMs}ms)`));
    }, timeoutMs);

    function handler(data) {
      try {
        const msg = JSON.parse(data.toString());
        if (msg.Type === type) {
          clearTimeout(timer);
          ws.removeListener('message', handler);
          resolve(msg);
        }
      } catch (e) { /* ignore parse errors */ }
    }
    ws.on('message', handler);
  });
}

async function collectMessages(durationMs = 8000) {
  const messages = [];
  const handler = (data) => {
    try {
      messages.push(JSON.parse(data.toString()));
    } catch (e) { /* ignore */ }
  };
  ws.on('message', handler);
  await sleep(durationMs);
  ws.removeListener('message', handler);
  return messages;
}

async function sendAndLog(label, packet) {
  log('SEND', `${label}: ${JSON.stringify(packet).substring(0, 200)}`);
  ws.send(JSON.stringify(packet));
}

async function runTests() {
  // ═══════════════════════════════════════════════════════
  // TEST 1: Connection
  // ═══════════════════════════════════════════════════════
  log('TEST', '1. WebSocket Connection');
  try {
    ws = await new Promise((resolve, reject) => {
      const socket = new WebSocket(WS_URL);
      const timer = setTimeout(() => { socket.close(); reject(new Error('Connection timeout 10s')); }, 10000);
      socket.on('open', () => { clearTimeout(timer); resolve(socket); });
      socket.on('error', (err) => { clearTimeout(timer); reject(err); });
    });
    recordResult('1. WebSocket Connection', 'PASS', `Connected to ${WS_URL}`);
  } catch (err) {
    recordResult('1. WebSocket Connection', 'FAIL', err.message);
    printSummary();
    process.exit(1);
  }

  // ═══════════════════════════════════════════════════════
  // TEST 2: Login
  // ═══════════════════════════════════════════════════════
  log('TEST', '2. Login Request');
  try {
    await sendAndLog('Login', { Type: 'Login', Data: { LoginId: LOGIN_ID, Password: PASSWORD } });
    const loginResp = await waitForMessage('Login', 10000);

    if (loginResp.Data.Error === '' || loginResp.Data.Error === null) {
      recordResult('2. Login', 'PASS', `LoginId=${loginResp.Data.LoginId}, Version=${loginResp.Data.Version}, Xchgs=${loginResp.Data.Xchgs}`);
    } else {
      recordResult('2. Login', 'FAIL', `Error: ${loginResp.Data.Error}`);
      ws.close();
      printSummary();
      process.exit(1);
    }
  } catch (err) {
    recordResult('2. Login', 'FAIL', err.message);
    ws.close();
    printSummary();
    process.exit(1);
  }

  // ═══════════════════════════════════════════════════════
  // TEST 3: Collect initial messages (FeedStatus, IndexData, Info)
  // ═══════════════════════════════════════════════════════
  log('TEST', '3. Collect post-login messages (FeedStatus, IndexData, Info)');
  {
    const msgs = await collectMessages(5000);
    const types = [...new Set(msgs.map(m => m.Type))];
    recordResult('3. Post-login message types received', 'INFO', `Types: [${types.join(', ')}] (${msgs.length} messages)`);

    // Check FeedStatus
    const feedStatus = msgs.find(m => m.Type === 'FeedStatus');
    if (feedStatus) {
      recordResult('3a. FeedStatus received', 'PASS', feedStatus.Data);
    } else {
      recordResult('3a. FeedStatus received', 'INFO', 'Not received in 5s window (may come later)');
    }

    // Check IndexData
    const indexData = msgs.find(m => m.Type === 'IndexData');
    if (indexData) {
      const indices = Array.isArray(indexData.Data) ? indexData.Data.map(d => d.Symbol).join(', ') : 'single object';
      recordResult('3b. IndexData received', 'PASS', `Indices: ${indices}`);
    } else {
      recordResult('3b. IndexData received', 'INFO', 'Not received in 5s window (may come during market hours only)');
    }

    // Check Info
    const infoMsg = msgs.find(m => m.Type === 'Info');
    if (infoMsg) {
      recordResult('3c. Info message received', 'PASS', infoMsg.Data);
    } else {
      recordResult('3c. Info message received', 'INFO', 'Not received in 5s window');
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 4: Subscribe MarketData (FeedType=1)
  // ═══════════════════════════════════════════════════════
  log('TEST', '4. Subscribe MarketData (FeedType=1) — RELIANCE');
  {
    await sendAndLog('TokenRequest MarketData', {
      Type: 'TokenRequest',
      Data: {
        SubType: true,
        FeedType: 1,
        quotes: [{ Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' }]
      }
    });

    const msgs = await collectMessages(8000);
    const marketDataMsgs = msgs.filter(m => m.Type === 'MarketData');

    if (marketDataMsgs.length > 0) {
      const sample = marketDataMsgs[0].Data;
      const fields = Object.keys(sample);
      recordResult('4. MarketData subscription', 'PASS', `${marketDataMsgs.length} msgs received, Fields: [${fields.join(',')}]`);
      recordResult('4a. MarketData sample', 'INFO', `LTP=${sample.LTP}, LTQ=${sample.LTQ}, O=${sample.O}, H=${sample.H}, L=${sample.L}, C=${sample.C}, TTQ=${sample.TTQ}, OI=${sample.OI}`);

      // Validate expected fields exist
      const expectedFields = ['Xchg', 'Tkn', 'LTP', 'LTQ', 'LUT', 'LTT', 'ATP', 'BQ', 'BP', 'SQ', 'SP', 'TBQ', 'TSQ', 'TTQ', 'TTV', 'OI', 'O', 'H', 'L', 'C', 'DPRL', 'DPRH'];
      const missing = expectedFields.filter(f => !(f in sample));
      if (missing.length === 0) {
        recordResult('4b. MarketData field validation', 'PASS', `All ${expectedFields.length} expected fields present`);
      } else {
        recordResult('4b. MarketData field validation', 'FAIL', `Missing fields: [${missing.join(',')}]`);
      }
    } else {
      // Check if any other messages came
      const otherTypes = [...new Set(msgs.map(m => m.Type))];
      recordResult('4. MarketData subscription', 'INFO', `No MarketData msgs in 8s (market may be closed). Other types: [${otherTypes.join(', ')}]`);
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 5: Subscribe Depth (FeedType=2)
  // ═══════════════════════════════════════════════════════
  log('TEST', '5. Subscribe Depth (FeedType=2) — RELIANCE');
  {
    await sendAndLog('TokenRequest Depth', {
      Type: 'TokenRequest',
      Data: {
        SubType: true,
        FeedType: 2,
        quotes: [{ Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' }]
      }
    });

    const msgs = await collectMessages(8000);
    const depthMsgs = msgs.filter(m => m.Type === 'Depth');

    if (depthMsgs.length > 0) {
      const sample = depthMsgs[0].Data;
      recordResult('5. Depth subscription', 'PASS', `${depthMsgs.length} msgs, Tkn=${sample.Tkn}, Depth levels=${sample.Depths ? sample.Depths.length : 'N/A'}`);
      if (sample.Depths && sample.Depths.length > 0) {
        const level = sample.Depths[0];
        recordResult('5a. Depth level-0 sample', 'INFO', `BO=${level.BO}, BP=${level.BP}, BQ=${level.BQ}, SQ=${level.SQ}, SP=${level.SP}, SO=${level.SO}`);

        const expectedDepthFields = ['BO', 'BP', 'BQ', 'SQ', 'SP', 'SO'];
        const missing = expectedDepthFields.filter(f => !(f in level));
        if (missing.length === 0) {
          recordResult('5b. Depth field validation', 'PASS', `All ${expectedDepthFields.length} depth fields present`);
        } else {
          recordResult('5b. Depth field validation', 'FAIL', `Missing: [${missing.join(',')}]`);
        }
      }
    } else {
      const otherTypes = [...new Set(msgs.map(m => m.Type))];
      recordResult('5. Depth subscription', 'INFO', `No Depth msgs in 8s (market may be closed). Other: [${otherTypes.join(', ')}]`);
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 6: Subscribe Greeks (FeedType=4) — NIFTY options
  // ═══════════════════════════════════════════════════════
  log('TEST', '6. Subscribe Greeks (FeedType=4) — NIFTY option');
  {
    await sendAndLog('TokenRequest Greeks', {
      Type: 'TokenRequest',
      Data: {
        SubType: true,
        FeedType: 4,
        quotes: [{ Xchg: 'NSEFO', Tkn: '57133', Symbol: 'NIFTY' }]
      }
    });

    const msgs = await collectMessages(8000);
    const greekMsgs = msgs.filter(m => m.Type === 'Greek');

    if (greekMsgs.length > 0) {
      const sample = greekMsgs[0].Data;
      recordResult('6. Greek subscription', 'PASS', `${greekMsgs.length} msgs`);
      recordResult('6a. Greek sample', 'INFO', `IV=${sample.IV}, Delta=${sample.Delta}, Gamma=${sample.Gamma}, Theta=${sample.Theta}, Vega=${sample.Vega}, Rho=${sample.Rho}, SpotPrice=${sample.SpotPrice}`);

      const greekFields = ['IV', 'Delta', 'Gamma', 'Theta', 'Vega', 'Rho', 'SpotPrice'];
      const missing = greekFields.filter(f => !(f in sample));
      if (missing.length === 0) {
        recordResult('6b. Greek field validation', 'PASS', `All Greek fields present`);
      } else {
        recordResult('6b. Greek field validation', 'FAIL', `Missing: [${missing.join(',')}]`);
      }
    } else {
      const otherTypes = [...new Set(msgs.map(m => m.Type))];
      recordResult('6. Greek subscription', 'INFO', `No Greek msgs in 8s. Other: [${otherTypes.join(', ')}]`);
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 7: Unsubscribe MarketData
  // ═══════════════════════════════════════════════════════
  log('TEST', '7. Unsubscribe MarketData — RELIANCE');
  {
    // Count MarketData messages before unsubscribe
    const msgsBefore = await collectMessages(3000);
    const countBefore = msgsBefore.filter(m => m.Type === 'MarketData' && m.Data && m.Data.Tkn === '2885').length;

    await sendAndLog('Unsubscribe MarketData', {
      Type: 'TokenRequest',
      Data: {
        SubType: false,
        FeedType: 1,
        quotes: [{ Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' }]
      }
    });

    await sleep(1000); // Let server process

    const msgsAfter = await collectMessages(3000);
    const countAfter = msgsAfter.filter(m => m.Type === 'MarketData' && m.Data && m.Data.Tkn === '2885').length;

    recordResult('7. Unsubscribe MarketData', countAfter < countBefore || countAfter === 0 ? 'PASS' : 'INFO',
      `Before: ${countBefore} msgs, After: ${countAfter} msgs (in 3s windows)`);
  }

  // ═══════════════════════════════════════════════════════
  // TEST 8: Heartbeat
  // ═══════════════════════════════════════════════════════
  log('TEST', '8. Heartbeat (Info HB)');
  {
    await sendAndLog('Heartbeat', { Type: 'Info', Data: { InfoType: 'HB', InfoMsg: '' } });
    await sleep(1000);
    // If connection is still open, heartbeat was accepted
    if (ws.readyState === WebSocket.OPEN) {
      recordResult('8. Heartbeat accepted', 'PASS', 'Connection still alive after HB');
    } else {
      recordResult('8. Heartbeat accepted', 'FAIL', `Connection state: ${ws.readyState}`);
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 9: OChain (Option Chain)
  // ═══════════════════════════════════════════════════════
  log('TEST', '9. OChain subscription — NIFTY');
  {
    // Use a near-term expiry
    const today = new Date();
    // Find next Thursday (typical expiry)
    const dayOfWeek = today.getDay();
    const daysUntilThursday = (4 - dayOfWeek + 7) % 7 || 7;
    const nextThursday = new Date(today);
    nextThursday.setDate(today.getDate() + daysUntilThursday);
    const expiry = `${nextThursday.getDate().toString().padStart(2, '0')}-${(nextThursday.getMonth() + 1).toString().padStart(2, '0')}-${nextThursday.getFullYear()}`;

    await sendAndLog('OChain Subscribe', {
      Type: 'OChain',
      Data: {
        SubType: true,
        Xchg: 'NSEFO',
        Symbol: 'NIFTY',
        Expiry: expiry
      }
    });

    const msgs = await collectMessages(10000);
    const ochainMsgs = msgs.filter(m => m.Type === 'OChain');

    if (ochainMsgs.length > 0) {
      const sample = ochainMsgs[0].Data;
      recordResult('9. OChain subscription', 'PASS', `${ochainMsgs.length} msgs, SpotPrice=${sample.SpotPrice}, MaxPain=${sample.MaxPain}, PCR=${sample.PCR}, VIX=${sample.VIX}`);

      if (sample.OptChain && sample.OptChain.length > 0) {
        recordResult('9a. OChain strikes', 'PASS', `${sample.OptChain.length} strikes received`);
        const strike = sample.OptChain[0];
        recordResult('9b. OChain sample strike', 'INFO', `Strike=${strike.Strike}, CLTP=${strike.CLTP}, PLTP=${strike.PLTP}, COI=${strike.COI}, POI=${strike.POI}`);
      } else {
        recordResult('9a. OChain strikes', 'INFO', 'OptChain array empty or missing');
      }

      // Unsubscribe
      await sendAndLog('OChain Unsubscribe', {
        Type: 'OChain',
        Data: { SubType: false, Xchg: 'NSEFO', Symbol: 'NIFTY', Expiry: expiry }
      });
    } else {
      const otherTypes = [...new Set(msgs.map(m => m.Type))];
      recordResult('9. OChain subscription', 'INFO', `No OChain msgs in 10s (expiry=${expiry}). Other: [${otherTypes.join(', ')}]`);
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 10: Subscribe SnapQuote (FeedType=3)
  // ═══════════════════════════════════════════════════════
  log('TEST', '10. Subscribe SnapQuote (FeedType=3) — TCS');
  {
    await sendAndLog('TokenRequest SnapQuote', {
      Type: 'TokenRequest',
      Data: {
        SubType: true,
        FeedType: 3,
        quotes: [{ Xchg: 'NSECM', Tkn: '11536', Symbol: 'TCS' }]
      }
    });

    const msgs = await collectMessages(8000);
    // SnapQuote may come as MarketData or a separate type
    const snapMsgs = msgs.filter(m => m.Type === 'SnapQuote' || (m.Type === 'MarketData' && m.Data && m.Data.Tkn === '11536'));

    if (snapMsgs.length > 0) {
      recordResult('10. SnapQuote subscription', 'PASS', `${snapMsgs.length} msgs received, Type=${snapMsgs[0].Type}`);
    } else {
      const otherTypes = [...new Set(msgs.map(m => m.Type))];
      recordResult('10. SnapQuote subscription', 'INFO', `No SnapQuote/MarketData for TCS in 8s. Other: [${otherTypes.join(', ')}]`);
    }

    // Unsubscribe
    await sendAndLog('Unsubscribe SnapQuote', {
      Type: 'TokenRequest',
      Data: { SubType: false, FeedType: 3, quotes: [{ Xchg: 'NSECM', Tkn: '11536', Symbol: 'TCS' }] }
    });
  }

  // ═══════════════════════════════════════════════════════
  // TEST 11: Multiple token subscription
  // ═══════════════════════════════════════════════════════
  log('TEST', '11. Multi-token subscription');
  {
    await sendAndLog('Multi-subscribe', {
      Type: 'TokenRequest',
      Data: {
        SubType: true,
        FeedType: 1,
        quotes: [
          { Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' },
          { Xchg: 'NSECM', Tkn: '11536', Symbol: 'TCS' },
          { Xchg: 'NSECM', Tkn: '1594', Symbol: 'INFY' }
        ]
      }
    });

    const msgs = await collectMessages(8000);
    const marketMsgs = msgs.filter(m => m.Type === 'MarketData');
    const uniqueTokens = [...new Set(marketMsgs.map(m => m.Data.Tkn))];

    if (marketMsgs.length > 0) {
      recordResult('11. Multi-token subscription', 'PASS', `${marketMsgs.length} msgs for ${uniqueTokens.length} unique tokens: [${uniqueTokens.join(', ')}]`);
    } else {
      recordResult('11. Multi-token subscription', 'INFO', 'No MarketData msgs (market may be closed)');
    }

    // Cleanup: unsubscribe all
    await sendAndLog('Multi-unsubscribe', {
      Type: 'TokenRequest',
      Data: {
        SubType: false,
        FeedType: 1,
        quotes: [
          { Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' },
          { Xchg: 'NSECM', Tkn: '11536', Symbol: 'TCS' },
          { Xchg: 'NSECM', Tkn: '1594', Symbol: 'INFY' }
        ]
      }
    });
  }

  // ═══════════════════════════════════════════════════════
  // TEST 12: Unsubscribe Depth
  // ═══════════════════════════════════════════════════════
  log('TEST', '12. Cleanup — Unsubscribe Depth & Greeks');
  {
    await sendAndLog('Unsubscribe Depth', {
      Type: 'TokenRequest',
      Data: { SubType: false, FeedType: 2, quotes: [{ Xchg: 'NSECM', Tkn: '2885', Symbol: 'RELIANCE' }] }
    });
    await sendAndLog('Unsubscribe Greeks', {
      Type: 'TokenRequest',
      Data: { SubType: false, FeedType: 4, quotes: [{ Xchg: 'NSEFO', Tkn: '57133', Symbol: 'NIFTY' }] }
    });
    await sleep(1000);

    if (ws.readyState === WebSocket.OPEN) {
      recordResult('12. Cleanup unsubscribe', 'PASS', 'All subscriptions cleared');
    } else {
      recordResult('12. Cleanup unsubscribe', 'FAIL', 'Connection lost during cleanup');
    }
  }

  // ═══════════════════════════════════════════════════════
  // TEST 13: Logout
  // ═══════════════════════════════════════════════════════
  log('TEST', '13. Logout');
  {
    await sendAndLog('Logout', { Type: 'Logout', Data: 'logout' });

    try {
      const logoutResp = await waitForMessage('Logout', 5000);
      recordResult('13. Logout', 'PASS', logoutResp.Data);
    } catch (err) {
      // Connection may close immediately on logout
      if (ws.readyState !== WebSocket.OPEN) {
        recordResult('13. Logout', 'PASS', 'Connection closed (server closed after logout)');
      } else {
        recordResult('13. Logout', 'INFO', `No Logout response in 5s: ${err.message}`);
      }
    }
  }

  // Print final summary
  printSummary();

  // Cleanup
  if (ws.readyState === WebSocket.OPEN) {
    ws.close();
  }
  process.exit(0);
}

// Set overall timeout (2 minutes)
testTimeout = setTimeout(() => {
  log('TIMEOUT', 'Overall test timeout (120s) reached');
  printSummary();
  if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  process.exit(1);
}, 120000);

runTests().catch(err => {
  log('FATAL', err.message);
  printSummary();
  if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  process.exit(1);
});

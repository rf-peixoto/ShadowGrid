/* The gate: solve the server's proof of work on every core (Web Workers), show real progress, then go on to sign-in. */
(() => {
  const $ = id => document.getElementById(id);
  const next = document.body.dataset.next || '/login';
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const LEGENDS = [
    'Connecting to the Matrix', 'Handshaking with the grid', 'Spoofing your datatrail', 'Slipping past the GOD watchlist',
    'Compiling your persona', 'Loading the host sculpture', 'Negotiating with the spider', 'Decrypting the access node',
    'Bouncing through three proxies', 'Calibrating the trodes', 'Masking your commlink ID', 'Reticulating the ICE',
    'Waking the agent', 'Syncing with the grid overwatch clock',
  ];
  const GLYPHS = '01アイウエオカキクケコサシスセソ#%&$@<>/\\[]{}=+*';

  // ------------------------------------------------------------------ text glitches
  let legendTimer = 0, legendIdx = 0;
  function scramble(el, text, ms = 420) {
    if (calm) { el.textContent = text; return; }
    const t0 = performance.now();
    const step = t => {
      const k = Math.min(1, (t - t0) / ms), keep = Math.floor(text.length * k);
      el.textContent = text.slice(0, keep) + [...text.slice(keep)].map(c => c === ' ' ? ' ' : GLYPHS[Math.random() * GLYPHS.length | 0]).join('');
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  function rotateLegend() {
    legendIdx = (legendIdx + 1 + (Math.random() * 3 | 0)) % LEGENDS.length;
    scramble($('gate-legend'), LEGENDS[legendIdx] + '…');
    legendTimer = setTimeout(rotateLegend, 2800 + Math.random() * 1800);
  }
  let glitchTimer = 0;
  function glitch() {
    const g = $('gate');
    g.style.setProperty('--gx', `${(Math.random() * 10 - 5).toFixed(1)}px`);
    g.style.setProperty('--gy', `${(Math.random() * 60 + 10).toFixed(0)}%`);
    g.classList.add('glitch');
    setTimeout(() => g.classList.remove('glitch'), 120 + Math.random() * 160);
    glitchTimer = setTimeout(glitch, 1400 + Math.random() * 4200);
  }

  // ------------------------------------------------------------------ progress
  const log = line => {
    const ol = $('gate-log'), li = document.createElement('li');
    li.textContent = line; ol.prepend(li);
    while (ol.children.length > 5) ol.lastChild.remove();
  };
  const fmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(0) + 'k' : String(n);
  function setProgress(p) {
    const pct = Math.floor(p * 100);
    $('gate-fill').style.width = (p * 100).toFixed(2) + '%';
    $('gate-pct').textContent = pct + '%';
    $('gate-sectors').setAttribute('aria-valuenow', pct);
  }

  // ------------------------------------------------------------------ the work
  let workers = [];
  function stop() { workers.forEach(w => w.terminate()); workers = []; clearTimeout(legendTimer); clearTimeout(glitchTimer); }

  function fail(text) {
    stop();
    $('gate-legend').textContent = 'Connection dropped';
    $('gate-hint').textContent = text;
    $('gate-retry').hidden = false;
    $('gate').classList.add('failed');
  }

  async function run() {
    $('gate-retry').hidden = true; $('gate').classList.remove('failed');
    $('gate-hint').textContent = "Your device is proving it isn't a bot. It runs once per sign-in and can take a minute on a phone. Keep this tab open.";
    if (!window.Worker) return fail('This browser cannot run the connection check. Try a current Chrome, Firefox, Edge or Safari.');
    let ch;
    try {
      const r = await fetch('/api/gate/challenge', { cache: 'no-store' });
      if (r.status === 429) return fail('Too many connection attempts from here. Wait a minute and try again.');
      ch = await r.json();
    } catch (e) { return fail('Could not reach the server. Check your connection and try again.'); }

    const total = ch.puzzles, per = 2 ** ch.bits, expected = total * per;
    const cells = $('gate-sectors'); cells.replaceChildren();
    for (let i = 0; i < total; i++) { const c = document.createElement('i'); cells.append(c); }
    const counters = new Array(total).fill(null);
    let nextIdx = 0, solved = 0, hashes = 0, active = 0;
    const samples = [];               // [time, hashes] for the speed readout
    const t0 = performance.now();
    legendIdx = 0; scramble($('gate-legend'), LEGENDS[0] + '…');
    legendTimer = setTimeout(rotateLegend, 3000);
    if (!calm) glitchTimer = setTimeout(glitch, 900);
    log(`> jack-in request ${ch.challenge.slice(0, 8)} · ${total} sectors`);

    const update = () => {
      const now = performance.now();
      samples.push([now, hashes]);
      while (samples.length > 2 && now - samples[0][0] > 4000) samples.shift();
      const [ts, hs] = samples[0], rate = now > ts ? (hashes - hs) / ((now - ts) / 1000) : 0;
      const p = solved === total ? 1 : Math.max(solved / total, Math.min(hashes / expected, (solved + active) / total) * 0.995);
      setProgress(p);
      if (rate > 0) {
        $('gate-rate').textContent = `${fmt(rate)} hashes/s · ${workers.length} cores`;
        const left = Math.max(0, (total - solved) * per - Math.max(0, hashes - solved * per)) / rate;
        $('gate-eta').textContent = solved === total ? '' : left > 1 ? `about ${left > 90 ? Math.round(left / 60) + ' min' : Math.ceil(left) + ' s'} left` : 'almost there';
      }
    };

    const give = w => {
      if (nextIdx >= total) { w.idle = true; return; }
      const i = nextIdx++;
      w.job = i; active++;
      cells.children[i].className = 'work';
      w.postMessage({ prefix: `${ch.challenge}:${i}:`, bits: ch.bits });
    };

    const done = new Promise((resolve, reject) => {
      const n = Math.max(1, Math.min(navigator.hardwareConcurrency || 2, 8));
      for (let k = 0; k < n; k++) {
        let w;
        try { w = new Worker(document.body.dataset.worker); } catch (e) { reject(e); return; }
        w.onmessage = e => {
          const m = e.data;
          if (m.type === 'tick') { hashes += m.hashes; return; }
          hashes += m.hashes; counters[w.job] = m.counter; solved++; active--;
          cells.children[w.job].className = 'done';
          if (Math.random() < 0.6 || solved === total) log(`> sector ${w.job.toString(16).toUpperCase().padStart(2, '0')} decrypted · nonce ${m.counter}`);
          update();
          if (solved === total) resolve(); else give(w);
        };
        w.onerror = () => reject(new Error('worker'));
        workers.push(w); give(w);
      }
    });
    const ticker = setInterval(update, 250);
    try { await done; } catch (e) { clearInterval(ticker); return fail('The connection check stopped unexpectedly. Try again.'); }
    clearInterval(ticker); stop(); update();
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    log(`> all sectors clean in ${secs} s`);
    scramble($('gate-legend'), 'Uploading proof to the host…', 300);
    try {
      const r = await fetch('/api/gate', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'ShadowGrid' },
        body: JSON.stringify({ challenge: ch.challenge, counters, next }) });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) return fail(data.error || 'The host rejected the proof. Try again.');
      $('gate').classList.add('granted');
      scramble($('gate-legend'), 'Access granted', 360);
      $('gate-hint').textContent = 'Opening the sign-in page…';
      setTimeout(() => { location.replace(data.next || next); }, calm ? 200 : 700);
    } catch (e) { fail('Could not reach the server. Check your connection and try again.'); }
  }

  $('gate-retry').onclick = run;
  run();
})();

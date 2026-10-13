/* Game music: plays the gamemaster's current track in sync with everyone else in the game.

   The server keeps one shared timeline per game (track + start time); the player here plays that track
   from the same moment as everyone else and corrects drift.

   Two parts:
   - the engine owns the <audio> element. The app pages run inside a thin persistent frame (shell.html),
     and the engine lives in that frame, so the music keeps playing while you move between screens
     (browsers only allow sound on a newly loaded page after a click or a key press there);
   - the control in each page's header bar: Music.mount({ host, gm, game, map }).
   Only one tab per browser plays at a time. Only the mute button mutes. */
(() => {
  'use strict';
  const LS = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
  };

  // ================================================================ engine
  function createEngine() {
    const tabId = Math.random().toString(36).slice(2);
    const chan = 'BroadcastChannel' in window ? new BroadcastChannel('sg-music') : null;
    const audio = new Audio();
    audio.preload = 'auto';
    const canOpus = !!audio.canPlayType && audio.canPlayType('audio/webm; codecs="opus"') !== '';
    const S = {
      ctx: null, state: null, skew: 0, bestRtt: Infinity, src: null, key: null,
      on: LS.get('sg.music.on', '1') === '1', vol: +LS.get('sg.music.vol', '0.6'),
      blocked: false, elsewhere: false, startTimer: 0, tracks: [], gameId: null,
    };
    audio.volume = Math.max(0, Math.min(1, S.vol));
    const subs = new Set();
    const emit = () => { for (const fn of [...subs]) { try { fn(); } catch { subs.delete(fn); } } };

    const serverNow = () => Date.now() / 1000 + S.skew;
    function position() {
      const p = S.state && S.state.playing; if (!p) return null;
      let t = serverNow() - p.startedAt;
      const dur = isFinite(audio.duration) && audio.duration > 0 ? audio.duration : p.duration;
      if (t < 0) return t;
      if (dur) { if (p.loop) t %= dur; else if (t >= dur) return Infinity; }
      return t;
    }
    const wanted = () => !!(S.on && !S.elsewhere && S.state && S.state.playing);

    function sync(force) {
      clearTimeout(S.startTimer);
      const p = S.state && S.state.playing;
      if (!p) { stopAudio(); emit(); return; }
      const key = p.trackId + '@' + p.startedAt;
      const src = canOpus ? p.src.opus : p.src.aac;
      if (S.src !== src) { S.src = src; audio.src = src; }
      audio.loop = !!p.loop;
      if (!wanted()) { audio.pause(); emit(); return; }
      const t = position();
      if (t === Infinity) { audio.pause(); emit(); return; }
      if (t < 0) {                       // the GM's start is a moment away: everyone begins together
        audio.pause(); audio.currentTime = 0;
        S.startTimer = setTimeout(() => sync(true), Math.min(5000, -t * 1000));
        emit(); return;
      }
      const drift = Math.abs((audio.currentTime || 0) - t);
      if (force || S.key !== key || drift > 0.75) { try { audio.currentTime = t; } catch { /* not seekable yet */ } }
      S.key = key;
      if (audio.paused) {
        audio.play().then(() => { S.blocked = false; claim(); emit(); })
          .catch(e => { if (e && e.name === 'NotAllowedError') { S.blocked = true; emit(); } });
      }
      emit();
    }
    function stopAudio() {
      audio.pause(); S.key = null;
      if (S.src) { S.src = null; audio.removeAttribute('src'); audio.load(); }
    }
    audio.addEventListener('loadedmetadata', () => { if (wanted()) sync(true); });
    for (const ev of ['play', 'pause', 'ended']) audio.addEventListener(ev, emit);
    setInterval(() => { if (wanted() && !audio.paused && !audio.seeking) sync(false); }, 4000);
    // something else paused it (a phone call, the system, a hidden tab on a phone): pick up when back
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });

    function claim() { if (chan) chan.postMessage({ type: 'claim', id: tabId }); }
    if (chan) {
      chan.onmessage = e => {
        const m = e.data || {};
        if (m.type === 'claim' && m.id !== tabId && !audio.paused) { S.elsewhere = true; audio.pause(); emit(); }
        if (m.type === 'release' && S.elsewhere) { S.elsewhere = false; sync(true); }
      };
      addEventListener('pagehide', () => { if (!audio.paused) chan.postMessage({ type: 'release', id: tabId }); });
    }

    async function refresh() {
      if (!S.ctx) return;
      const q = S.ctx.map ? `?map=${encodeURIComponent(S.ctx.map)}` : S.ctx.game ? `?game=${encodeURIComponent(S.ctx.game)}` : '';
      const t0 = Date.now();
      let d;
      try { d = await api('/api/music/now' + q); } catch { return; }
      const rtt = Date.now() - t0;
      if (rtt <= S.bestRtt * 1.5 || Math.abs(d.serverNow - (t0 + rtt / 2) / 1000 - S.skew) > 2) {
        S.bestRtt = Math.min(S.bestRtt, rtt);
        S.skew = d.serverNow - (t0 + rtt / 2) / 1000;
      }
      const before = S.state && S.state.playing, after = d.playing;
      S.state = d;
      if (d.tracks) S.tracks = d.tracks;
      if (d.gameId) S.gameId = d.gameId;
      if (after && (!before || before.trackId !== after.trackId || before.startedAt !== after.startedAt)) S.elsewhere = false;
      sync(!before || !after || before.startedAt !== after.startedAt);
    }
    setInterval(() => { if (!document.hidden) refresh(); }, 60000);   // safety net for screens without live updates

    const gid = () => S.gameId || (S.ctx && S.ctx.game);
    return {
      audio, S,
      subscribe(fn) { subs.add(fn); return () => subs.delete(fn); },
      refresh,
      setContext(ctx) {
        const same = S.ctx && S.ctx.gm === ctx.gm && S.ctx.game === ctx.game && S.ctx.map === ctx.map;
        if (!same) S.ctx = ctx;
        return refresh();
      },
      // a click or key press on any screen: start the music if the browser was holding it back
      unlock() { if (S.blocked && wanted()) { S.blocked = false; sync(true); } },
      listenHere() { S.blocked = false; S.elsewhere = false; sync(true); },
      setOn(on) { S.on = !!on; LS.set('sg.music.on', S.on ? '1' : '0'); S.elsewhere = false; if (!S.on) audio.pause(); sync(true); },
      setVolume(v) { S.vol = Math.max(0, Math.min(1, +v)); audio.volume = S.vol; LS.set('sg.music.vol', String(S.vol)); emit(); },
      async play(track, loop) { const d = await api(`/api/games/${gid()}/music/play`, 'POST', { track, loop }); S.elsewhere = false; await refresh(); return d; },
      async setLoop(loop) { await api(`/api/games/${gid()}/music/play`, 'POST', { loop }); await refresh(); },
      async stop() { await api(`/api/games/${gid()}/music/stop`, 'POST', {}); await refresh(); },
    };
  }

  // The persistent frame creates the engine; pages inside it borrow that one.
  if (document.documentElement.dataset.shell !== undefined) {
    window.SGShell = Object.assign(window.SGShell || {}, { engine: createEngine() });
    return;
  }
  function shellEngine() {
    try { if (window.parent !== window && window.parent.SGShell && window.parent.SGShell.engine) return window.parent.SGShell.engine; } catch { /* not ours */ }
    return null;
  }
  let engine = null;
  const E = () => engine || (engine = shellEngine() || createEngine());

  // ================================================================ the control in the header
  const fmt = s => s == null ? '' : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  function mount(opts) {
    const eng = E(), S = eng.S, audio = eng.audio;
    let pop = null;
    const vol = h('input.music-vol', { type: 'range', min: 0, max: 1, step: 0.05, value: S.vol, 'aria-label': 'Music volume',
      oninput: e => eng.setVolume(e.target.value) });
    const root = h('div.music-chip', { role: 'group', 'aria-label': 'Music' },
      h('button.music-toggle', { type: 'button', 'aria-pressed': 'true', onclick: () => eng.setOn(!S.on) }, h('span.eq', h('i'), h('i'), h('i'))),
      opts.gm
        ? h('button.music-title.linkish', { type: 'button', 'aria-haspopup': 'true', onclick: e => { e.stopPropagation(); pop.hidden = !pop.hidden; if (!pop.hidden) { eng.refresh(); drawPop(); } } })
        : h('span.music-title'),
      h('button.small.primary.music-tap', { type: 'button', hidden: true, onclick: () => eng.listenHere() }, 'Tap to listen'),
      vol);
    function draw() {
      const p = S.state && S.state.playing;
      root.hidden = !opts.gm && !p;
      root.classList.toggle('playing', !!p && !audio.paused);
      root.classList.toggle('off', !S.on);
      const title = root.querySelector('.music-title');
      title.textContent = p ? p.title : 'No music';
      title.title = p ? `${p.title}${p.loop ? ' (looping)' : ''}` : '';
      const tap = root.querySelector('.music-tap');
      tap.hidden = !(p && S.on && (S.blocked || S.elsewhere));
      tap.textContent = S.elsewhere ? 'Play here' : 'Tap to listen';
      tap.title = S.elsewhere ? 'The music plays in another tab' : 'Your browser waits for a click before it plays sound (any click or key works)';
      const tog = root.querySelector('.music-toggle');
      tog.setAttribute('aria-pressed', S.on ? 'true' : 'false');
      tog.title = S.on ? 'Music on (click to mute on this device)' : 'Music muted on this device (click to turn on)';
      if (+vol.value !== S.vol) vol.value = S.vol;
      if (pop && !pop.hidden) drawPop();
    }
    function drawPop() {
      const p = S.state && S.state.playing;
      pop.replaceChildren(
        h('div.music-pop-head', h('strong', p ? p.title : 'Nothing playing'),
          p ? h('label.check', h('input', { type: 'checkbox', checked: p.loop, onchange: e => eng.setLoop(e.target.checked).catch(err => toast(err.message)) }), 'Loop') : null,
          p ? h('button.small.danger', { type: 'button', onclick: () => eng.stop().catch(err => toast(err.message)) }, 'Stop') : null),
        S.tracks.length
          ? h('ul.music-pop-list', S.tracks.map(t => h('li', { class: p && p.trackId === t.id ? 'current' : '' },
              h('button.small', { type: 'button', title: 'Play for everyone', onclick: () => eng.play(t.id, true).catch(err => toast(err.message)) }, p && p.trackId === t.id ? 'Restart' : 'Play'),
              h('span.grow', t.title), h('span.hint.num', fmt(t.duration)))))
          : h('p.hint', 'No tracks yet.'),
        S.gameId ? h('a.small', { href: `/game/${S.gameId}#music` }, 'Upload and manage music') : null);
    }
    if (opts.gm) {
      pop = h('div.music-pop', { hidden: true, onclick: e => e.stopPropagation() });
      root.append(pop);
      document.addEventListener('click', () => { pop.hidden = true; });
      document.addEventListener('keydown', e => { if (e.key === 'Escape') pop.hidden = true; });
    }
    opts.host.prepend(root);
    const unsub = eng.subscribe(draw);
    addEventListener('pagehide', unsub);
    draw();
    eng.setContext({ gm: !!opts.gm, game: opts.game || null, map: opts.map || null });
    Live.on(() => eng.refresh());
    attach();
  }
  // Screens without a music control: any click, tap or key press there still lets a blocked player start
  // (phones only count some of these events as a "gesture").
  let attached = false;
  function attach() {
    if (attached) return; attached = true;
    const eng = E();
    for (const ev of ['pointerdown', 'pointerup', 'touchend', 'click', 'keydown']) document.addEventListener(ev, () => eng.unlock(), { capture: true, passive: true });
  }

  const api_ = {
    mount, attach,
    refresh: () => E().refresh(),
    play: (t, l) => E().play(t, l),
    stop: () => E().stop(),
    setLoop: l => E().setLoop(l),
    onChange: fn => {
      const eng = E(); let last;
      const un = eng.subscribe(() => { if (eng.S.state !== last) { last = eng.S.state; fn(last); } });
      addEventListener('pagehide', un);
    },
    state: () => E().S.state,
    get audio() { return E().audio; },
  };
  window.Music = api_;
})();

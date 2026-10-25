/* Player app: map (player view), character sheet, store, runs and wiki in one page. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
const S = {
  st: null, view: 'map', sheet: null, sheetRev: null, runsSig: '', storeCat: 'All',
  // map
  map: null, explored: new Set(), hover: null, drag: null, spaceDown: false, busy: false,
  fitted: false, lastMapId: null, sceneDirty: true, sceneZoom: 1, frame: null, pathCache: null, ghost: null, pingFrame: null, lastTap: 0, clockSkew: 0, iso: {}, sceneIso: null,
};
let CAT = null, sheetUI = null, mapRoller = null;
const post = (path, body) => api('/api/me/' + path, 'POST', Object.assign({ cellsSig: S.cellsSig || '' }, body || {}));

// ================================================================ tabs
function setView(v) {
  if (!['map', 'sheet', 'store', 'runs', 'handouts', 'wiki'].includes(v)) v = 'map';
  S.view = v;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  document.querySelectorAll('.view').forEach(s => s.classList.toggle('active', s.id === 'view-' + v));
  if (location.hash !== '#' + v) history.replaceState(null, '', '#' + v);
  if (v === 'map') { requestDraw(); }
  if (v === 'sheet' && sheetUI) sheetUI.render();
  if (v === 'store') renderStore();
  if (v === 'runs') loadRuns();
  if (v === 'handouts') renderHandouts();
}
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => setView(b.dataset.view));
document.addEventListener('click', e => { const g = e.target.closest('[data-goto]'); if (g) setView(g.dataset.goto); });
window.addEventListener('hashchange', () => setView(location.hash.slice(1)));

// account menu
$('btn-account').onclick = e => { e.stopPropagation(); $('account-menu').hidden = !$('account-menu').hidden; };
document.addEventListener('click', e => { if (!e.target.closest('.menu')) $('account-menu').hidden = true; });
$('btn-password').onclick = async () => {
  $('account-menu').hidden = true;
  const cur = h('input', { type: 'password', autocomplete: 'current-password', required: true });
  const nw = h('input', { type: 'password', autocomplete: 'new-password', minlength: 8, required: true });
  const ok = await UI.modal('Change password', h('div', h('label.stack', 'Current password', cur), h('label.stack', 'New password (8+ characters)', nw)), { ok: 'Change', narrow: true });
  if (!ok) return;
  try { await post('password', { current: cur.value, new: nw.value }); toast('Password changed.'); } catch (e) { toast(e.message); }
};

// ================================================================ header chips
function renderChips() {
  const me = S.st && S.st.me; if (!me) return;
  $('me-name').textContent = me.name; $('me-dot').style.background = me.color; $('drawer-name').textContent = me.name;
  $('game-name').textContent = S.st.game.name;
  $('chip-karma').textContent = me.karma;
  $('chip-nuyen').textContent = money(me.nuyen);
  $('chip-edge').textContent = `${me.edge.cur}/${me.edge.max}`;
  $('chip-edge-pips').replaceChildren(SR.pips(me.edge.cur, me.edge.max));
  const st = me.cm.status;
  $('chip-health').replaceChildren(h('span.k', 'Health'), h('b', { class: st === 'OK' ? 'good' : st === 'Wounded' ? 'warn' : 'bad' }, st === 'OK' ? 'OK' : st),
    me.cm.wound ? h('span.hint', ` ${me.cm.wound} dice`) : '');
  $('badge-sheet').hidden = me.status === 'approved';
  $('badge-sheet').textContent = me.status === 'waiting' ? '…' : '!';
  $('badge-sheet').title = me.status === 'waiting' ? 'Waiting for GM approval' : 'Finish your character and submit it';
  $('badge-runs').hidden = !S.st.activeRuns; $('badge-runs').textContent = S.st.activeRuns;
  $('store-nuyen').textContent = money(me.nuyen);
  document.title = `${me.name} · ShadowGrid`;
}

// ================================================================ state polling
async function refresh(force) {
  if (!force && (document.hidden || S.busy || S.drag)) return;
  try {
    const st = await api('/api/me/state?since=' + encodeURIComponent(force ? '' : (S.st ? S.st.version : '')) + '&cells=' + encodeURIComponent(force ? '' : (S.cellsSig || '')));
    if (st.unchanged) return;
    applyState(st);
  } catch (e) { /* transient */ }
}
function applyState(st) {
  S.st = st;
  if (st.view.now) S.clockSkew = Date.now() / 1000 - st.view.now;
  renderChips();
  applyView(st.view);
  renderPlayerLog(st.rolls);
  if (sheetUI) sheetUI.updateLog(st.rolls);
  if (st.sheetRev !== S.sheetRev) {
    S.sheetRev = st.sheetRev;
    if (sheetUI && !sheetUI.editing()) sheetUI.reload();
  }
  const sig = JSON.stringify(st.runsSig) + JSON.stringify(st.sessionsSig || []);
  if (sig !== S.runsSig) { S.runsSig = sig; if (S.view === 'runs') loadRuns(); }
  const hsig = JSON.stringify((st.handouts || []).map(x => [x.id, x.updatedAt]));
  if (hsig !== S.handoutsSig) { S.handoutsSig = hsig; renderHandouts(); }
}

// ================================================================ handouts
function seenHandouts() { try { return JSON.parse(localStorage.getItem('sg.seenHandouts') || '{}') || {}; } catch { return {}; } }
/* handouts are collapsed cards, newest first; one counts as read once it's been opened ([NEW] until then) */
function handoutBadge() {
  const list = (S.st && S.st.handouts) || [], seen = seenHandouts();
  const unread = list.filter(x => seen[x.id] !== x.updatedAt);
  const badge = $('badge-handouts');
  badge.hidden = !unread.length; badge.textContent = unread.length;
  return unread;
}
function renderHandouts() {
  const list = [...((S.st && S.st.handouts) || [])].sort((a, b) => (b.shownAt || 0) - (a.shownAt || 0));
  const seen = seenHandouts();
  const unread = handoutBadge();
  const known = S.handoutIds || null;
  const arrived = known ? unread.filter(x => !known.has(x.id + x.updatedAt)) : [];
  if (arrived.length && S.view !== 'handouts') toast(`New handout from your GM: ${arrived[0].title}`, 4500);
  S.handoutIds = new Set(list.map(x => x.id + x.updatedAt));
  SR.handoutBrowser($('handouts-list'), list, {
    storeKey: 'sg.handoutsOpen', state: S.handoutSearch || (S.handoutSearch = { q: '' }),
    isNew: ho => seen[ho.id] !== ho.updatedAt,
    onOpen: (ho, card) => {
      const now = seenHandouts(); now[ho.id] = ho.updatedAt;
      try { localStorage.setItem('sg.seenHandouts', JSON.stringify(now)); } catch { /* ignore */ }
      card.classList.remove('fresh'); const tag = card.querySelector('.tag.new'); if (tag) tag.remove();
      handoutBadge();
    },
    meta: ho => h('span.hint', ho.shownAt ? timeAgo(ho.shownAt) : ''),
    empty: h('div.card.empty', h('h3', 'No handouts yet'), h('p', 'When your GM shares a dossier, a picture or a message, it appears here.')),
  });
}
function onSheet(sh) {
  S.sheet = sh;
  if (S.st) { Object.assign(S.st.me, sh.player); renderChips(); }
  renderCondition();
  if (mapRoller) mapRoller.render();
  if (S.view === 'store') renderStore();
  if (S.st && S.st.view) { renderTactics(); requestDraw(); }
}
function renderPlayerLog(rolls) {
  SR.renderLog($('p-log'), rolls);
  const r = (rolls || [])[0];
  $('dock-last').textContent = r ? 'Last: ' + SR.rollSummary(r) : '';
}
function onRolled(res) {
  if (res.sheet && sheetUI) sheetUI.setSheet(res.sheet);
  if (res.me && S.st) { Object.assign(S.st.me, res.me); renderChips(); }
  if (res.rolls) { renderPlayerLog(res.rolls); if (sheetUI) sheetUI.updateLog(res.rolls); }
  if (res.me && sheetUI) { sheetUI.mergeMe(res.me); }
  if (mapRoller && S.view !== 'map') mapRoller.render();
}

// ================================================================ map sidebar
function renderCondition() {
  const el = $('p-condition'); el.innerHTML = '';
  if (!S.sheet) return;
  const dv = S.sheet.derived;
  const cm = { p: dv.physical_damage, pm: dv.physical_boxes, s: dv.stun_damage, sm: dv.stun_boxes, ov: dv.overflow_boxes };
  const set = async (track, value) => { try { sheetUI.setSheet(await api('/api/me/sheet/action', 'POST', { action: 'set_damage', track, value })); } catch (e) { toast(e.message); } };
  el.append(SR.monitor('physical', cm, { onSet: set, compact: true, showTools: false }), SR.monitor('stun', cm, { onSet: set, compact: true, showTools: false }));
  const ch = S.sheet.char;
  el.append(h('div.row.between', h('span', 'Edge ', SR.pips(ch.current_edge, dv.edge_max)),
    h('button.small', { type: 'button', disabled: !ch.current_edge, onclick: () => SR.edgeMenu(S.sheet, post, res => { onRolled(res); sheetUI.reload(); }) }, 'Spend Edge…')));
  if (dv.wound_modifier) el.append(h('p.hint.mb0', `Wound modifier ${dv.wound_modifier} dice (applied to rolls).`));
}

// ================================================================ map view (player view)
const { key, geom, tracePoly, drawMarker, renderScene, makeViewport, MARKER_BY_ID, MARKER_TYPES, doorOnEdge, findPath, drawPing } = GridCore;
const canvas = $('map'), ctx2d = canvas.getContext('2d'), wrap = $('canvas-wrap');
const scene = document.createElement('canvas'), sctx = scene.getContext('2d');
const mini = document.createElement('canvas'), mctx = mini.getContext('2d');
const vp = makeViewport(canvas, wrap, $('minimap'), () => S.map);
$('minimap').addEventListener('minimap-move', requestDraw);
function loadIso() { try { return localStorage.getItem('sg.iso') !== '0'; } catch { return true; } }
function setIso(on, remember = true) { vp.setIso(on); $('iso-toggle').checked = on; if (remember) try { localStorage.setItem('sg.iso', on ? '1' : '0'); } catch { /* ignore */ } if (S.map) focusToken(); invalidate(); }
vp.setIso(loadIso());
$('iso-toggle').checked = vp.iso;
$('iso-toggle').onchange = e => setIso(e.target.checked);
/* first-person view: the camera stands on our token */
function loadFp() { try { return localStorage.getItem('sg.fp') === '1'; } catch { return false; } }
function setFp(on) {
  S.fp = on; $('fp-toggle').checked = on; $('fp-hint').hidden = !on; wrap.classList.toggle('fp', on);
  try { localStorage.setItem('sg.fp', on ? '1' : '0'); } catch { /* ignore */ }
  closeDetails(); invalidate();
}
const fpc = FPView.controller({
  map: () => S.map, mapId: () => S.st && S.st.view.map && S.st.view.map.id, at: () => token(), storeKey: 'sg.fp.face.',
  redraw: () => requestDraw(),
  step: cell => {
    const t = S.st.view.token; if (!t || S.busy) return;
    if (!GridCore.passable(geom(S.map), S.map.data.cells, t, cell)) { bump(); return; }
    S.ghost = { c: cell.c, r: cell.r }; requestDraw();
    act('move', { c: cell.c, r: cell.r });
  },
  door: edge => {
    const t = S.st.view.token; if (!t) return;
    if (doorOnEdge(geom(S.map), S.map.data.cells, t.c, t.r, edge)) act('door', { edge }); else bump();
  },
});
/* line of sight: what our runner can see from their token, cover shaded */
const LOS_RADIUS = 20;
function loadLos() { try { return localStorage.getItem('sg.los') === '1'; } catch { return false; } }
function setLos(on) {
  S.los = on; $('los-toggle').checked = on; $('los-key').hidden = !on;
  try { localStorage.setItem('sg.los', on ? '1' : '0'); } catch { /* ignore */ }
  requestDraw();
}
$('los-toggle').onchange = e => setLos(e.target.checked);
S.los = loadLos(); $('los-toggle').checked = S.los; $('los-key').hidden = !S.los;
/* range bands of one weapon (picked under Tactics), and the movement reach in combat */
function pref(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } }
function setPref(k, v) { try { localStorage.setItem(k, v); } catch { /* ignore */ } }
S.range = pref('sg.range', '0') === '1'; S.rangeWeapon = pref('sg.range.w', ''); S.reach = pref('sg.reach', '1') === '1';
function setRange(on) { S.range = on; $('range-toggle').checked = on; setPref('sg.range', on ? '1' : '0'); renderTactics(); requestDraw(); }
function setReach(on) { S.reach = on; $('reach-toggle').checked = on; setPref('sg.reach', on ? '1' : '0'); requestDraw(); }
$('range-toggle').checked = S.range; $('reach-toggle').checked = S.reach;
$('range-toggle').onchange = e => setRange(e.target.checked);
$('reach-toggle').onchange = e => setReach(e.target.checked);
function weaponPools() {
  const sh = S.sheet; if (!sh || !sh.pools) return [];
  return sh.pools.filter(p => p.key.startsWith('weapon:') && p.key !== 'weapon:unarmed' && Array.isArray(p.ar));
}
function eyesOpts() { const e = (S.st && S.st.view.eyes) || {}; return { vision: e.vision || [], blinded: e.blinded || 0 }; }
function sightSig() { return S.cellsSig + '|' + S.explored.size; }
function bump() { wrap.classList.remove('bump'); void wrap.offsetWidth; wrap.classList.add('bump'); }
$('fp-toggle').onchange = e => setFp(e.target.checked);
/* the GM can fix how players see a map (top-down, isometric, first person); otherwise it's the player's choice */
function forcedView() { const v = S.map && S.map.settings && S.map.settings.playerView; return v && v !== 'choose' ? v : null; }
function applyForcedView() {
  const f = forcedView();
  $('iso-toggle').disabled = !!f; $('fp-toggle').disabled = !!f;
  for (const id of ['iso-toggle', 'fp-toggle']) {
    const lab = $(id).closest('label');
    if (lab.dataset.title === undefined) lab.dataset.title = lab.title;
    lab.title = f ? 'The game master chose how this map is seen.' : lab.dataset.title;
  }
  $('view-locked').hidden = !f;
  if (f) {
    const iso = f === 'iso', fp = f === 'fp';
    if (vp.iso !== iso) setIso(iso, false);
    if (S.fp !== fp) setFpView(fp);
  } else if (S.forced) {
    if (vp.iso !== loadIso()) setIso(loadIso(), false);
    if (S.fp !== loadFp()) setFpView(loadFp());
  }
  S.forced = f;
}
function setFpView(on) { S.fp = on; $('fp-toggle').checked = on; $('fp-hint').hidden = !on; wrap.classList.toggle('fp', on); closeDetails(); invalidate(); }
S.fp = loadFp(); $('fp-toggle').checked = S.fp; $('fp-hint').hidden = !S.fp; wrap.classList.toggle('fp', S.fp);

function applyView(v) {
  S.st.view = v; S.ghost = null; S.pathCache = null;
  $('map-empty').hidden = !!v.map;
  if (!v.map) { S.map = null; $('p-help').textContent = 'Your GM has not placed you on a map yet. This page updates on its own.'; renderActions(); renderTracker(); invalidate(); return; }
  $('p-help').textContent = v.token ? `${v.map.name}. Drag your token or click a room you can reach. Doors on your cell open below or by clicking them.` : `${v.map.name}. Waiting for the GM to place your token.`;
  const m = v.map;
  // the server leaves the cells out when we already have this version of them
  let cellsChanged = false;
  if (m.cells == null && m.cellsSig && m.cellsSig === S.cellsSig && S.cells) m.cells = S.cells;
  else if (m.cells == null) { S.cellsSig = ''; refresh(true); return; }
  else if (m.cellsSig !== S.cellsSig || m.cells !== S.cells) { S.cells = m.cells; S.cellsSig = m.cellsSig || ''; cellsChanged = true; }
  const look = JSON.stringify([m.id, m.gridType, m.settings, m.markers, v.token, v.others, m.mapStation, v.stealth]);
  const sceneChanged = cellsChanged || look !== S.lookSig;
  S.lookSig = look;
  S.map = { id: m.id, gridType: m.gridType, width: m.width, height: m.height, cellSize: m.cellSize,
    settings: Object.assign({}, m.settings), data: { cells: m.cells, markers: m.markers, rooms: [] } };
  if (cellsChanged) S.explored = new Set(Object.keys(m.cells).filter(k => m.cells[k].vis !== 'dim'));
  // fit once the map has a size (before layout it is 0 x 0, and draw() does it instead)
  if (!S.fitted || S.lastMapId !== m.id) { if (S.view === 'map' && wrap.clientWidth && wrap.clientHeight) { focusToken(); S.fitted = true; S.lastMapId = m.id; } }
  applyForcedView();
  renderActions(); renderTactics(); renderLegend(); renderTracker();
  if (sceneChanged) invalidate(); else requestDraw();
}
/* initiative order, when the GM shows it */
function renderTracker() {
  const t = S.st && S.st.view.tracker, panel = $('tracker-panel');
  const was = !panel.hidden;
  panel.hidden = !t;
  if (was !== !panel.hidden) Layout.relayout();
  if (!t) return;
  $('p-round').textContent = `Round ${t.round}`;
  const el = $('p-tracker'); el.innerHTML = '';
  for (const e of t.entries) {
    const mine = e.kind === 'player' && e.ref === S.st.me.id;
    el.append(h('span.strip-chip' + (e.current ? '.current' : '') + (mine ? '.mine' : '') + (e.total == null ? '.unrolled' : ''), { role: 'listitem',
      title: `${e.name}${e.minor ? `: 1 Major + ${e.minor} Minor` : ''}` }, h('span.dot', { style: { background: e.color } }),
      h('span.nm', mine ? `${e.name} (you)` : e.name), h('b.sc', e.total == null ? '–' : e.total), mine ? SR.actionPips(e) : null));
  }
  const me = t.entries.find(e => e.kind === 'player' && e.ref === S.st.me.id);
  const note = $('p-turn-note');
  note.className = 'strip-note' + (me && me.current ? ' your-turn' : '');
  note.textContent = !me ? '' : me.total == null ? 'Roll your initiative in the dice panel.' : me.current ? 'Your turn!' : '';
  const cur = el.querySelector('.current'); if (cur) cur.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}
/* fit the map, then zoom in on our own token so the explored area is readable */
function focusToken() {
  vp.fit();
  const t = S.st && S.st.view.token; if (!t || !S.map) return;
  const G = geom(S.map), c = G.cellCenter(t.c, t.r);
  vp.zoom = Math.max(vp.zoom, 46 / G.cs);
  vp.centerOn(c.x, c.y);
}
function token() { return S.ghost || (S.st && S.st.view.token); }
function viewModel() {
  const sneak = s => s ? Object.assign({}, s.statuses || {}, { Sneaking: true }) : null;
  const tokens = (S.st.view.others || []).map(o => ({ ...o, me: false, statuses: o.sneaking ? sneak(o) : o.statuses }));
  const t = token(), stl = S.st.view.stealth || {};
  if (t) tokens.push({ c: t.c, r: t.r, color: S.st.me.color, name: S.st.me.name, me: true, cm: S.st.me.cm, statuses: stl.on ? sneak(S.st.me) : S.st.me.statuses });
  // while sneaking, enemies in view that have eyes on you carry a badge
  const badges = {};
  for (const id of stl.on ? stl.watchers || [] : []) badges[id] = { Watching: true };
  // light as this runner's eyes see it: low-light sees dim light clearly, thermographic and ultrasound see in the dark
  const eyes = eyesOpts().vision, L = GridCore.LIGHT_LEVELS;
  const light = (c, r, cell) => {
    const lv = cell.light ? Math.max(0, L.indexOf(cell.light)) : 0;
    if (!lv) return 0;
    return SightCore.handles(eyes, lv, null, 0) ? (lv === 2 ? 1 : 0) : lv;
  };
  return { mode: 'player', explored: S.explored, mapStation: !!S.st.view.map.mapStation, tokens, light, badges };
}
function pathTo(cell) {
  const t = S.st.view.token; if (!t || !cell) return null;
  const k = key(cell.c, cell.r);
  if (S.pathCache && S.pathCache.k === k) return S.pathCache.path;
  const path = findPath(geom(S.map), S.map.data.cells, t, cell);
  S.pathCache = { k, path };
  return path;
}
function invalidate() { S.sceneDirty = true; requestDraw(); }
function requestDraw() { if (!S.frame) S.frame = requestAnimationFrame(() => { S.frame = null; draw(); }); }
function draw() {
  if (S.view !== 'map') return;
  const dpr = window.devicePixelRatio || 1, W = wrap.clientWidth, H = wrap.clientHeight;
  if (!W || !H) return;
  if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
  ctx2d.setTransform(1, 0, 0, 1, 0, 0);
  ctx2d.fillStyle = S.map ? S.map.settings.colors.fog : '#050707'; ctx2d.fillRect(0, 0, canvas.width, canvas.height);
  if (!S.map) return;
  if (!S.fitted || S.lastMapId !== S.st.view.map.id) { focusToken(); S.fitted = true; S.lastMapId = S.st.view.map.id; S.sceneDirty = true; }
  const v = viewModel(), G = geom(S.map), { w, h: hh } = G.mapPixelSize();
  if (S.fp && token()) { drawFirstPerson(v, G, W, H, dpr, w, hh); return; }
  if (S.sceneDirty || Math.abs(vp.zoom - S.sceneZoom) > 0.5 || S.sceneIso !== vp.iso) {
    const q = Math.min(3, Math.max(1, Math.ceil(vp.zoom * dpr)));
    if (vp.iso) GridCore.buildIsoLayers(S.iso, S.map, v, q);
    else {
      const ow = Math.ceil(w * q), oh = Math.ceil(hh * q);
      if (scene.width !== ow || scene.height !== oh) { scene.width = ow; scene.height = oh; }
      sctx.setTransform(q, 0, 0, q, 0, 0); sctx.clearRect(0, 0, w, hh); renderScene(sctx, S.map, v, { pixel: false }); scene._q = q;
    }
    const { MW, MH, scale } = vp.minimapSize();
    if (mini.width !== MW || mini.height !== MH) { mini.width = MW; mini.height = MH; }
    mctx.setTransform(scale, 0, 0, scale, 0, 0); mctx.clearRect(0, 0, w, hh); renderScene(mctx, S.map, v, { pixel: false, grid: false, borders: false, forExport: true });
    S.sceneDirty = false; S.sceneZoom = vp.zoom; S.sceneIso = vp.iso;
  }
  if (vp.iso) GridCore.drawIsoLayers(ctx2d, S.iso, vp, dpr, G.cs);
  else { ctx2d.setTransform(...vp.matrix(dpr)); const q = scene._q || 1; ctx2d.drawImage(scene, 0, 0, scene.width / q, scene.height / q); }
  ctx2d.setTransform(...vp.matrix(dpr));
  // ---- world-space overlays (lie on the floor)
  const world = GridCore.sightWorld(S.map, {}, sightSig());
  const mv = S.st.view.movement;
  $('reach-key').hidden = !(S.reach && mv && token());
  const wpn = S.range ? weaponPools().find(p => p.key === S.rangeWeapon) : null;
  $('range-key').hidden = !wpn;
  if ((S.los || wpn) && token()) {
    const t = token(), from = S.drag && S.drag.token && S.hover ? S.hover : t;
    const field = GridCore.sightField(S.map, from, LOS_RADIUS, sightSig(), eyesOpts(), requestDraw);
    if (field && wpn) GridCore.drawRange(ctx2d, S.map, field, world, wpn.ar, vp.zoom, ((S.st.view.eyes || {}).extras || []).includes('Magnification'));
    else if (field) GridCore.drawSight(ctx2d, S.map, field, vp.zoom);
  }
  if (S.reach && mv && token() && !(S.drag && S.drag.token)) GridCore.drawReach(ctx2d, S.map, S.st.view.token, mv, vp.zoom);
  if ((S.st.view.templates || []).length) GridCore.drawTemplates(ctx2d, S.map, world, S.st.view.templates, vp.zoom);
  if (S.placing && S.hover) {
    const t0 = Object.assign({ c: S.hover.c, r: S.hover.r }, S.placing.preview);
    ctx2d.globalAlpha = 0.6; GridCore.drawTemplates(ctx2d, S.map, world, [t0], vp.zoom); ctx2d.globalAlpha = 1;
  }
  const target = S.drag && S.drag.token ? S.hover : (S.hover && !S.busy ? S.hover : null);
  const path = target ? pathTo(target) : null;
  if (path && path.length) {
    const t = S.st.view.token;
    ctx2d.strokeStyle = 'rgba(0,229,255,.85)'; ctx2d.lineWidth = 2.5 / vp.zoom; ctx2d.setLineDash([5 / vp.zoom, 4 / vp.zoom]); ctx2d.lineJoin = 'round';
    ctx2d.beginPath(); const s0 = G.cellCenter(t.c, t.r); ctx2d.moveTo(s0.x, s0.y);
    for (const p of path) { const c = G.cellCenter(p.c, p.r); ctx2d.lineTo(c.x, c.y); }
    ctx2d.stroke(); ctx2d.setLineDash([]);
    ctx2d.strokeStyle = S.map.settings.colors.highlight; ctx2d.lineWidth = 2 / vp.zoom;
    tracePoly(ctx2d, G.cellCorners(target.c, target.r), false); ctx2d.stroke();
  } else if (S.hover && S.explored.has(key(S.hover.c, S.hover.r))) {
    ctx2d.strokeStyle = 'rgba(255,255,255,.3)'; ctx2d.lineWidth = 1.5 / vp.zoom;
    tracePoly(ctx2d, G.cellCorners(S.hover.c, S.hover.r), false); ctx2d.stroke();
  }
  const nowS = Date.now() / 1000; let activePing = false;
  for (const pg of S.st.view.pings || []) { const age = nowS - (S.clockSkew || 0) - pg.t; if (age < 0 || age > 10) continue; activePing = true; const { x, y } = G.cellCenter(pg.c, pg.r); drawPing(ctx2d, x, y, G.cs, pg.color, age); }
  if (activePing && !S.pingFrame) S.pingFrame = setTimeout(() => { S.pingFrame = null; requestDraw(); }, 60);
  // ---- screen-space: upright sprites (iso), dragged token, labels
  ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
  const dragging = S.drag && S.drag.token && S.drag.pt;
  if (vp.iso) GridCore.renderSprites(ctx2d, S.map, v, vp, { skipToken: t => dragging && t.me });
  if (dragging) {
    const p = vp.toScreen(S.drag.pt.x, S.drag.pt.y), tok = { color: S.st.me.color, name: S.st.me.name, me: true };
    if (vp.iso) GridCore.drawTokenSprite(ctx2d, p.x, p.y, G.cs * vp.zoom * 0.7, tok, S.map.settings.colors);
    else GridCore.drawToken(ctx2d, p.x, p.y, G.cs * vp.zoom * 0.7, tok, S.map.settings.colors, false);
  }
  const hl = hoverLabel();
  if (hl) { const c = G.cellCenter(hl.c, hl.r), p = vp.toScreen(c.x, c.y); GridCore.drawLabel(ctx2d, p.x, p.y + G.cs * vp.zoom * 0.35, hl.text, G.cs * vp.zoom); }
  vp.drawMinimap(mini);
}
function fpSprites(v, G) {
  const out = [], cells = S.map.data.cells;
  for (const m of S.map.data.markers) {
    if (m.hidden || GridCore.visibility(v, key(m.c, m.r), cells[key(m.c, m.r)]) !== 'full') continue;
    const p = G.cellCenter(m.c, m.r);
    out.push({ kind: 'marker', x: p.x, y: p.y, type: m.type, color: m.color, label: markerName(m), cm: m.cm, statuses: GridCore.markerStatuses(v, m), at: { c: m.c, r: m.r } });
  }
  for (const t of v.tokens) {
    if (t.me || GridCore.visibility(v, key(t.c, t.r), cells[key(t.c, t.r)]) !== 'full') continue;
    const p = G.cellCenter(t.c, t.r);
    out.push({ kind: 'token', x: p.x, y: p.y, color: t.color, name: t.name, label: t.name, cm: t.cm, statuses: t.statuses, at: { c: t.c, r: t.r } });
  }
  return out;
}
function drawFirstPerson(v, G, W, H, dpr, w, hh) {
  if (S.sceneDirty) {      // the minimap still shows the whole map
    const { MW, MH, scale } = vp.minimapSize();
    if (mini.width !== MW || mini.height !== MH) { mini.width = MW; mini.height = MH; }
    mctx.setTransform(scale, 0, 0, scale, 0, 0); mctx.clearRect(0, 0, w, hh); renderScene(mctx, S.map, v, { pixel: false, grid: false, borders: false, forExport: true });
    S.sceneDirty = false;
  }
  const cam = fpc.camera(performance.now());
  // the floor carries the same overlays as the flat map: line of sight or range bands, movement, areas
  const world = GridCore.sightWorld(S.map, {}, sightSig()), mv = S.st.view.movement, t0 = token();
  const wpn = S.range ? weaponPools().find(p => p.key === S.rangeWeapon) : null;
  $('reach-key').hidden = !(S.reach && mv && t0); $('range-key').hidden = !wpn;
  const field = (S.los || wpn) && t0 ? GridCore.sightField(S.map, t0, LOS_RADIUS, sightSig(), eyesOpts(), requestDraw) : null;
  const overlay = GridCore.fpOverlay(S.map, { field, world, ar: wpn ? wpn.ar : null, reach: S.reach && mv && t0 ? { from: S.st.view.token, mv } : null, templates: S.st.view.templates || [] });
  FPView.render(ctx2d, W, H, dpr, { map: S.map, view: v, cam, sprites: fpSprites(v, G), eyes: eyesOpts().vision, overlay });
  const t = token(), c = G.cellCenter(t.c, t.r);
  vp.centerOn(c.x, c.y); vp.drawMinimap(mini);
  if (cam.animating) requestDraw();
}
/* what is under the pointer: the drawn icon in the isometric view, else the cell's contents */
function thingsAt(sx, sy, cell) {
  if (!S.map || !S.st) return null;
  const sprite = vp.iso ? GridCore.pickSprite(S.map, viewModel(), vp, sx, sy) : null;
  const at = sprite ? (sprite.kind === 'marker' ? { c: sprite.m.c, r: sprite.m.r } : { c: sprite.t.c, r: sprite.t.r }) : cell;
  if (!at) return null;
  const mk = S.map.data.markers.find(x => x.c === at.c && x.r === at.r);
  const me = S.st.view.token && S.st.view.token.c === at.c && S.st.view.token.r === at.r;
  const tk = (S.st.view.others || []).find(o => o.c === at.c && o.r === at.r);
  return { c: at.c, r: at.r, marker: mk || null, token: tk || null, me };
}
const markerName = mk => mk.label || (MARKER_BY_ID[mk.type] || MARKER_TYPES[0]).name;
function hoverLabel() {
  const at = S.hoverAt;
  if (!at) return null;
  const parts = [];
  const mk = at.marker, tk = at.token;
  if (mk) { parts.push(markerName(mk)); if (mk.cm) { const st = GridCore.cmStatus(mk.cm); if (st !== 'OK') parts.push(st); } if (mk.isLink) parts.push('→ ' + (mk.targetName || 'somewhere')); }
  if (tk) parts.push(tk.name + (tk.cm && tk.cm.status !== 'OK' ? ` (${tk.cm.status})` : ''));
  return parts.length ? { c: at.c, r: at.r, text: parts.join(' · ') } : null;
}
/* right-click: a small card with what the runner can tell about a marker, a runner or a door */
function closeDetails() { const old = document.getElementById('map-details'); if (old) old.remove(); }
function showDetails(sx, sy, at) {
  closeDetails();
  if (!at) return;
  const blocks = [];
  const stats = st => st && Object.keys(st).length ? SR.statusChips(st) : null;
  if (at.marker) {
    const mk = at.marker, type = (MARKER_BY_ID[mk.type] || MARKER_TYPES[0]).name, hs = mk.cm ? GridCore.cmStatus(mk.cm) : null;
    blocks.push(h('div.md-block', h('div.md-title', h('span.md-dot', { style: { background: mk.color || S.map.settings.colors.markerDefault } }), markerName(mk)),
      mk.label ? h('div.hint', type) : null,
      hs ? h('div.row.tight', SR.healthTag(hs)) : null, stats(mk.statuses),
      mk.isLink ? h('p.hint', `Leads to ${mk.targetName || 'somewhere'}.`) : null,
      mk.info ? h('p.md-info', mk.info) : null));
  }
  for (const t of [at.me ? { name: S.st.me.name + ' (you)', color: S.st.me.color, cm: S.st.me.cm, statuses: S.st.me.statuses } : null, at.token].filter(Boolean)) {
    const hs = t.cm ? (t.cm.status || GridCore.cmStatus(t.cm)) : null;
    blocks.push(h('div.md-block', h('div.md-title', h('span.md-dot', { style: { background: t.color } }), t.name), hs ? h('div.row.tight', SR.healthTag(hs)) : null, stats(t.statuses)));
  }
  const cell = S.map.data.cells[key(at.c, at.r)];
  const doors = cell && cell.doors ? Object.values(cell.doors) : [];
  if (doors.length) blocks.push(h('div.md-block', h('div.hint', doors.length === 1 ? (doors[0].open ? 'An open door.' : doors[0].locked ? 'A locked door.' : 'A closed door.') : `${doors.length} doors.`)));
  if (!blocks.length) return;
  S.hoverAt = null;
  const card = h('div#map-details.map-details', { role: 'dialog', 'aria-label': 'Details' }, h('button.x.md-close', { type: 'button', title: 'Close', onclick: closeDetails }, '×'), blocks);
  wrap.append(card);
  const W = wrap.clientWidth, H = wrap.clientHeight, cw = card.offsetWidth, ch = card.offsetHeight;
  card.style.left = Math.max(8, Math.min(W - cw - 8, sx + 12)) + 'px';
  card.style.top = Math.max(8, Math.min(H - ch - 8, sy + 12)) + 'px';
}
/* Tactics: flashlight, movement left, range bands, areas */
function rangeKey(p) {
  const el = $('range-key'); el.innerHTML = '';
  if (!p) return;
  el.append(h('span.kt', p.label));
  GridCore.RANGE_BANDS.forEach(([name], i) => el.append(h('span.b' + (p.ar[i] == null ? 'x' : i), `${name} ${p.ar[i] == null ? '—' : 'AR ' + p.ar[i]}`)));
}
function templateThings() {
  const v = S.st.view, out = [];
  if (v.token) out.push({ c: v.token.c, r: v.token.r, name: S.st.me.name });
  for (const o of v.others || []) out.push({ c: o.c, r: o.r, name: o.name });
  for (const m of (S.map && S.map.data.markers) || []) out.push({ c: m.c, r: m.r, name: markerName(m) });
  return out;
}
function renderTactics() {
  const el = $('p-tactics'), v = S.st && S.st.view;
  $('p-tactics-block').hidden = !(v && v.map && v.token);
  el.innerHTML = '';
  if (!v || !v.map || !v.token) return;
  // movement this turn
  const mv = v.movement;
  if (mv) {
    const cm = mv.cellM || 2;
    let txt;
    if (!mv.rolled) txt = 'Roll initiative: until then you move freely.';
    else if (!mv.yourTurn) txt = 'Not your turn: you move on yours.';
    else if (!mv.walk && !mv.sprint) txt = mv.mode ? `You've moved ${mv.moved} m this turn.` : `You can't move${mv.why.length ? ` (${mv.why.join(', ')})` : ''}.`;
    else txt = [mv.walk ? `Move: ${mv.walk} m left` : null,
                mv.sprint ? (mv.mode === 'sprint' ? `Sprint: ${mv.sprint} m left` : `Sprint: ${mv.sprint}${mv.sprintMax > mv.sprint ? `–${mv.sprintMax}` : ''} m`) : null].filter(Boolean).join(' · ')
              + (mv.why.length ? ` (${mv.why.join(', ')})` : '');
    el.append(h('p.hint.tac-move', txt));
    const rk = $('reach-key'); rk.innerHTML = '';
    if (mv.walk) rk.append(h('span.rw', `Move ${mv.walk} m (${Math.floor(mv.walk / cm)} cells)`));
    if (mv.sprint) rk.append(h('span.rs', `Sprint ${mv.sprint} m`));
    if (mv.sprintMax > mv.sprint) rk.append(h('span.rm', `with hits, up to ${mv.sprintMax} m`));
  }
  // flashlight
  if (v.flashlight && v.flashlight.has) {
    el.append(h('button', { type: 'button', onclick: () => act('flashlight', { on: !v.flashlight.on }) },
      v.flashlight.on ? 'Switch the flashlight off' : 'Switch the flashlight on'));
  }
  // stealth: ticking it rolls Stealth + Agility; enemies who can see you roll Perception against the hits
  const stl = v.stealth || {};
  const sneakCb = h('input', { type: 'checkbox', id: 'stealth-toggle', checked: !!stl.on, onchange: e => act('stealth', { on: e.target.checked }) });
  el.append(h('div.tac-stealth', h('label.check', { title: 'Stealth + Agility is rolled when you tick it. Attacking or being attacked ends it.' }, sneakCb, ' Stealth'),
    stl.on ? h('span.hint', [stl.hits != null ? `${stl.hits} hit${stl.hits === 1 ? '' : 's'}` : 'Sneaking',
      (stl.watchers || []).length ? `${stl.watchers.length} in view ${stl.watchers.length === 1 ? 'has' : 'have'} eyes on you 👀` : 'no one in view has eyes on you'].join(' · ')) : null));
  // vision
  const eyes = v.eyes || {};
  el.append(h('p.hint', 'Your eyes: ' + (['Normal', ...(eyes.vision || [])].join(', ')) + ((eyes.extras || []).length ? ` · ${eyes.extras.join(', ')}` : '') + (eyes.blinded ? ` · Blinded ${'I'.repeat(eyes.blinded)}` : '')));
  // range bands
  const pools = weaponPools();
  if (pools.length) {
    const sel = h('select', { 'aria-label': 'Weapon for the range bands', onchange: e => { S.rangeWeapon = e.target.value; setPref('sg.range.w', S.rangeWeapon); setRange(!!S.rangeWeapon); } },
      h('option', { value: '' }, 'Range bands: off'),
      pools.map(p => h('option', { value: p.key, selected: S.range && p.key === S.rangeWeapon }, p.label)));
    el.append(h('label.tac-range', sel));
    rangeKey(S.range ? pools.find(p => p.key === S.rangeWeapon) : null);
  }
  // areas
  const inv = (S.sheet && S.sheet.char && S.sheet.char.inventory) || [];
  const boom = inv.filter(it => it.cat === 'Ammo & Explosives' && (it.blast || /Grenade|Rocket|Explosive|Flash-Pak/i.test(it.name)));
  const spells = ((S.sheet && S.sheet.char && S.sheet.char.spells) || []).filter(sp => sp.area);
  const src = h('select', { 'aria-label': 'What makes the area' },
    boom.map(it => h('option', { value: 'item:' + it.uid }, it.name)),
    spells.map(sp => h('option', { value: 'spell:' + sp.name }, `${sp.name} (spell)`)),
    h('option', { value: 'custom' }, 'A radius…'));
  const extra = h('input', { type: 'number', min: 0, max: 50, value: 0, title: 'Increase Area steps (+2 m each) or the radius in meters', style: { width: '4.2em' } });
  const syncExtra = () => { const v2 = src.value; extra.hidden = !(v2.startsWith('spell:') || v2 === 'custom'); if (v2 === 'custom' && +extra.value < 1) extra.value = 4; };
  src.onchange = syncExtra; syncExtra();
  const place = h('button', { type: 'button', onclick: () => {
    const v2 = src.value, source = v2 === 'custom' ? { type: 'custom', radius: +extra.value || 4 }
      : v2.startsWith('spell:') ? { type: 'spell', name: v2.slice(6), increase: +extra.value || 0 } : { type: 'item', uid: v2.slice(5) };
    const r = source.type === 'custom' ? source.radius : source.type === 'spell' ? 2 + 2 * source.increase : 4;
    S.placing = { source, preview: { radius: r, name: src.options[src.selectedIndex].textContent, kind: 'custom', color: S.st.me.color } };
    wrap.classList.add('placing'); toast('Click the cell at the centre of the area (Esc cancels).');
  } }, 'Place an area');
  el.append(h('div.tac-area', src, extra, place));
  const world = S.map ? GridCore.sightWorld(S.map, {}, sightSig()) : null;
  for (const t of v.templates || []) {
    const mine = t.by === S.st.me.id, hits = world ? GridCore.templateTargets(world, t, templateThings()) : [];
    el.append(h('div.tac-tpl', { style: { borderLeftColor: t.color } },
      h('div.tac-tpl-h', h('b', t.name), ` ${t.radius} m`, t.note ? h('span.muted', ` · ${t.note}`) : null,
        mine ? h('button.x', { type: 'button', title: 'Remove', onclick: () => act('templates', { op: 'remove', id: t.id }) }, '×') : null),
      hits.length ? h('div.tac-hits', hits.map(x => h('span', x.name + (x.ring ? ` · ${x.ring}${x.dv ? ' ' + x.dv : ''}` : '')))) : h('div.muted', 'Nobody you can see is inside.')));
  }
}
function renderActions() {
  const el = $('p-actions'); el.innerHTML = '';
  if (!S.st || !S.st.view.map) return;
  const G = geom(S.map);
  for (const d of S.st.view.doorsHere || []) {
    const b = h('button', { type: 'button', disabled: !!d.locked, onclick: () => act('door', { edge: d.edge }) },
      h('span.dot', { style: { background: d.color } }), d.locked ? `${G.edgeNames[d.edge]} door is locked` : `${d.open ? 'Close' : 'Open'} ${G.edgeNames[d.edge].toLowerCase()} door`);
    el.append(b);
  }
  if (S.st.view.canTravel) el.append(h('button.primary', { type: 'button', onclick: () => act('travel') }, `Travel to ${S.st.view.canTravel.mapName}`));
  const others = S.st.view.others || [];
  if (others.length) el.append(h('p.hint', 'Nearby: ' + others.map(o => o.name + (o.cm && o.cm.status !== 'OK' ? ` (${o.cm.status})` : '')).join(', ')));
}
function renderLegend() {
  const el = $('legend'); el.hidden = !(S.map && S.map.settings.legendVisible); el.innerHTML = '';
  if (el.hidden) return;
  // the GM decides per map whether players get a legend; it names the kinds of markers in view, without counts
  const groups = new Set(), col = S.map.settings.colors;
  for (const m of S.map.data.markers) groups.add(m.type + '|' + (m.color || col.markerDefault));
  if (!groups.size) return;
  el.append(h('h4', 'Legend'));
  for (const k of groups) {
    const [type, color] = k.split('|');
    const cv = h('canvas', { width: 36, height: 36 }); drawMarker(cv.getContext('2d'), 18, 18, 26, type, color, col.markerText, false);
    el.append(h('div.legend-row', cv, h('span', (MARKER_BY_ID[type] || MARKER_TYPES[0]).name)));
  }
}
async function ping(cell) {
  if (!cell) return;
  S.st.view.pings = (S.st.view.pings || []).concat([{ c: cell.c, r: cell.r, t: Date.now() / 1000 - (S.clockSkew || 0), color: S.st.me.color, name: S.st.me.name }]); requestDraw();
  try { await post('ping', cell); } catch (e) { toast(e.message); }
}
async function act(path, body) {
  if (S.busy) return; S.busy = true;
  try { applyView(await post(path, body)); } catch (e) { S.ghost = null; invalidate(); toast(e.message); }
  S.busy = false;
}
function moveTo(cell) {
  if (!cell || !S.st.view.token) return;
  const path = pathTo(cell);
  if (!path || !path.length) return;
  S.ghost = { c: cell.c, r: cell.r }; invalidate();
  act('move', { c: cell.c, r: cell.r });
}
canvas.addEventListener('contextmenu', e => e.preventDefault());
function stopPlacing() { S.placing = null; wrap.classList.remove('placing'); requestDraw(); }
canvas.addEventListener('pointerdown', ev => {
  if (S.fp && token()) { S.drag = { fp: true, sx: ev.clientX, sy: ev.clientY, right: ev.button === 2 }; return; }
  if (S.placing && ev.button === 0) {
    const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy), cell = S.map ? geom(S.map).pointToCell(pt.x, pt.y) : null;
    const source = S.placing.source; stopPlacing();
    if (cell) act('templates', { op: 'add', source, c: cell.c, r: cell.r });
    return;
  }
  canvas.setPointerCapture(ev.pointerId);
  const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy);
  const pan = ev.button === 1 || ev.button === 2 || S.spaceDown;
  const t = S.st && S.st.view.token, cell = S.map ? geom(S.map).pointToCell(pt.x, pt.y) : null;
  const at = !pan ? thingsAt(sx, sy, cell) : null;
  const onToken = !pan && t && at && at.me;
  if (!ev.target.closest || !ev.target.closest('#map-details')) closeDetails();
  S.drag = { sx, sy, px: vp.panX, py: vp.panY, moved: false, token: onToken, tap: !pan, pt, right: ev.button === 2 };
  canvas.classList.toggle('panning', pan);
});
canvas.addEventListener('pointermove', ev => {
  if (S.fp && token()) return;
  const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy);
  S.hover = S.map ? geom(S.map).pointToCell(pt.x, pt.y) : null;
  S.hoverAt = S.drag || document.getElementById('map-details') ? null : thingsAt(sx, sy, S.hover);
  if (S.drag) {
    if (Math.hypot(sx - S.drag.sx, sy - S.drag.sy) > 6) S.drag.moved = true;
    if (S.drag.token) S.drag.pt = pt;
    else if (S.drag.moved) { vp.panX = S.drag.px + (sx - S.drag.sx); vp.panY = S.drag.py + (sy - S.drag.sy); }
  }
  requestDraw();
});
canvas.addEventListener('pointerup', ev => {
  if (S.fp && token() && S.drag && S.drag.fp) {
    const d = S.drag; S.drag = null;
    const { sx, sy } = vp.canvasPoint(ev), hit = FPView.pick(sx, sy);
    if (hit) { const at = thingsAt(0, 0, hit.at); showDetails(sx, sy, at); return; }
    if (!d.right) { closeDetails(); fpc.tap(sx, sy, wrap.clientWidth, wrap.clientHeight); }
    return;
  }
  const d = S.drag; S.drag = null; canvas.classList.remove('panning');
  if (d && S.map) {
    const { sx, sy } = vp.canvasPoint(ev), pt = vp.screenToMap(sx, sy), cell = geom(S.map).pointToCell(pt.x, pt.y);
    const t = S.st.view.token;
    if (d.right && !d.moved) { showDetails(sx, sy, thingsAt(sx, sy, cell)); requestDraw(); return; }
    if (d.tap && !d.moved) { const nowMs = Date.now(); if (nowMs - S.lastTap < 350 && cell) { S.lastTap = 0; ping(cell); requestDraw(); return; } S.lastTap = nowMs; }
    if (d.token && d.moved) moveTo(cell);
    else if (d.tap && !d.moved && cell && t && cell.c === t.c && cell.r === t.r) {
      const G = geom(S.map), e = G.nearestEdge(t.c, t.r, pt.x, pt.y);
      if (doorOnEdge(G, S.map.data.cells, t.c, t.r, e)) act('door', { edge: e });
    } else if (d.tap && !d.moved) moveTo(cell);
  }
  requestDraw();
});
canvas.addEventListener('pointerleave', () => { S.hover = null; S.hoverAt = null; requestDraw(); });
canvas.addEventListener('wheel', ev => { ev.preventDefault(); if (S.fp) return; closeDetails(); const { sx, sy } = vp.canvasPoint(ev); vp.zoomAt(sx, sy, Math.exp(-ev.deltaY * 0.0015)); requestDraw(); }, { passive: false });
const ARROWS = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
window.addEventListener('keydown', ev => {
  if (S.view !== 'map' || ev.target.matches('input, textarea, select') || document.querySelector('dialog[open]')) return;
  if (ev.key === 'Escape') closeDetails();
  if ((ev.key.toLowerCase() === 'v' || ev.key === '3') && !ev.ctrlKey && !ev.metaKey) { if (!forcedView()) setFp(!S.fp); return; }
  if (ev.key.toLowerCase() === 'l' && !ev.ctrlKey && !ev.metaKey && !S.fp) { setLos(!S.los); return; }
  if (ev.key.toLowerCase() === 'r' && !ev.ctrlKey && !ev.metaKey && !S.fp) {
    if (!S.rangeWeapon && weaponPools()[0]) { S.rangeWeapon = weaponPools()[0].key; setPref('sg.range.w', S.rangeWeapon); }
    setRange(!S.range); return;
  }
  if (ev.key.toLowerCase() === 'm' && !ev.ctrlKey && !ev.metaKey && !S.fp) { setReach(!S.reach); return; }
  if (ev.key === 'Escape' && S.placing) { stopPlacing(); return; }
  if (S.fp && token() && !ev.ctrlKey && !ev.metaKey && !ev.altKey) { if (fpc.key(ev)) return; }
  if (ev.code === 'Space') { S.spaceDown = true; canvas.classList.add('panning'); ev.preventDefault(); }
  if (ev.key.toLowerCase() === 'f' && S.map) { vp.fit(); invalidate(); }
  if (ev.key.toLowerCase() === 'c' && S.map) { focusToken(); invalidate(); }
  if (ev.key.toLowerCase() === 'i' && !ev.ctrlKey && !ev.metaKey && !forcedView()) setIso(!vp.iso);
  if (ARROWS[ev.key] && S.map && S.st.view.token && !S.busy) {
    ev.preventDefault();
    const t = S.st.view.token, G = geom(S.map), [dc, dr] = ARROWS[ev.key];
    let target = { c: t.c + dc, r: t.r + dr };
    if (G.hex) {
      let best = null, bestDot = 0.3;
      for (let e = 0; e < G.edgeCount; e++) { const n = G.neighbor(t.c, t.r, e), a0 = G.cellCenter(t.c, t.r), b0 = G.cellCenter(n.c, n.r), a = vp.toScreen(a0.x, a0.y), b = vp.toScreen(b0.x, b0.y); const vx = b.x - a.x, vy = b.y - a.y, len = Math.hypot(vx, vy); const dot = (vx * dc + vy * dr) / len; if (dot > bestDot) { bestDot = dot; best = n; } }
      target = best;
    }
    if (target) moveTo(target);
  }
});
window.addEventListener('keyup', ev => { if (ev.code === 'Space') { S.spaceDown = false; canvas.classList.remove('panning'); } });
new ResizeObserver(() => requestDraw()).observe(wrap);

// ================================================================ store
function setStoreCat(c) { S.storeCat = c || 'All'; }
function renderStore() {
  if (!CAT || !S.sheet) return;
  const ch = S.sheet.char, sh = S.sheet, approved = sh.approved;
  $('store-nuyen').textContent = money(ch.nuyen);
  $('store-custom').hidden = approved;
  $('store-note').replaceChildren(approved ? h('div.banner', h('p', `Legal gear up to Availability ${CAT.store.alwaysAvail} is always on sale. Everything else needs a contact who sources it, with a Connection above its Availability. Purchases are final; the store buys gear back at ${sh.sellPct}%.`,
    h('button.small', { type: 'button', onclick: () => { setView('sheet'); sheetUI.go('contacts'); } }, 'My contacts ›'))) :
    h('div.banner.info', h('p', `Character creation: everything up to Availability ${CAT.store.creationMaxAvail} is on sale, and anything you buy can be returned for a full refund from the Gear section of your character.`)));
  const cats = $('store-cats'); cats.innerHTML = '';
  for (const c of ['All', ...CAT.store.categories, 'PACKs']) cats.append(h('button' + (S.storeCat === c ? '.active' : ''), { type: 'button', onclick: () => { S.storeCat = c; renderStore(); } }, c));
  const q = $('store-search').value.trim().toLowerCase();
  const only = $('store-avail-only').checked;
  const grid = $('store-grid'); grid.innerHTML = '';
  const owned = {}; for (const it of ch.inventory) if (it.ref) owned[it.ref] = (owned[it.ref] || 0) + (it.unit ? 1 : (it.qty || 1));
  let n = 0, hidden = 0, lastSub = null;
  for (const e of [...CAT.store.items, ...CAT.packs]) {
    if (S.storeCat !== 'All' && S.storeCat !== e.cat) continue;
    if (e.pack && S.storeCat === 'All' && !q) continue;           // PACKs live in their own tab (or show up in searches)
    if (q && !(e.name + ' ' + e.sub + ' ' + (e.desc || '')).toLowerCase().includes(q)) continue;
    const acc = sh.store[e.id] || [true, '', 0];
    if (only && !acc[0]) { hidden++; continue; }
    n++;
    const sub = `${e.cat} · ${e.sub}`;
    if (sub !== lastSub && !q) { grid.append(h('h3.store-sub', sub)); lastSub = sub; }
    grid.append(e.pack ? packCard(e, acc) : storeCard(e, acc, owned[e.id]));
  }
  if (!n) grid.append(h('p.empty', hidden ? 'Nothing you can get here yet. Untick “Only what I can get” to see what your contacts would need.' : 'Nothing matches. Try another search.'));
  else if (hidden) grid.append(h('p.hint', `${hidden} item${hidden > 1 ? 's' : ''} hidden: none of your contacts can get them.`));
}
/* A Sixth World Companion PACK: one price for a whole kit (augmentation PACKs come in grades). */
function packCard(e, acc) {
  const ch = S.sheet.char, ok = acc[0];
  const grade = e.packGrades ? h('select', { title: 'Grade' }, option('Standard', 'Standard grade'), Object.keys(e.packGrades).map(g => option(g))) : null;
  const priceEl = h('span.price'), essEl = h('span.hint'), btn = h('button.primary.small', { type: 'button' });
  const mult = (S.sheet.derived.price_markup || [0, 0])[0];
  function calc() {
    const g = grade && grade.value !== 'Standard' ? e.packGrades[grade.value] : null;
    const cost = Math.round((g ? g.cost : e.cost) * (1 + mult)), ess = g ? g.essence : e.essenceN;
    priceEl.textContent = money(cost);
    essEl.textContent = `Avail ${e.avail}` + (ess ? ` · Essence ${ess}` : '');
    btn.textContent = !ok ? 'Unavailable' : cost > ch.nuyen ? 'Not enough ¥' : 'Buy PACK';
    btn.disabled = !ok || cost > ch.nuyen;
    btn.title = !ok ? acc[1] : '';
    return { cost, g: grade ? grade.value : 'Standard' };
  }
  if (grade) grade.onchange = calc;
  btn.onclick = async () => {
    const v = calc();
    if (!await UI.confirm(`Buy the ${e.name}${v.g !== 'Standard' ? ` (${v.g})` : ''} for ${money(v.cost)}? It adds ${e.contents.length} entries to your gear.${S.sheet.approved ? ' Purchases are final.' : ''}`, { ok: 'Buy' })) return;
    try { const sh = await api('/api/me/sheet/action', 'POST', { action: 'buy_pack', ref: e.id, grade: v.g }); sheetUI.setSheet(sh); toast(sh.message, 4000); }
    catch (err) { toast(err.message, 5000); }
  };
  const card = h('div.item-card.pack' + (ok ? '' : '.locked'),
    h('div.cat', e.sub), h('h4', e.name), h('p.hint', e.desc),
    e.includes ? h('p.hint', `Includes the ${e.includes}.`) : null,
    e.skills ? h('p.hint', `Recommended skills: ${e.skills}`) : null,
    h('details', h('summary', `Contents (${e.contents.length})`), h('ul.pack-list', e.contents.map(x => h('li', x)))),
    ok ? null : h('p.why', (outOfStock(acc) ? '📦 ' : '🔒 ') + acc[1]),
    h('div.buy-opts', grade),
    h('div.buy', h('div.col', priceEl, essEl), btn));
  calc();
  return card;
}
const outOfStock = acc => !acc[0] && /^Out of stock/.test(acc[1] || '');
function storeCard(e, acc, owned) {
  const ch = S.sheet.char, ok = acc[0], oos = outOfStock(acc);
  const rating = e.rating ? h('input', { type: 'number', min: e.rating[0], max: e.rating[1], value: e.rating[0], title: `Rating ${e.rating[0]}-${e.rating[1]}` }) : null;
  const grade = e.implant ? h('select', { title: 'Implant grade' }, Object.keys(CAT.store.grades).map(g => option(g, g === 'Standard' ? 'Standard grade' : g))) : null;
  const qty = !e.implant && !e.rating ? h('input', { type: 'number', min: 1, max: 100, value: 1, title: e.sub === 'Ammunition' ? 'Boxes of 10' : 'Quantity' }) : null;
  const priceEl = h('span.price'), availEl = h('span.hint'), whyEl = h('p.why');
  const btn = h('button.primary.small', { type: 'button' });
  const mk = S.sheet.derived.price_markup || [0, 0];
  const metaMult = 1 + mk[0] + (e.cat === 'Armor' ? mk[1] : 0);
  function calc() {
    let cost = e.costN, av = e.availN, legal = e.legalN, ess = e.essenceN ?? null, r = 1;
    if (e.byRating) {
      r = Math.max(e.rating[0], Math.min(e.rating[1], +rating.value || e.rating[0]));
      const row = e.byRating.find(x => x[0] === r) || e.byRating[0];
      [, cost, av, legal] = row; ess = e.implant ? row[4] : null;
    }
    if (grade) { const g = CAT.store.grades[grade.value]; cost *= g.cost; av = Math.max(0, av + g.avail); if (ess != null) ess = Math.round(ess * g.essence * 100) / 100; }
    cost = Math.ceil(cost * metaMult - 1e-9);
    const n = qty ? Math.max(1, +qty.value || 1) : 1;
    const total = cost * n;
    const reach = oos ? [false, acc[1]] : availOk(av, legal, e.supply);
    priceEl.textContent = money(total) + (n > 1 ? ` (${money(cost)} each)` : '');
    priceEl.classList.toggle('short', total > ch.nuyen);
    availEl.textContent = `Avail ${SR.availText(av, legal)}` + (ess != null ? ` · Essence ${ess}` : '');
    btn.textContent = oos ? 'Out of stock' : !reach[0] ? 'Unavailable' : total > ch.nuyen ? 'Not enough ¥' : 'Buy';
    btn.disabled = !reach[0] || total > ch.nuyen;
    btn.title = !reach[0] ? reach[1] : total > ch.nuyen ? `You need ${money(total - ch.nuyen)} more` : '';
    whyEl.textContent = reach[0] ? '' : (oos ? '📦 ' : '🔒 ') + reach[1];
    whyEl.hidden = reach[0];
    return { r, n, total, cost };
  }
  for (const el of [rating, grade, qty]) if (el) el.oninput = el.onchange = calc;
  btn.onclick = async () => {
    const v = calc();
    if (S.sheet.approved && !await UI.confirm(`Buy ${v.n > 1 ? v.n + ' × ' : ''}${e.name}${rating ? ' ' + v.r : ''}${grade && grade.value !== 'Standard' ? ' (' + grade.value + ')' : ''} for ${money(v.total)}? Purchases are final.${e.implant ? ' Surgery leaves you with some damage to heal.' : ''}`, { ok: 'Buy' })) return;
    try {
      const sh = await api('/api/me/sheet/action', 'POST', { action: 'buy', ref: e.id, rating: v.r, grade: grade ? grade.value : 'Standard', qty: v.n });
      sheetUI.setSheet(sh); toast(sh.message);
    } catch (err) { toast(err.message, 4500); }
  };
  const card = h('div.item-card' + (ok ? '' : '.locked') + (oos ? '.oos' : ''),
    h('div.cat', e.sub + (owned ? '' : '')), h('h4', e.name, oos ? h('span.tag.oos-tag', 'Out of stock') : null, owned ? h('span.tag.approved', { style: { marginLeft: '.4rem' } }, `owned ×${owned}`) : null),
    h('p.stats', SR.itemStats(e)), e.desc ? h('p.hint', e.desc) : null,
    whyEl,
    h('div.buy', h('div.col', priceEl, availEl), h('div.buy-opts', rating ? h('label', 'Rating', rating) : null, grade, qty ? h('label', e.sub === 'Ammunition' ? 'Boxes' : 'Qty', qty) : null), btn));
  calc();
  return card;
}
/* same contact rule as the server: creation limit, always-available legal items, or a confirmed contact
   who covers the goods and whose Connection is higher than the Availability */
function availOk(av, legal, supply) {
  const sh = S.sheet;
  if (!sh.approved) return av <= CAT.store.creationMaxAvail ? [true, ''] : [false, `Availability ${av}: above the creation limit of ${CAT.store.creationMaxAvail}.`];
  if (av <= CAT.store.alwaysAvail && legal !== 'I') return [true, ''];
  let pending = null;
  for (const ct of sh.char.contacts) {
    const sup = SR.contactSupply(ct);
    if ((sup.includes(supply) || sup.includes('Fixer')) && ct.connection > av) {
      if (ct.verified !== false) return [true, ct.name];
      pending = pending || ct.name;
    }
  }
  if (pending) return [false, `${pending} can get this once the GM confirms them.`];
  return [false, `Needs a contact for ${supply} with Connection ${av + 1} or more.`];
}
$('store-search').oninput = () => renderStore();
$('store-avail-only').onchange = () => renderStore();
$('store-custom').onclick = async () => {
  const it = await SR.editItem({}, { title: 'Custom item', ok: 'Buy', cat: S.storeCat !== 'All' ? S.storeCat : 'Survival' });
  if (!it) return;
  try { const sh = await api('/api/me/sheet/action', 'POST', { action: 'buy_custom', item: it }); sheetUI.setSheet(sh); toast(sh.message); } catch (e) { toast(e.message, 4000); }
};

// ================================================================ runs
async function loadRuns() {
  try { renderRuns((await api('/api/me/runs')).runs); } catch (e) { /* transient */ }
  try { renderSessionRecaps((await api('/api/me/sessions')).sessions); } catch (e) { /* transient */ }
}
function renderSessionRecaps(list) {
  const el = $('sessions-list'); el.innerHTML = '';
  if (!list.length) return;
  el.append(h('div.section-head.mt', h('h2', 'Session log'), h('span.hint', 'Recaps your GM shared.')));
  for (const s of list) {
    const st = s.recap.stats, when = new Date(s.startedAt * 1000);
    const tl = h('ol.timeline', s.recap.events.filter(e => e.kind !== 'init').map(e => h('li.' + e.kind + (e.flag ? '.' + e.flag : ''),
      h('span.t', new Date(e.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })), h('span.x', e.kind === 'note' ? `${e.who} ${e.text}` : e.text))));
    el.append(h('div.run-card.session',
      h('div.head', h('h3', s.title), h('span.hint', when.toLocaleDateString())),
      h('p.hint', `${st.minutes} minutes · ${st.fights} fight(s) · ${st.attacks} attacks · ${st.rolls} rolls`),
      s.notes ? renderMarkdown(s.notes) : null,
      h('details.timeline-wrap', h('summary', `Timeline (${tl.children.length})`), tl)));
  }
}
function renderRuns(runs) {
  const el = $('runs-list'); el.innerHTML = '';
  if (!runs.length) { el.append(h('div.card.empty', h('h3', 'No contracts yet'), h('p', 'When your GM gives you a run it shows up here, with its tasks and the reward.'))); return; }
  for (const r of runs) {
    const tasks = h('ul.tasks');
    r.tasks.forEach(t => tasks.append(h('li' + (t.completed ? '.done' : ''), h('span.tick', t.completed ? '✓' : ''), h('span.t', t.description), t.mandatory ? h('span.mand', { title: 'Mandatory' }, '*') : null)));
    const reward = r.status === 'Completed' ? h('span', 'Paid ', h('b.good', money(r.payout)), ' to each runner') :
      r.status === 'Abandoned' ? h('span.hint', 'Abandoned') : h('span', 'Reward ', h('b', money(r.reward)), r.tasks.length ? h('span.hint', ` · currently ${money(r.scaledPayout)} (${r.progress}% of tasks)`) : '');
    el.append(h('div.run-card' + (r.status === 'Abandoned' ? '.dim' : ''),
      h('div.head', h('h3', r.name), h('span.tag.' + r.status.toLowerCase(), r.status)),
      r.description ? h('p', { style: { whiteSpace: 'pre-wrap' } }, r.description) : null,
      r.tasks.length ? h('div.bar', h('span', { style: { width: r.progress + '%' } })) : null,
      r.tasks.length ? tasks : null,
      r.tasks.some(t => t.mandatory) ? h('p.hint.mb0', '* mandatory. The GM ticks tasks as you complete them.') : null,
      h('div', reward)));
  }
}

// ================================================================ boot
async function boot() {
  Layout.init($('layout'), 'player');
  try {
    CAT = await SR.catalog();
    await refresh(true);
    sheetUI = Sheet.mount($('sheet-root'), { gm: false, sheetUrl: '/api/me/sheet', actionUrl: '/api/me/sheet/action', transferUrl: '/api/me/transfer', post, onSheet,
      openStore: cat => { if (cat) setStoreCat(cat); setView('store'); }, log: () => (S.st ? S.st.rolls : []), onRolled });
    await sheetUI.load();
    S.sheetRev = S.st.sheetRev;
    mapRoller = SR.roller({ compact: true, getSheet: () => S.sheet, post, onRolled });
    $('p-roller').append(mapRoller); mapRoller.render();
    Wiki($('wiki'), CAT.wiki);
    const first = location.hash.slice(1) || (S.st.me.status !== 'approved' && !S.st.view.map ? 'sheet' : 'map');
    setView(first);
    setInterval(() => refresh(false), 15000);
    Live.on(() => refresh(false));
    Music.mount({ host: document.querySelector('.appbar .chips') });
  } catch (e) { if (e.message !== 'auth') toast('Could not load: ' + e.message, 6000); }
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(true); });
boot();
// handle for automated UI tests
window.__sgp = { S, vp, canvas };
})();

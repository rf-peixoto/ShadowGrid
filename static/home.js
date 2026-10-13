/* GM home page: games, their maps and runners. Map generator. */
(() => {
'use strict';
const $ = id => document.getElementById(id);
let OV = null;

function dialog(id, onOk, focusId) {
  const d = $(id); d.returnValue = '';
  d.onclose = () => { if (d.returnValue === 'ok') onOk(); };
  d.showModal(); if (focusId) $(focusId).focus();
}

async function load() {
  OV = await api('/api/overview');
  const root = $('campaigns'); root.innerHTML = '';
  if (!OV.games.length && !OV.maps.length) {
    root.innerHTML = '<section class="panel empty"><h2>Start with a game</h2><p class="muted">A game holds your maps, runners and runs. Create one, add a map, then invite your players with a link.</p></section>';
    root.querySelector('section').appendChild(Object.assign(document.createElement('button'), { className: 'primary', textContent: 'New game', onclick: newCampaign }));
  }
  for (const g of OV.games) root.appendChild(campaignSection(g, OV.maps.filter(m => m.campaignId === g.id), g.players));
  const loose = OV.maps.filter(m => !m.campaignId);
  if (loose.length) root.appendChild(campaignSection(null, loose, []));
}

function mapCard(m) {
  const card = document.createElement('div'); card.className = 'map-card';
  const a = document.createElement('a'); a.className = 'map-name'; a.href = '/map/' + m.id; a.textContent = m.name;
  const meta = document.createElement('div'); meta.className = 'meta';
  const d = new Date(m.updatedAt * 1000);
  meta.textContent = `${m.gridType === 'hex' ? 'Hex' : 'Square'} · ${m.width}×${m.height} · ${d.toLocaleDateString()}`;
  const acts = document.createElement('div'); acts.className = 'row tight';
  const open = document.createElement('a'); open.className = 'btn small'; open.href = '/map/' + m.id; open.textContent = 'Open';
  const more = document.createElement('select'); more.className = 'small'; more.title = 'More actions';
  more.innerHTML = '<option value="">More…</option><option value="dup">Duplicate</option><option value="export">Export JSON</option>' +
    (OV.campaigns.length ? '<optgroup label="Move to">' + '<option value="mv:">No game</option>' + OV.campaigns.map(c => `<option value="mv:${c.id}">${escapeHtml(c.name)}</option>`).join('') + '</optgroup>' : '') +
    '<option value="del">Delete</option>';
  more.onchange = async () => {
    const v = more.value; more.value = '';
    if (v === 'dup') { await api(`/api/maps/${m.id}/duplicate`, 'POST', {}); load(); }
    else if (v === 'export') location.href = `/api/maps/${m.id}/export`;
    else if (v.startsWith('mv:')) { await api(`/api/maps/${m.id}`, 'PUT', { campaignId: v.slice(3) || null }); load(); }
    else if (v === 'del' && await UI.confirm(`Delete "${m.name}"? This cannot be undone.`, { danger: true, ok: 'Delete map' })) { await api(`/api/maps/${m.id}`, 'DELETE'); load(); }
  };
  acts.append(open, more);
  card.append(a, meta, acts);
  return card;
}

function campaignSection(c, maps, players) {
  const node = document.importNode($('tpl-campaign').content, true);
  const sec = node.querySelector('section');
  const name = node.querySelector('.campaign-name');
  if (c) {
    name.textContent = c.name;
    if (c.waiting) name.after(h('span.tag.waiting', { title: 'Sheets waiting for your approval' }, `${c.waiting} sheet${c.waiting > 1 ? 's' : ''} to approve`));
    name.onblur = async () => { const n = name.textContent.trim(); if (n && n !== c.name) { await api(`/api/campaigns/${c.id}`, 'PUT', { name: n }); c.name = n; toast('Game renamed.'); } else name.textContent = c.name; };
    name.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); name.blur(); } };
    node.querySelector('.open-game').href = '/game/' + c.id;
    node.querySelector('.add-player').onclick = async () => { await SR.invite(c.id, c.name); load(); };
    node.querySelector('.del-campaign').onclick = async () => {
      if (await UI.confirm(`Delete "${c.name}"? Its maps are kept (unassigned). Its runners, their characters, runs and snapshots are deleted for good.`, { danger: true, ok: 'Delete game' }))
        api(`/api/campaigns/${c.id}`, 'DELETE').then(load);
    };
  } else {
    name.textContent = 'Maps without a game'; name.contentEditable = 'false'; name.title = '';
    node.querySelector('.add-player').remove(); node.querySelector('.del-campaign').remove(); node.querySelector('.open-game').remove();
    node.querySelector('.players-col').remove();
    sec.classList.add('loose');
  }
  node.querySelector('.new-map').onclick = () => newMap(c);
  node.querySelector('.gen-map').onclick = () => genMap(c);
  const grid = node.querySelector('.map-grid');
  if (!maps.length) grid.innerHTML = '<p class="muted">No maps yet. Create or generate one.</p>';
  for (const m of maps) grid.appendChild(mapCard(m));
  const pl = node.querySelector('.player-list');
  if (pl) {
    if (!players.length) pl.append(h('li.muted', 'No runners yet. Use “Invite player” and send them the link.'));
    for (const p of players) {
      const where = p.currentMapId ? OV.maps.find(m => m.id === p.currentMapId) : null;
      pl.append(h('li',
        h('span.player-name', h('span.dot', { style: { background: p.color } }), h('a', { href: `/game/${p.campaignId}/sheet/${p.id}` }, p.name),
          h('span.sub', p.name !== p.username ? '@' + p.username : '')),
        h('span.row.tight', SR.healthTag(p.cm.status), SR.statusTag(p.status), h('span.hint', where ? where.name : ''))));
    }
  }
  return sec;
}

function newCampaign() {
  $('cd-name').value = '';
  dialog('campaign-dialog', async () => { const n = $('cd-name').value.trim() || 'New game'; const r = await api('/api/campaigns', 'POST', { name: n }); location.href = '/game/' + r.id; }, 'cd-name');
}
function newMap(c) {
  $('md-title').textContent = c ? `New map in ${c.name}` : 'New map';
  $('md-name').value = '';
  $('md-file').value = '';
  $('md-import').onclick = () => $('md-file').click();
  $('md-file').onchange = async e => {
    const f = e.target.files[0]; if (!f) return;
    try { const r = await api('/api/maps/import?campaign=' + encodeURIComponent(c ? c.id : ''), 'POST', await f.text()); location.href = '/map/' + r.id; }
    catch (err) { toast(err.message); }
  };
  dialog('map-dialog', async () => {
    const r = await api('/api/maps', 'POST', { name: $('md-name').value || 'Untitled map', gridType: $('md-grid').value, width: +$('md-w').value, height: +$('md-h').value, cellSize: +$('md-cs').value, campaignId: c ? c.id : null });
    location.href = '/map/' + r.id;
  }, 'md-name');
}
// ---------------------------------------------------------------- generator dialog
const GEN = { out: null, timer: null };
function genOpts() {
  return {
    gridType: $('gd-grid').value, algo: $('gd-algo').value, width: +$('gd-w').value, height: +$('gd-h').value, seed: $('gd-seed').value.trim(),
    doors: $('gd-doors').checked, doorChance: +$('gd-doorchance').value, groupRooms: $('gd-rooms').checked,
    roomCount: +$('gd-roomcount').value, roomMin: +$('gd-roommin').value, roomMax: +$('gd-roommax').value, wallGap: +$('gd-gap').value,
    loops: +$('gd-loops').value, corridorWidth: +$('gd-cwidth').value, corridorMax: +$('gd-cmax').value,
    windiness: +$('gd-windy').value, deadEnds: +$('gd-deadends').value,
    caveFill: +$('gd-fill').value, caveSmooth: +$('gd-smooth').value, caveMinBlob: +$('gd-minblob').value,
  };
}
function genConstrain() {
  const hex = $('gd-grid').value === 'hex';
  $('gd-algo-caves').disabled = !hex;
  if (!hex && $('gd-algo').value === 'caves') $('gd-algo').value = 'rooms';
  $('gd-door-opts').hidden = hex || $('gd-algo').value === 'caves';
  $('gd-room-opts').hidden = $('gd-algo').value === 'caves';
}
function genPreview() {
  clearTimeout(GEN.timer);
  genConstrain();
  GEN.timer = setTimeout(() => {
    const o = genOpts();
    if (o.gridType === 'hex') o.doors = false;
    if (o.width < 12 || o.height < 12) return;
    $('gd-stats').textContent = 'Generating…';
    GEN.out = GridGen.generate(o);
    const map = { gridType: o.gridType, width: o.width, height: o.height, cellSize: 16,
      settings: { colors: { background: '#0b1214', grid: '#1a2c30', fog: '#050909', cellBorder: '#4fd8dc', revealedTint: '#3e5c60', exploredTint: '#ffffff', secretHatch: '#ff2f7d', doorDefault: '#2de2e6', doorOpen: '#6dff9c', roomLabel: '#9ff3f5', markerDefault: '#ff2f7d', markerText: '#12060b', tokenOutline: '#ffffff', highlight: '#ffffff' }, showGrid: false },
      data: { cells: GEN.out.cells, markers: [], rooms: GEN.out.rooms } };
    const cv = $('gd-canvas'), g = cv.getContext('2d'), G = GridCore.geom(map), { w, h } = G.mapPixelSize();
    const scale = Math.min(cv.width / w, cv.height / h);
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cv.width, cv.height);
    g.setTransform(scale, 0, 0, scale, (cv.width - w * scale) / 2, (cv.height - h * scale) / 2);
    GridCore.renderScene(g, map, { mode: 'edit', rooms: false }, { pixel: false, forExport: true, borders: scale > 0.5 });
    const doors = Object.values(GEN.out.cells).reduce((n, c) => n + (c.doors ? Object.keys(c.doors).length : 0), 0);
    $('gd-stats').textContent = `${Object.keys(GEN.out.cells).length} cells · ${GEN.out.rooms.length} rooms · ${doors} doors · seed ${GEN.out.seed}`;
    document.querySelectorAll('.gen-adv').forEach(d => d.hidden = !d.dataset.for.split(' ').includes(o.algo));
  }, 60);
}
for (const id of ['gd-grid', 'gd-algo', 'gd-w', 'gd-h', 'gd-seed', 'gd-doors', 'gd-doorchance', 'gd-rooms', 'gd-roomcount', 'gd-roommin', 'gd-roommax', 'gd-gap', 'gd-loops', 'gd-cwidth', 'gd-cmax', 'gd-windy', 'gd-deadends', 'gd-fill', 'gd-smooth', 'gd-minblob']) {
  $(id).addEventListener('input', genPreview);
}
for (const [id, suffix] of [['gd-doorchance', '%'], ['gd-loops', '%'], ['gd-windy', '%'], ['gd-deadends', '%'], ['gd-fill', '%']]) $(id).addEventListener('input', () => $(id + '-val').textContent = $(id).value + suffix);
$('gd-regen').onclick = () => { $('gd-seed').value = ''; genPreview(); };
function genMap(c) {
  $('gd-title').textContent = c ? `Generate map in ${c.name}` : 'Generate map';
  $('gd-name').value = ''; $('gd-seed').value = '';
  genPreview();
  dialog('gen-dialog', async () => {
    if (!GEN.out) return;
    const o = genOpts();
    const r = await api('/api/maps', 'POST', { name: $('gd-name').value || `Generated ${o.algo} ${GEN.out.seed}`, gridType: o.gridType, width: o.width, height: o.height, cellSize: +$('gd-cs').value,
      campaignId: c ? c.id : null, data: { cells: GEN.out.cells, markers: [], rooms: GEN.out.rooms } });
    location.href = '/map/' + r.id;
  }, 'gd-name');
}
$('btn-new-campaign').onclick = newCampaign;

// ---------------------------------------------------------------- backups
const bytes = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB';
const KIND = { auto: 'Daily', manual: 'Saved by you', 'before-restore': 'Before a restore' };
async function backupsDialog() {
  const list = h('div.backup-list');
  const file = h('input', { type: 'file', accept: '.zip,application/zip', hidden: true });
  async function draw(rows) {
    rows = rows || (await api('/api/backups')).backups;
    list.innerHTML = '';
    if (!rows.length) { list.append(h('p.hint', 'No backups yet.')); return; }
    list.append(h('table.compact', h('thead', h('tr', h('th', 'When'), h('th', 'Kind'), h('th', 'Size'), h('th', ''))),
      h('tbody', rows.map(b => h('tr',
        h('td', new Date(b.at * 1000).toLocaleString()), h('td.hint', KIND[b.kind] || b.kind), h('td.hint', bytes(b.size)),
        h('td', h('div.row.tight.end',
          h('a.btn.small', { href: `/api/backups/${encodeURIComponent(b.name)}` }, 'Download'),
          h('button.small', { type: 'button', onclick: () => restore(() => api(`/api/backups/${encodeURIComponent(b.name)}/restore`, 'POST', {}), new Date(b.at * 1000).toLocaleString()) }, 'Restore…'),
          h('button.small.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Delete the backup from ${new Date(b.at * 1000).toLocaleString()}?`, { danger: true, ok: 'Delete' })) draw((await api(`/api/backups/${encodeURIComponent(b.name)}`, 'DELETE')).backups); } }, 'Delete'))))))));
  }
  async function restore(run, label) {
    if (!await UI.confirm(`Restore the backup from ${label}? Everything (games, maps, runners, images, music) goes back to that moment, and everyone is signed out. The current state is saved as a backup first, so you can undo this.`, { danger: true, ok: 'Restore' })) return;
    try { const r = await run(); await UI.info('Backup restored', h('p', r.message)); location.href = '/login'; }
    catch (e) { toast(e.message, 6000); }
  }
  file.onchange = async () => {
    const f = file.files[0]; if (!f) return;
    file.value = '';
    restore(async () => {
      const fd = new FormData(); fd.append('file', f);
      const res = await fetch('/api/backup/restore', { method: 'POST', body: fd, headers: { 'X-Requested-With': 'ShadowGrid' } });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }, `the file ${f.name}`);
  };
  const withMusic = h('input', { type: 'checkbox', checked: true });
  const body = h('div',
    h('p.hint', 'A backup holds everything: games, maps, runners and their sheets, runs, handouts and their images, and music. One is made automatically every day without the music (the last 10 are kept); restoring one keeps the music already here.'),
    h('div.row.tight', h('button.primary', { type: 'button', onclick: async () => { toast('Saving a backup…'); draw((await api('/api/backups', 'POST', { music: withMusic.checked })).backups); toast('Backup saved.'); } }, 'Back up now'),
      h('label.check', withMusic, 'Include music'),
      h('button', { type: 'button', onclick: () => file.click() }, 'Restore from a file…'), file),
    h('div.mt', list));
  draw();
  UI.modal('Backups', body, { ok: null, cancel: 'Close', wide: true });
}
$('btn-backups').onclick = backupsDialog;
load().then(() => {
  // deep links from the game page: /?newmap=<gameId> or /?genmap=<gameId>
  const q = new URLSearchParams(location.search), id = q.get('newmap') || q.get('genmap');
  if (!id) return;
  history.replaceState(null, '', '/');
  const g = OV.games.find(x => x.id === id);
  if (g) (q.get('newmap') ? newMap : genMap)(g);
}).catch(e => { if (e.message !== 'auth') toast(e.message); });
})();
Music.attach();

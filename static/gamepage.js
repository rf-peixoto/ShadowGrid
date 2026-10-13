/* GM game dashboard: runners (approval, Karma/Nuyen, Edge, accounts), invites, runs, maps, dice log, history. */
(() => {
'use strict';
const CID = document.body.dataset.gameId;
const $ = id => document.getElementById(id);
const S = { data: null, view: 'players', version: null, gm: { dice: 6, label: '', wild: false, threshold: '', hidden: false, mode: 'pool', score: 8, idice: 1 } };
try { Object.assign(S.gm, JSON.parse(localStorage.getItem('sg.gmroller') || '{}')); } catch { /* ignore */ }

// ================================================================ tabs & polling
function setView(v) {
  if (!['players', 'runs', 'store', 'handouts', 'maps', 'log', 'sessions', 'history', 'wiki'].includes(v)) v = 'players';
  S.view = v;
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  document.querySelectorAll('.view').forEach(s => s.classList.toggle('active', s.id === 'view-' + v));
  if (location.hash !== '#' + v) history.replaceState(null, '', '#' + v);
  render();
}
document.querySelectorAll('#tabs button').forEach(b => b.onclick = () => setView(b.dataset.view));
async function load(force) {
  const d = await api(`/api/games/${CID}?since=${encodeURIComponent(force ? '' : S.version || '')}`);
  if (d.unchanged) return false;
  S.data = d; S.version = d.version;
  return true;
}
async function poll() {
  if (document.hidden || document.querySelector('dialog[open]')) return;
  const ae = document.activeElement;
  if (ae && ae.matches('input, textarea, select') && ae.closest('.page')) return;
  try { if (await load(false)) render(); } catch { /* transient */ }
}
async function reload() { await load(true); render(); }
const players = () => S.data.players;
const pname = id => (players().find(p => p.id === id) || {}).name || '(removed)';
const mapName = id => (S.data.maps.find(m => m.id === id) || {}).name;

function render() {
  if (!S.data) return;
  document.title = `${S.data.game.name} · ShadowGrid`;
  $('game-name').textContent = S.data.game.name;
  const waiting = players().filter(p => p.status === 'waiting').length;
  $('badge-waiting').hidden = !waiting; $('badge-waiting').textContent = waiting; $('badge-waiting').title = `${waiting} sheet(s) waiting for approval`;
  const active = S.data.runs.filter(r => r.status === 'Active').length;
  $('badge-runs').hidden = !active; $('badge-runs').textContent = active;
  const live = (S.data.sessions || []).find(x => x.active);
  $('badge-session').hidden = !live; $('badge-session').title = live ? `“${live.title}” is running` : '';
  ({ players: renderPlayers, runs: renderRuns, store: renderStore, handouts: renderHandouts, maps: renderMaps, sessions: renderSessions, log: renderLog, history: renderHistory, wiki: () => {} })[S.view]();
}

// ================================================================ store (stock)
const ST = { q: '', cat: 'All', show: 'all', limit: 150 };
async function setStock(ids, inStock) {
  try {
    const r = await api(`/api/games/${CID}/stock`, 'PUT', { ids, inStock });
    S.data.game.settings.outOfStock = r.outOfStock; renderStore();
  } catch (e) { toast(e.message); }
}
async function renderStore() {
  const root = $('store-root');
  const cat = await SR.catalog();
  const out = new Set(S.data.game.settings.outOfStock || []);
  const all = [...cat.store.items, ...cat.packs];
  const q = ST.q.trim().toLowerCase();
  const shown = all.filter(e => (ST.cat === 'All' || (ST.cat === 'PACKs' ? e.pack : e.cat === ST.cat && !e.pack))
    && (!q || e.name.toLowerCase().includes(q) || (e.sub || '').toLowerCase().includes(q))
    && (ST.show === 'all' || (ST.show === 'out') === out.has(e.id)));
  const focused = document.activeElement && document.activeElement.id === 'stock-search';
  root.innerHTML = '';
  root.append(h('div.section-head', h('h2', 'Store'), h('span.hint', out.size ? `${out.size} item${out.size === 1 ? '' : 's'} out of stock` : 'Everything is in stock')));
  root.append(h('p.hint', 'When the sellers run out of something, untick it: players see it as out of stock and can’t buy it (you can still give it from a sheet). Tick it again when it’s back.'));
  const search = h('input#stock-search', { type: 'search', placeholder: 'Search items and PACKs', value: ST.q, oninput: e => { ST.q = e.target.value; ST.limit = 150; renderStore(); } });
  const catSel = h('select', { 'aria-label': 'Category', onchange: e => { ST.cat = e.target.value; ST.limit = 150; renderStore(); } },
    ['All', ...cat.store.categories, 'PACKs'].map(c => h('option', { value: c, selected: c === ST.cat }, c === 'All' ? 'All categories' : c)));
  const showSel = h('select', { 'aria-label': 'Show', onchange: e => { ST.show = e.target.value; ST.limit = 150; renderStore(); } },
    [['all', 'In and out of stock'], ['in', 'In stock'], ['out', 'Out of stock']].map(([v, t]) => h('option', { value: v, selected: v === ST.show }, t)));
  const ids = shown.map(e => e.id);
  root.append(h('div.gm-toolbar.stock-bar', search, catSel, showSel, h('span.grow'),
    h('button.small', { type: 'button', disabled: !ids.some(i => out.has(i)), onclick: () => setStock(ids, true) }, 'All shown in stock'),
    h('button.small.danger', { type: 'button', disabled: !ids.some(i => !out.has(i)), onclick: async () => {
      if (ids.length > 1 && !await UI.confirm(`Mark ${ids.length} items out of stock?`, { danger: true, ok: 'Out of stock' })) return;
      setStock(ids, false);
    } }, 'All shown out of stock')));
  if (!shown.length) { root.append(h('div.card.empty', h('p', 'Nothing matches.'))); return; }
  const tb = h('tbody');
  for (const e of shown.slice(0, ST.limit)) {
    const inStock = !out.has(e.id);
    const cb = h('input', { type: 'checkbox', checked: inStock, 'aria-label': `${e.name} in stock`, onchange: ev => setStock([e.id], ev.target.checked) });
    tb.append(h('tr' + (inStock ? '' : '.out'),
      h('td', h('label.check.stock-toggle', cb, inStock ? 'In stock' : 'Out of stock')),
      h('td', h('b', e.name), e.sub ? h('span.hint', ` · ${e.sub}`) : null),
      h('td.hint', e.pack ? 'PACK' : e.cat),
      h('td.num', SR.availText ? SR.availText(e.availN, e.legalN) : e.avail),
      h('td.num', typeof e.costN === 'number' ? money(e.costN) : String(e.cost))));
  }
  root.append(h('div.card', h('table.list.stock-table', h('thead', h('tr', h('th', 'Stock'), h('th', 'Item'), h('th', 'Category'), h('th.num', 'Avail'), h('th.num', 'Price'))), tb)));
  if (shown.length > ST.limit) root.append(h('div.row.mt', h('button', { type: 'button', onclick: () => { ST.limit += 300; renderStore(); } }, `Show more (${shown.length - ST.limit} left)`)));
  if (focused) { const el = $('stock-search'); el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
}

// ================================================================ runners
function miniCM(cm) {
  const bar = (d, m, cls) => h('div.bar.' + cls, { title: `${cls === 'p' ? 'Physical' : 'Stun'} ${Math.min(d, m)}/${m}` }, h('span', { style: { width: `${Math.max(0, m - Math.min(d, m)) / m * 100}%` } }));
  return h('div.mini-cm', bar(cm.p, cm.pm, 'p'), bar(cm.s, cm.sm, 's'));
}
function renderPlayers() {
  const root = $('players-root'); root.innerHTML = '';
  const ps = [...players()].sort((a, b) => (a.status === 'waiting' ? 0 : 1) - (b.status === 'waiting' ? 0 : 1));
  root.append(h('div.section-head', h('h2', 'Runners'), h('div.row.tight',
    h('button.primary', { type: 'button', onclick: async () => { await SR.invite(CID, S.data.game.name); reload(); } }, 'Invite player'))));
  if (ps.length) root.append(h('div.gm-toolbar',
    h('span.tb-label', 'Between runs'),
    h('button', { type: 'button', onclick: () => award(null) }, 'Award Karma / Nuyen…'),
    h('button', { type: 'button', onclick: () => edge('all', 'refresh'), title: 'Every runner back to their Edge rating' }, 'Refresh everyone’s Edge'),
    h('button', { type: 'button', onclick: chargeLifestyle, title: 'Start of a new month: every runner pays their lifestyle' }, 'Charge monthly lifestyle'),
    h('button', { type: 'button', onclick: substanceLibrary, title: 'The toxins, drugs and diseases of this game' }, 'Toxins & drugs…'),
    h('span.grow'),
    h('button.ghost', { type: 'button', onclick: storeSettings, title: 'How much the store pays for gear players sell' }, `Store buys gear at ${(S.data.game.settings || {}).sellPct ?? 50}%`)));
  const waiting = ps.filter(p => p.status === 'waiting');
  if (waiting.length) root.append(h('div.banner.warn', h('p', h('b', `${waiting.length} sheet${waiting.length > 1 ? 's' : ''} waiting for your approval: `), waiting.map(p => p.name).join(', ')),
    h('a.btn.primary', { href: `/game/${CID}/sheet/${waiting[0].id}` }, 'Review')));
  if (!ps.length) {
    root.append(h('div.card.empty', h('h3', 'No runners yet'), h('p', 'Invite your players. Each invite link works once; the player picks a username and password and lands on their character sheet.'),
      h('button.primary', { type: 'button', onclick: async () => { await SR.invite(CID, S.data.game.name); reload(); } }, 'Invite player')));
  } else {
    const t = h('table.list.players-table', h('thead', h('tr', h('th', 'Runner'), h('th', 'Sheet'), h('th', 'Condition'), h('th', 'Edge'), h('th.right', 'Karma'), h('th.right', 'Nuyen'), h('th', 'Where'), h('th', ''))));
    const tb = h('tbody');
    for (const p of ps) {
      const online = p.lastSeen && Date.now() / 1000 - p.lastSeen < 90;
      tb.append(h('tr',
        h('td', h('div.player-name', h('span.dot', { style: { background: p.color } }), h('a', { href: `/game/${CID}/sheet/${p.id}` }, p.name)),
          h('div.hint', '@' + p.username, ' · ', [p.metatype, p.role].filter(Boolean).join(' '), ' · ', online ? h('span.good', 'online') : (p.lastSeen ? 'seen ' + timeAgo(p.lastSeen) : 'never signed in'))),
        h('td', SR.statusTag(p.status), p.pendingContacts ? h('div', h('a.tag.waiting', { href: `/game/${CID}/sheet/${p.id}`, title: 'New or changed contacts to confirm' }, `${p.pendingContacts} contact${p.pendingContacts > 1 ? 's' : ''} to confirm`)) : null),
        h('td', h('div.row.tight', miniCM(p.cm), SR.healthTag(p.cm.status), p.os ? h('a.chip.os-chip' + (p.os >= 30 ? '.hot' : ''), { href: `/game/${CID}/sheet/${p.id}`, title: 'Overwatch Score (players don’t see it). At 40 the GOD converges.' }, h('span.k', 'OS'), h('b', p.os)) : null)),
        h('td.nowrap', h('div.row.tight', SR.pips(p.edge.cur, p.edge.max),
          h('button.small.ghost', { type: 'button', title: 'Take 1 Edge', disabled: !p.edge.cur, onclick: () => edge([p.id], 'lose') }, '−'),
          h('button.small.ghost', { type: 'button', title: 'Award 1 Edge (max 7)', disabled: p.edge.cur >= 7, onclick: () => edge([p.id], 'gain') }, '+'),
          h('button.small.ghost', { type: 'button', title: 'Refresh to Edge rating', onclick: () => edge([p.id], 'refresh') }, '↻'))),
        h('td.right.num', p.karma), h('td.right.num.nowrap', { class: p.nuyen < 0 ? 'bad' : '' }, money(p.nuyen)),
        h('td.hint.where', p.currentMapId ? h('a', { href: `/map/${p.currentMapId}?view=${p.id}` }, mapName(p.currentMapId) || 'map') : 'not placed'),
        h('td.right.nowrap',
          h('a.btn.small' + (p.status === 'waiting' ? '.primary' : ''), { href: `/game/${CID}/sheet/${p.id}` }, p.status === 'waiting' ? 'Review sheet' : 'Sheet'), ' ',
          h('button.small', { type: 'button', onclick: () => award([p.id]) }, 'Award'), ' ',
          accountMenu(p))));
    }
    t.append(tb);
    root.append(h('div.card', h('div.table-wrap', t)));
  }
  // invites
  const open = S.data.invites.filter(i => !i.usedBy && i.expiresAt > Date.now() / 1000);
  const card = h('div.card', h('h3', 'Invite links', h('button.small', { type: 'button', onclick: async () => { await SR.invite(CID, S.data.game.name); reload(); } }, 'New invite')));
  if (!open.length) card.append(h('p.hint', 'No open invites. Used and expired links are cleaned up from this list.'));
  for (const i of open) {
    const url = `${location.origin}/invite/${i.token}`;
    card.append(h('div.invite-row', h('code', url), h('span.hint', `expires ${new Date(i.expiresAt * 1000).toLocaleDateString()}`),
      h('button.small', { type: 'button', onclick: async () => { try { await navigator.clipboard.writeText(url); toast('Copied.'); } catch { UI.prompt('Invite link', 'Copy this link', { value: url }); } } }, 'Copy'),
      h('button.small.danger', { type: 'button', onclick: async () => { await api(`/api/invites/${i.token}`, 'DELETE'); toast('Invite revoked.'); reload(); } }, 'Revoke')));
  }
  root.append(card);
}
function accountMenu(p) {
  const sel = h('select.small', { title: 'Account', onchange: async e => {
    const v = e.target.value; e.target.value = '';
    if (v === 'pw') {
      if (!await UI.confirm(`Reset ${p.name}'s password? They are signed out and need the new password you'll get next.`, { ok: 'Reset' })) return;
      const r = await api(`/api/players/${p.id}/password`, 'POST', {});
      UI.info('New password', h('div', h('p', `Give this password to ${p.name} (username `, h('b', p.username), '):'), h('p', h('code', { style: { fontSize: '1.2rem' } }, r.password)), h('p.hint', 'They can change it from their account menu.')));
    } else if (v === 'unplace') {
      await api(`/api/players/${p.id}/unplace`, 'POST', {}); toast('Token removed from the map.'); reload();
    } else if (v === 'del') {
      if (!await UI.confirm(`Remove ${p.name} (@${p.username}) from the game? Their account and character are deleted for good.`, { danger: true, ok: 'Remove runner' })) return;
      await api(`/api/players/${p.id}`, 'DELETE'); toast('Runner removed.'); reload();
    }
  } }, option('', 'More…'), option('pw', 'Reset password'), p.currentMapId ? option('unplace', 'Take token off the map') : null, option('del', 'Remove from game'));
  return sel;
}
function selector(selected) {
  const box = h('div.selector');
  const all = h('label', h('input', { type: 'checkbox', checked: selected === null, onchange: e => box.querySelectorAll('input[data-id]').forEach(i => { i.checked = e.target.checked; }) }), 'Everyone');
  box.append(all);
  for (const p of players()) box.append(h('label', h('input', { type: 'checkbox', dataset: { id: p.id }, checked: selected === null || (selected || []).includes(p.id),
    onchange: () => { all.querySelector('input').checked = [...box.querySelectorAll('input[data-id]')].every(i => i.checked); } }), p.name));
  box.value = () => [...box.querySelectorAll('input[data-id]:checked')].map(i => i.dataset.id);
  return box;
}
async function award(ids) {
  const sel = selector(ids);
  const karma = h('input', { type: 'number', value: 0 }), nuyen = h('input', { type: 'number', value: 0, step: 100 });
  const reason = h('input', { placeholder: 'e.g. Session 4, good roleplay', maxlength: 120 });
  const ok = await UI.modal('Award Karma / Nuyen', h('div', h('p.hint', 'Use negative numbers to take Karma or Nuyen away (never below 0, unless the runner is already in debt). It shows in each runner’s history.'),
    h('label.stack', 'Runners', sel), h('div.form-grid', h('label', 'Karma', karma), h('label', 'Nuyen', nuyen)), h('label.stack', 'Reason', reason)), { ok: 'Apply' });
  if (!ok) return;
  const who = sel.value();
  if (!who.length) { toast('Pick at least one runner.'); return; }
  try { const r = await api(`/api/games/${CID}/grant`, 'POST', { players: who.length === players().length ? 'all' : who, karma: +karma.value || 0, nuyen: +nuyen.value || 0, reason: reason.value }); toast(`Applied to ${r.count} runner${r.count > 1 ? 's' : ''}.`); reload(); }
  catch (e) { toast(e.message); }
}
async function chargeLifestyle() {
  const list = players().map(p => p.name).join(', ');
  if (!await UI.confirm(`Charge one month of lifestyle to every runner (${list})? Runners who can't pay go into debt (negative nuyen).`, { ok: 'Charge' })) return;
  try { const r = await api(`/api/games/${CID}/lifestyle`, 'POST', {}); toast(`Lifestyle charged to ${r.count} runner${r.count > 1 ? 's' : ''}. See the log for amounts.`); reload(); }
  catch (e) { toast(e.message); }
}
async function storeSettings() {
  const cur = (S.data.game.settings || {}).sellPct ?? 50;
  const v = await UI.prompt('Store buy-back', 'Percentage of an item’s price the store pays when a runner sells it (0-100)', { type: 'number', value: cur, min: 0, ok: 'Save',
    hint: 'Selling also needs a contact who could get that item.' });
  if (v === null) return;
  try { await api(`/api/games/${CID}/settings`, 'PUT', { sellPct: +v }); toast(`The store now pays ${Math.max(0, Math.min(100, +v))}%.`); reload(); }
  catch (e) { toast(e.message); }
}
async function edge(who, action) {
  try { await api(`/api/games/${CID}/edge`, 'POST', { players: who, action }); if (action === 'refresh') toast(who === 'all' ? 'Everyone’s Edge refreshed.' : 'Edge refreshed.'); reload(); }
  catch (e) { toast(e.message); }
}

// ================================================================ runs
function renderRuns() {
  const root = $('runs-root'); root.innerHTML = '';
  root.append(h('div.section-head', h('h2', 'Runs'), h('button.primary', { type: 'button', onclick: () => editRun(null) }, 'New run')));
  root.append(h('p.hint', 'Players see the runs they are assigned to, read-only. Tick tasks as they happen; completing a run pays every assigned runner the full payout.'));
  if (!S.data.runs.length) { root.append(h('div.card.empty', h('h3', 'No runs yet'), h('p', 'Create a contract with a reward, a few tasks and the runners who take it.'), h('button.primary', { type: 'button', onclick: () => editRun(null) }, 'New run'))); return; }
  for (const r of S.data.runs) root.append(runCard(r));
}
function runCard(r) {
  const activeRun = r.status === 'Active';
  const tasks = h('ul.tasks');
  r.tasks.forEach((t, i) => tasks.append(h('li' + (t.completed ? '.done' : ''),
    activeRun ? h('input', { type: 'checkbox', checked: t.completed, onchange: e => tickTask(r, i, e.target.checked), 'aria-label': 'Done' }) : h('span.tick', t.completed ? '✓' : ''),
    h('span.t', t.description), t.mandatory ? h('span.mand', { title: 'Mandatory' }, '*') : null)));
  const who = r.assignees.length ? r.assignees.map(id => { const p = players().find(x => x.id === id); return h('span.chip', p ? h('span.dot', { style: { background: p.color } }) : null, pname(id)); }) : [h('span.warn', 'Nobody assigned yet')];
  const money_ = r.status === 'Completed' ? h('span', 'Paid ', h('b.good', money(r.payout)), ' to each runner ', h('span.hint', timeAgo(r.completedAt))) :
    h('span', 'Reward ', h('b', money(r.reward)), r.tasks.length ? h('span.hint', ` · payout now ${money(r.scaledPayout)} (${r.progress}% of tasks)`) : '');
  const actions = h('div.row.tight');
  if (activeRun) {
    actions.append(h('button.primary', { type: 'button', disabled: !r.mandatoryDone || !r.assignees.length, title: !r.mandatoryDone ? 'Tick every mandatory task first' : !r.assignees.length ? 'Assign runners first' : '', onclick: () => completeRun(r) }, 'Complete & pay…'),
      h('button', { type: 'button', onclick: () => editRun(r) }, 'Edit'),
      h('button', { type: 'button', onclick: async () => { if (await UI.confirm(`Abandon “${r.name}”? Nobody gets paid.`, { ok: 'Abandon' })) { await api(`/api/runs/${r.id}/abandon`, 'POST', {}); reload(); } } }, 'Abandon'));
  }
  if (r.status === 'Abandoned') actions.append(h('button', { type: 'button', onclick: async () => { await api(`/api/runs/${r.id}/reopen`, 'POST', {}); reload(); } }, 'Reopen'));
  actions.append(h('button.ghost.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Delete “${r.name}”? Payouts already made stay with the runners.`, { danger: true, ok: 'Delete' })) { await api(`/api/runs/${r.id}`, 'DELETE'); reload(); } } }, 'Delete'));
  return h('div.run-card' + (r.status === 'Abandoned' ? '.dim' : ''),
    h('div.head', h('h3', r.name), h('span.tag.' + r.status.toLowerCase(), r.status)),
    r.description ? h('p', { style: { whiteSpace: 'pre-wrap' } }, r.description) : null,
    h('div.row.tight', h('span.hint', 'Runners:'), who),
    r.tasks.length ? h('div.bar', h('span', { style: { width: r.progress + '%' } })) : null,
    r.tasks.length ? tasks : null,
    money_, actions);
}
async function tickTask(r, i, val) {
  const tasks = r.tasks.map((t, j) => j === i ? { ...t, completed: val } : t);
  try { await api(`/api/runs/${r.id}`, 'PUT', { tasks }); reload(); } catch (e) { toast(e.message); }
}
async function completeRun(r) {
  const pay = h('input', { type: 'number', min: 0, value: r.scaledPayout });
  const ok = await UI.modal(`Complete “${r.name}”`, h('div',
    h('p', `${r.tasks.filter(t => t.completed).length} of ${r.tasks.length} tasks done, so the payout is ${money(r.scaledPayout)} (reward ${money(r.reward)}). You can change it.`),
    h('label.stack', 'Each runner gets (¥)', pay),
    h('p.hint', 'Paid to: ' + r.assignees.map(pname).join(', '))), { ok: 'Complete & pay' });
  if (!ok) return;
  try { await api(`/api/runs/${r.id}/complete`, 'POST', { payout: +pay.value || 0 }); toast('Run completed. Runners paid.'); reload(); } catch (e) { toast(e.message); }
}
async function editRun(r) {
  r = r || { name: '', description: '', reward: 0, tasks: [], assignees: players().map(p => p.id) };
  const name = h('input', { value: r.name, required: true, maxlength: 120, placeholder: 'e.g. Shiawase data grab' });
  const reward = h('input', { type: 'number', min: 0, step: 500, value: r.reward });
  const desc = h('textarea', { rows: 4, placeholder: 'The job, as Mr. Johnson tells it…' }, r.description);
  const tasks = r.tasks.map(t => ({ ...t }));
  const list = h('div.col');
  const newTask = h('input', { placeholder: 'Add a task and press Enter', onkeydown: e => { if (e.key === 'Enter') { e.preventDefault(); addTask(); } } });
  const newMand = h('input', { type: 'checkbox', checked: true });
  function addTask() { const v = newTask.value.trim(); if (!v) return; tasks.push({ description: v, mandatory: newMand.checked, completed: false }); newTask.value = ''; drawTasks(); newTask.focus(); }
  function drawTasks() {
    list.innerHTML = '';
    tasks.forEach((t, i) => list.append(h('div.task-edit',
      h('input', { value: t.description, oninput: e => { t.description = e.target.value; } }),
      h('label.check', { title: 'Must be done before the run can be completed' }, h('input', { type: 'checkbox', checked: t.mandatory, onchange: e => { t.mandatory = e.target.checked; } }), 'Mandatory'),
      h('button.small.danger', { type: 'button', onclick: () => { tasks.splice(i, 1); drawTasks(); } }, '✕'))));
    if (!tasks.length) list.append(h('p.hint', 'No tasks: the full reward is paid on completion.'));
  }
  drawTasks();
  const sel = selector(r.assignees.length === players().length && players().length ? null : r.assignees);
  const ok = await UI.modal(r.id ? `Edit “${r.name}”` : 'New run', h('div',
    h('div.form-grid', h('label', 'Name', name), h('label', 'Reward per runner (¥)', reward)),
    h('label.stack', 'Description (players see this)', desc),
    h('h3', 'Tasks'), list, h('div.task-edit', newTask, h('label.check', newMand, 'Mandatory'), h('button.small', { type: 'button', onclick: addTask }, 'Add')),
    h('p.hint', 'The payout scales with the share of tasks completed. Mandatory tasks (*) must be ticked before you can complete the run.'),
    h('h3', 'Runners'), players().length ? sel : h('p.hint', 'Invite players first; you can assign them later.')), { ok: r.id ? 'Save' : 'Create run', wide: true });
  if (!ok) return;
  if (newTask.value.trim()) addTask();
  const bodyOut = { name: name.value.trim(), reward: +reward.value || 0, description: desc.value, tasks: tasks.filter(t => t.description.trim()), assignees: players().length ? sel.value() : [] };
  try { await api(r.id ? `/api/runs/${r.id}` : `/api/games/${CID}/runs`, r.id ? 'PUT' : 'POST', bodyOut); toast(r.id ? 'Run updated.' : 'Run created. Assigned runners can see it now.'); reload(); }
  catch (e) { toast(e.message); }
}

// ================================================================ toxins, drugs and diseases
const VECTORS = ['Contact', 'Ingestion', 'Inhalation', 'Injection'];
const EFFECTS = ['Dazed', 'Nauseated', 'Immobilized', 'Blinded I', 'Fatigued I', 'Fatigued II', 'Confused II', 'Frightened', 'Ongoing'];
const CORE_ATTRS = ['Body', 'Agility', 'Reaction', 'Strength', 'Willpower', 'Logic', 'Intuition', 'Charisma'];
async function substanceLibrary() {
  let list = (S.data.substances || []).filter(x => !x.builtin).map(x => ({ ...x }));
  const box = h('div');
  const effectText = x => [x.damage ? `${x.damage === 'P' ? 'Physical' : 'Stun'} damage` : '', ...(x.effects || []), Object.entries(x.attrs || {}).map(([a, v]) => `${a} ${v > 0 ? '+' : ''}${v}`).join(', '), x.init_dice ? `+${x.init_dice}D6 Init` : '',
    Object.entries(x.skills || {}).map(([k, v]) => `${k} ${v > 0 ? '+' : ''}${v}`).join(', '), x.pool ? `${x.pool > 0 ? '+' : ''}${x.pool} all tests` : '',
    x.pool_physical ? `${x.pool_physical} Physical tests` : '', x.hpt ? 'High Pain Tolerance' : '', x.crash ? 'crash' : ''].filter(Boolean).join(' · ');
  const table = (rows, actions) => h('table.compact.substances', h('thead', h('tr', h('th', 'Name'), h('th', 'Kind'), h('th.num', 'Power'), h('th', 'Effect'), h('th', ''))),
    h('tbody', rows.map(x => h('tr', h('td', h('b', x.name), x.source && x.source !== 'Custom' ? h('span.hint', ` · ${x.source}`) : null), h('td', x.kind), h('td.num', x.power),
      h('td.hint', effectText(x)), h('td', h('div.row.tight.end', actions(x)))))));
  function draw() {
    box.innerHTML = '';
    const builtin = (S.data.substances || []).filter(x => x.builtin);
    box.append(h('p.hint', 'Runners resist with Body + Willpower; each hit lowers the Power by 1, and what is left applies (damage, statuses, a drug’s bonuses). Expose a runner from their sheet (Combat); players take drugs they carry from their own sheet, and the store sells the core book’s toxins and drugs by the dose (Medical).'),
      h('h4.mt', 'Your substances'),
      list.length ? table(list, x => [
        h('button.small', { type: 'button', onclick: async () => { const e = await editSubstance(x); if (e) { Object.assign(x, e); draw(); } } }, 'Edit'),
        h('button.small.danger', { type: 'button', title: 'Remove', onclick: () => { list = list.filter(y => y !== x); draw(); } }, '✕')])
        : h('p.hint', 'None yet. Add your own, or copy a built-in one to change it.'),
      h('button.mt', { type: 'button', onclick: async () => { const e = await editSubstance(null); if (e) { list.push(e); draw(); } } }, '+ New toxin, drug or disease'),
      h('details.mt', h('summary', `Built in: the core rulebook and the Sixth World Companion (${builtin.length})`),
        table(builtin, x => h('button.small.ghost', { type: 'button', title: 'Make an editable copy', onclick: () => {
          const { builtin: _b, id: _i, ...rest } = x;
          list.push(JSON.parse(JSON.stringify({ ...rest, name: `${x.name} (house)`, source: 'Custom' }))); draw();
        } }, 'Copy'))));
  }
  draw();
  if (!await UI.modal('Toxins & drugs', box, { ok: 'Save library', wide: true })) return;
  try { const r = await api(`/api/games/${CID}/substances`, 'PUT', { substances: list }); S.data.substances = r.substances; toast('Library saved.'); } catch (e) { toast(e.message); }
}
async function editSubstance(x) {
  x = x || { name: '', kind: 'toxin', vectors: ['Injection'], speed: 'Immediate', power: 8, duration: '', damage: 'S', effects: [], attrs: {}, init_dice: 0, addiction: 0, crash: null, desc: '' };
  const num = (v, min, max) => h('input', { type: 'number', min, max, value: v || 0, style: { width: '4.2rem' } });
  const name = h('input', { value: x.name, required: true, maxlength: 60 });
  const kind = h('select', ['toxin', 'drug', 'disease'].map(k => option(k, k, x.kind === k)));
  const power = h('input', { type: 'number', min: 0, max: 30, value: x.power });
  const speed = h('input', { value: x.speed || '', placeholder: 'Immediate, 1 combat round…' }), duration = h('input', { value: x.duration || '', placeholder: 'e.g. 10 × 1D6 minutes' });
  const damage = h('select', option('', 'No damage', !x.damage), option('S', 'Stun', x.damage === 'S'), option('P', 'Physical', x.damage === 'P'));
  const vec = VECTORS.map(v => h('label.check', h('input', { type: 'checkbox', checked: (x.vectors || []).includes(v), dataset: { v } }), v));
  const effBoxes = list => EFFECTS.map(v => h('label.check', h('input', { type: 'checkbox', checked: (list || []).includes(v), dataset: { v } }), v));
  const eff = effBoxes(x.effects);
  const attrRow = src => CORE_ATTRS.map(a => h('label', a.slice(0, 3), h('input', { type: 'number', min: -6, max: 6, value: (src || {})[a] || 0, dataset: { a }, style: { width: '3.6rem' } })));
  const attrs = attrRow(x.attrs);
  const initd = num(x.init_dice, 0, 4), addiction = num(x.addiction, 0, 10);
  const pool = num(x.pool, -6, 6), poolPhys = num(x.pool_physical, -6, 6), perc = num((x.skills || {}).Perception, -6, 6), hpt = num(x.hpt, 0, 3);
  const cr = x.crash || {};
  const crashDv = num(cr.dv, 0, 30), crashType = h('select', option('S', 'Stun', cr.damage !== 'P'), option('P', 'Physical', cr.damage === 'P'));
  const crashEff = effBoxes(cr.effects), crashAttrs = attrRow(cr.attrs), crashPool = num(cr.pool, -6, 6);
  const crashDur = h('input', { value: cr.duration || '', placeholder: 'e.g. as long as the effect lasted' });
  const desc = h('textarea', { rows: 2, maxlength: 600 }, x.desc || '');
  const ok = await UI.modal(x.name ? `Edit ${x.name}` : 'New substance', h('div',
    h('div.form-grid', h('label', 'Name', name), h('label', 'Kind', kind), h('label', 'Power', power), h('label', 'Speed', speed), h('label', 'Duration', duration), h('label', 'Damage (equal to the Power left)', damage)),
    h('h4.mt', 'Vectors'), h('div.row', vec),
    h('h4.mt', 'Statuses while it lasts'), h('div.row', eff),
    h('h4.mt', 'Effects while it lasts'), h('div.row.tight', attrs, h('label', 'Init dice', initd)),
    h('div.row.tight.mt', h('label', 'All tests ±', pool), h('label', 'Physical tests ±', poolPhys), h('label', 'Perception ±', perc), h('label', 'High Pain Tolerance', hpt)),
    h('details.mt', { open: !!x.crash }, h('summary', 'Crash (when it wears off)'),
      h('div.row.tight', h('label', 'Unresisted damage', crashDv), crashType, h('label', 'All tests ±', crashPool), h('label.grow', 'Lasts', crashDur)),
      h('div.row.tight.mt', crashAttrs), h('div.row.mt', crashEff)),
    h('div.form-grid.mt', h('label', 'Addiction test threshold (0 = none)', addiction)),
    h('label.stack', 'Notes', desc)), { ok: 'Done', wide: true });
  if (!ok) return null;
  const pick = boxes => boxes.map(l => l.querySelector('input')).filter(i => i.checked).map(i => i.dataset.v);
  const readAttrs = row => { const at = {}; row.forEach(l => { const i = l.querySelector('input'); if (+i.value) at[i.dataset.a] = +i.value; }); return at; };
  const crash = { dv: +crashDv.value || 0, damage: crashType.value, effects: pick(crashEff), attrs: readAttrs(crashAttrs), pool: +crashPool.value || 0,
    duration: crashDur.value.trim(), zero: cr.zero || [] };
  const hasCrash = crash.dv || crash.effects.length || Object.keys(crash.attrs).length || crash.pool || crash.zero.length || crash.duration;
  const skills = Object.assign({}, x.skills || {}); if (+perc.value) skills.Perception = +perc.value; else delete skills.Perception;
  return { id: x.id, name: name.value.trim(), kind: kind.value, power: +power.value || 0, speed: speed.value, duration: duration.value, damage: damage.value,
    vectors: pick(vec), effects: pick(eff), attrs: readAttrs(attrs), init_dice: +initd.value || 0, addiction: +addiction.value || 0,
    pool: +pool.value || 0, pool_physical: +poolPhys.value || 0, hpt: +hpt.value || 0, skills, sustain: x.sustain || 0,
    crash: hasCrash ? crash : null, desc: desc.value, source: x.source && x.source !== 'Custom' ? x.source : 'Custom' };
}

// ================================================================ sessions
const EVENT_ICON = { attack: '⚔', roll: '🎲', note: '•', ledger: '¥', run: '◆', handout: '✉', init: '⏱' };
function statChips(st) {
  return h('div.row.tight.session-stats',
    h('span.chip', h('span.k', 'Length'), h('b', `${st.minutes} min`)),
    h('span.chip', h('span.k', 'Fights'), h('b', st.fights)),
    h('span.chip', { title: `${st.hits} of ${st.attacks} attacks did damage` }, h('span.k', 'Attacks landed'), h('b', `${st.hits} of ${st.attacks}`)),
    h('span.chip', h('span.k', 'Rolls'), h('b', st.rolls)),
    st.glitches || st.critical ? h('span.chip', h('span.k', 'Glitches'), h('b', st.glitches + st.critical)) : null,
    h('span.chip', h('span.k', 'Awarded'), h('b', `${st.karma} K · ${money(st.nuyen)}`)));
}
function timeline(events, open) {
  const list = h('ol.timeline');
  for (const e of events.filter(x => x.kind !== 'init')) {
    list.append(h('li.' + e.kind + (e.hidden ? '.hidden' : '') + (e.flag ? '.' + e.flag : ''),
      h('span.t', new Date(e.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })),
      h('span.i', EVENT_ICON[e.kind] || '•'),
      h('span.x', e.kind === 'note' ? `${e.who} ${e.text}` : e.text, e.hidden ? h('span.hint', ' (hidden)') : null)));
  }
  return h('details.timeline-wrap', { open }, h('summary', `Timeline (${list.children.length})`), list.children.length ? list : h('p.hint', 'Nothing happened yet.'));
}
function renderSessions() {
  const root = $('sessions-root'); root.innerHTML = '';
  const list = S.data.sessions || [];
  const live = list.find(x => x.active);
  root.append(h('div.section-head', h('h2', 'Sessions'),
    live ? h('button.primary', { type: 'button', onclick: () => endSession(live) }, 'End session') :
      h('button.primary', { type: 'button', onclick: startSession }, 'Start session')));
  root.append(h('p.hint', 'Start a session when the table sits down and end it afterwards. Fights, rolls, awards, runs and handouts in between become a recap you can annotate, share with the players and export.'));
  if (!list.length) { root.append(h('div.card.empty', h('h3', 'No sessions yet'), h('p', 'Start one at the beginning of your next game night.'), h('button.primary', { type: 'button', onclick: startSession }, 'Start session'))); return; }
  for (const s of list) root.append(sessionCard(s));
}
function sessionCard(s) {
  const rc = s.recap || { events: [], stats: { minutes: 0, fights: 0, attacks: 0, hits: 0, rolls: 0, glitches: 0, critical: 0, karma: 0, nuyen: 0, damage: [] } };
  const st = rc.stats;
  const notes = h('textarea', { rows: 4, maxlength: 30000, placeholder: 'What happened, in your words (Markdown). Players see it when you share the session.' }, s.notes);
  notes.onchange = () => api(`/api/sessions/${s.id}`, 'PUT', { notes: notes.value }).then(() => toast('Notes saved.')).catch(e => toast(e.message));
  const when = new Date(s.startedAt * 1000);
  const highlights = h('ul.plain.highlights',
    st.best ? h('li', 'Best roll: ', h('b', st.best.text)) : null,
    (st.damage || []).map(([n, v]) => h('li', `${n} dealt ${v} boxes of damage`)));
  return h('div.run-card.session' + (s.active ? '.live' : ''),
    h('div.head', h('h3', { contenteditable: 'true', spellcheck: 'false', title: 'Click to rename',
      onblur: e => { const t = e.target.textContent.trim(); if (t && t !== s.title) api(`/api/sessions/${s.id}`, 'PUT', { title: t }).then(reload).catch(x => toast(x.message)); else e.target.textContent = s.title; },
      onkeydown: e => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } } }, s.title),
      s.active ? h('span.tag.active', 'Running') : h('span.hint', `${when.toLocaleDateString()} ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`)),
    statChips(st), highlights.children.length ? highlights : null,
    h('label.stack', 'Your notes', notes),
    timeline(rc.events, s.active),
    h('div.row.tight',
      s.active ? h('button.primary', { type: 'button', onclick: () => endSession(s) }, 'End session') :
        h('label.check', { title: 'Players see the recap and your notes in their Runs tab (without hidden rolls)' },
          h('input', { type: 'checkbox', checked: s.shared, onchange: e => api(`/api/sessions/${s.id}`, 'PUT', { shared: e.target.checked }).then(() => { toast(e.target.checked ? 'Shared with the players.' : 'No longer shared.'); reload(); }) }), 'Share with players'),
      !s.active ? h('a.btn.small', { href: `/api/sessions/${s.id}/export` }, 'Export (.md)') : null,
      h('button.ghost.danger.small', { type: 'button', onclick: async () => { if (await UI.confirm(`Delete the session “${s.title}” and its recap? The table log and history are not affected.`, { danger: true, ok: 'Delete' })) { await api(`/api/sessions/${s.id}`, 'DELETE'); reload(); } } }, 'Delete')));
}
async function startSession() {
  const n = (S.data.sessions || []).length + 1;
  const t = await UI.prompt('Start a session', 'Title', { value: `Session ${n}`, ok: 'Start', required: false });
  if (t === null) return;
  try { await api(`/api/games/${CID}/sessions`, 'POST', { title: t }); toast('Session started. Have a good game.'); reload(); } catch (e) { toast(e.message); }
}
async function endSession(s) {
  if (!await UI.confirm(`End “${s.title}”? Its recap is saved; you can still edit the notes and share it.`, { ok: 'End session' })) return;
  try { await api(`/api/sessions/${s.id}/end`, 'POST', {}); toast('Session ended. The recap is saved.'); reload(); } catch (e) { toast(e.message); }
}

// ================================================================ handouts
function recipientsText(rec) {
  if (rec === 'all') return [h('span.chip', 'Every runner')];
  if (!rec.length) return [h('span.warn', 'Nobody yet')];
  return rec.map(id => { const p = players().find(x => x.id === id); return h('span.chip', p ? h('span.dot', { style: { background: p.color } }) : null, pname(id)); });
}
function renderHandouts() {
  const root = $('handouts-root'); root.innerHTML = '';
  root.append(h('div.section-head', h('h2', 'Handouts'), h('button.primary', { type: 'button', onclick: () => editHandout(null) }, 'New handout')));
  root.append(h('p.hint', 'Dossiers, maps, photos and messages for the runners. A handout stays hidden until you show it; then the runners you picked find it in their Handouts tab.'));
  const list = S.data.handouts || [];
  if (!list.length) { root.append(h('div.card.empty', h('h3', 'No handouts yet'), h('p', 'Write a note in Markdown, add a PNG or JPEG image, and choose who gets it.'), h('button.primary', { type: 'button', onclick: () => editHandout(null) }, 'New handout'))); return; }
  for (const ho of list) root.append(handoutCard(ho, true));
}
function handoutCard(ho, gm) {
  const img = ho.image ? h('a.handout-img', { href: `/uploads/${ho.image}`, target: '_blank', rel: 'noopener', title: 'Open the full image' }, h('img', { src: `/uploads/${ho.image}`, alt: ho.title, loading: 'lazy' })) : null;
  const actions = gm ? h('div.row.tight',
    h('button' + (ho.shown ? '' : '.primary'), { type: 'button', onclick: () => saveHandout(ho, { shown: !ho.shown }, ho.shown ? 'Hidden from the runners.' : 'Shown to the runners.') }, ho.shown ? 'Hide from runners' : 'Show to runners'),
    h('button', { type: 'button', onclick: () => editHandout(ho) }, 'Edit'),
    h('button.ghost.danger', { type: 'button', onclick: async () => { if (await UI.confirm(`Delete the handout “${ho.title}”?`, { danger: true, ok: 'Delete' })) { await api(`/api/handouts/${ho.id}`, 'DELETE'); reload(); } } }, 'Delete')) : null;
  return h('div.run-card.handout' + (gm && !ho.shown ? '.dim' : ''),
    h('div.head', h('h3', ho.title), gm ? h('span.tag.' + (ho.shown ? 'active' : 'abandoned'), ho.shown ? 'Shown' : 'Hidden') : h('span.hint', ho.shownAt ? timeAgo(ho.shownAt) : '')),
    h('div.handout-body', img, ho.body ? renderMarkdown(ho.body) : null),
    gm ? h('div.row.tight', h('span.hint', 'For:'), recipientsText(ho.recipients)) : null,
    actions);
}
async function saveHandout(ho, patch, msg) {
  try { await api(`/api/handouts/${ho.id}`, 'PUT', patch); toast(msg); reload(); } catch (e) { toast(e.message); }
}
async function editHandout(ho) {
  ho = ho || { title: '', body: '', image: null, recipients: 'all', shown: false };
  let image = ho.image;
  const title = h('input', { value: ho.title, required: true, maxlength: 120, placeholder: 'e.g. Dossier: Dr. Kessler' });
  const text = h('textarea', { rows: 10, maxlength: 20000, placeholder: '# Heading\n**bold**, *italic*, - lists, > quotes, [links](https://…)' }, ho.body);
  const preview = h('div.md-preview');
  const drawPreview = () => { preview.innerHTML = ''; preview.append(text.value.trim() ? renderMarkdown(text.value) : h('p.hint', 'The preview appears here.')); };
  text.oninput = drawPreview; drawPreview();
  const imgBox = h('div.handout-upload');
  const file = h('input', { type: 'file', accept: '.png,.jpg,.jpeg,image/png,image/jpeg', hidden: true });
  function drawImage() {
    imgBox.innerHTML = '';
    if (image) imgBox.append(h('img', { src: `/uploads/${image}`, alt: '' }), h('button.small', { type: 'button', onclick: () => { image = null; drawImage(); } }, 'Remove image'));
    imgBox.append(h('button.small', { type: 'button', onclick: () => file.click() }, image ? 'Replace image…' : 'Add an image…'), h('span.hint', 'PNG or JPEG, up to 8 MB'), file);
  }
  file.onchange = async () => {
    const f = file.files[0]; file.value = ''; if (!f) return;
    if (!/\.(png|jpe?g)$/i.test(f.name)) { toast('Only .png, .jpg and .jpeg images.'); return; }
    const fd = new FormData(); fd.append('file', f);
    try {
      const res = await fetch(`/api/games/${CID}/uploads`, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'ShadowGrid' } });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || res.statusText);
      image = data.image; drawImage();
    } catch (e) { toast(e.message, 5000); }
  };
  drawImage();
  const sel = selector(ho.recipients === 'all' ? null : ho.recipients);
  const show = h('input', { type: 'checkbox', checked: ho.shown });
  const ok = await UI.modal(ho.id ? `Edit “${ho.title}”` : 'New handout', h('div',
    h('label.stack', 'Title', title),
    h('div.md-edit', h('label.stack', 'Text (Markdown)', text), h('div', h('span.hint', 'Preview'), preview)),
    h('h3', 'Image'), imgBox,
    h('h3', 'Who gets it'), players().length ? sel : h('p.hint', 'Invite players first; until then it goes to every runner.'),
    h('label.check.mt', show, 'Show it to them now')), { ok: ho.id ? 'Save' : 'Create handout', wide: true });
  if (!ok) return;
  const allPicked = !players().length || sel.value().length === players().length;
  const out = { title: title.value.trim(), body: text.value, image, recipients: allPicked ? 'all' : sel.value(), shown: show.checked };
  try { await api(ho.id ? `/api/handouts/${ho.id}` : `/api/games/${CID}/handouts`, ho.id ? 'PUT' : 'POST', out); toast(show.checked ? 'Handout shown to the runners.' : 'Handout saved (hidden).'); reload(); }
  catch (e) { toast(e.message); }
}

// ================================================================ maps
async function deleteMap(m, here) {
  const who = here.length ? ` ${here.map(p => p.name).join(', ')} will be taken off it.` : '';
  if (!await UI.confirm(`Delete the map "${m.name}"? This can't be undone.${who}`, { danger: true, ok: 'Delete map' })) return;
  try { await api(`/api/maps/${m.id}`, 'DELETE'); toast(`Deleted "${m.name}".`); reload(); } catch (e) { toast(e.message); }
}
function renderMaps() {
  const root = $('maps-root'); root.innerHTML = '';
  root.append(h('div.section-head', h('h2', 'Maps'), h('div.row.tight', h('a.btn.primary', { href: `/?newmap=${CID}` }, 'New map'), h('a.btn', { href: `/?genmap=${CID}` }, 'Generate map'))));
  if (!S.data.maps.length) { root.append(h('div.card.empty', h('h3', 'No maps yet'), h('p', 'Draw a map or generate one, then place your runners’ tokens on it from Play mode.'))); return; }
  const grid = h('div.map-grid');
  for (const m of S.data.maps) {
    const here = players().filter(p => p.currentMapId === m.id);
    grid.append(h('div.map-card', h('a.map-name', { href: '/map/' + m.id }, m.name),
      h('div.meta', `${m.gridType === 'hex' ? 'Hex' : 'Square'} · ${m.width}×${m.height} · edited ${timeAgo(m.updatedAt)}`),
      h('div.row.tight', here.map(p => h('span.chip', h('span.dot', { style: { background: p.color } }), p.name))),
      h('div.row.tight', h('a.btn.small', { href: '/map/' + m.id }, 'Edit'), h('a.btn.small', { href: `/map/${m.id}?play=1` }, 'Play'),
        h('button.small', { type: 'button', onclick: async () => { await api(`/api/maps/${m.id}/duplicate`, 'POST', {}); toast('Map duplicated.'); reload(); } }, 'Duplicate'),
        h('a.btn.small', { href: `/api/maps/${m.id}/export` }, 'Export'),
        h('button.small.danger', { type: 'button', onclick: () => deleteMap(m, here) }, 'Delete'))));
  }
  root.append(grid);
}

// ================================================================ dice & log
function renderLog() {
  const root = $('log-root');
  if (!root._built) {
    root._built = true;
    root.innerHTML = '';
    const form = h('div.card', h('h3', 'GM roller'));
    const body = h('div.roller');
    form.append(body);
    const log = h('div.log#gm-log', { style: { maxHeight: 'none' } });
    root.append(h('div.grid2', form, h('div.card', h('h3', 'Table log', h('span.hint', 'Everyone sees rolls except hidden GM rolls (🔒)')), log)));
    root._roller = body;
    drawRoller();
  }
  SR.renderLog($('gm-log'), S.data.rolls);
}
function drawRoller() {
  const g = S.gm, body = $('log-root')._roller;
  const save = () => { try { localStorage.setItem('sg.gmroller', JSON.stringify(g)); } catch { /* ignore */ } };
  body.innerHTML = '';
  body.append(h('div.tabs-inline',
    h('button.small' + (g.mode === 'pool' ? '.active' : ''), { type: 'button', onclick: () => { g.mode = 'pool'; save(); drawRoller(); } }, 'Dice pool'),
    h('button.small' + (g.mode === 'init' ? '.active' : ''), { type: 'button', onclick: () => { g.mode = 'init'; save(); drawRoller(); } }, 'Initiative')));
  const label = h('input', { value: g.label, placeholder: g.mode === 'pool' ? 'What is it? e.g. Guard: Perception' : 'Who? e.g. Lone Star squad', oninput: e => { g.label = e.target.value; save(); } });
  body.append(h('label.stack', 'Label', label));
  if (g.mode === 'pool') {
    body.append(h('div.opts',
      h('label', 'Dice', h('input', { type: 'number', min: 1, max: 60, value: g.dice, oninput: e => { g.dice = e.target.value; save(); } })),
      h('label', 'Threshold', h('input', { type: 'number', min: 0, max: 30, value: g.threshold, placeholder: '–', oninput: e => { g.threshold = e.target.value; save(); } })),
      h('label.check', h('input', { type: 'checkbox', checked: g.wild, onchange: e => { g.wild = e.target.checked; save(); } }), 'Wild Die')));
  } else {
    body.append(h('div.opts',
      h('label', 'Score', h('input', { type: 'number', min: 0, max: 60, value: g.score, oninput: e => { g.score = e.target.value; save(); } })),
      h('label', '+ d6', h('input', { type: 'number', min: 1, max: 5, value: g.idice, oninput: e => { g.idice = e.target.value; save(); } }))));
  }
  body.append(h('label.check', h('input', { type: 'checkbox', checked: g.hidden, onchange: e => { g.hidden = e.target.checked; save(); } }), 'Hidden roll (only you see it)'));
  body.append(h('div.actions', h('button.primary', { type: 'button', onclick: gmRoll }, g.mode === 'pool' ? 'Roll' : 'Roll initiative')));
  body.append(h('div.row.tight', h('span.hint', 'Quick:'), [4, 6, 8, 10, 12, 14].map(n => h('button.small', { type: 'button', onclick: () => { g.dice = n; g.mode = 'pool'; save(); gmRoll(); } }, n + 'd'))));
}
async function gmRoll() {
  const g = S.gm;
  const b = g.mode === 'pool' ? { dice: +g.dice, label: g.label, wild: g.wild, threshold: +g.threshold || 0, hidden: g.hidden }
    : { kind: 'initiative', score: +g.score, dice: +g.idice, label: g.label, hidden: g.hidden };
  try { const r = await api(`/api/games/${CID}/roll`, 'POST', b); S.data.rolls = r.rolls; SR.renderLog($('gm-log'), r.rolls); }
  catch (e) { toast(e.message); }
}

// ================================================================ history
function renderHistory() {
  const root = $('history-root'); root.innerHTML = '';
  root.append(h('div.section-head', h('h2', 'History'), h('span.hint', 'Every Karma and Nuyen change in this game: purchases, upgrades, run rewards and GM awards.')));
  if (!S.data.ledger.length) { root.append(h('div.card.empty', h('p', 'Nothing yet.'))); return; }
  const t = h('table.list', h('thead', h('tr', h('th', 'When'), h('th', 'Runner'), h('th', 'What'), h('th.right', 'Change'), h('th.right', 'Balance'))));
  const tb = h('tbody');
  for (const r of S.data.ledger) {
    const val = r.kind === 'karma' ? `${r.delta > 0 ? '+' : ''}${r.delta} Karma` : `${r.delta > 0 ? '+' : '−'}${money(Math.abs(r.delta))}`;
    tb.append(h('tr', h('td.hint.nowrap', timeAgo(r.at)), h('td', pname(r.playerId)), h('td', r.reason, r.byGm ? h('span.hint', ' (GM)') : ''),
      h('td.right.nowrap', { class: r.delta > 0 ? 'good' : 'bad' }, val), h('td.right.hint.nowrap', r.kind === 'karma' ? r.balance : money(r.balance))));
  }
  t.append(tb);
  root.append(h('div.card', h('div.table-wrap', t)));
}

// ================================================================ boot
(async () => {
  try {
    await load(true);
    const cat = await SR.catalog();
    Wiki($('wiki'), cat.wiki);
    setView(location.hash.slice(1) || 'players');
    setInterval(poll, 20000);
    Live.on(poll);
  } catch (e) { if (e.message !== 'auth') toast(e.message); }
})();
document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
})();

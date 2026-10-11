/* GM game dashboard: runners (approval, Karma/Nuyen, Edge, accounts), invites, runs, maps, dice log, history. */
(() => {
'use strict';
const CID = document.body.dataset.gameId;
const $ = id => document.getElementById(id);
const S = { data: null, view: 'players', version: null, gm: { dice: 6, label: '', wild: false, threshold: '', hidden: false, mode: 'pool', score: 8, idice: 1 } };
try { Object.assign(S.gm, JSON.parse(localStorage.getItem('sg.gmroller') || '{}')); } catch { /* ignore */ }

// ================================================================ tabs & polling
function setView(v) {
  if (!['players', 'runs', 'maps', 'log', 'history', 'wiki'].includes(v)) v = 'players';
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
  ({ players: renderPlayers, runs: renderRuns, maps: renderMaps, log: renderLog, history: renderHistory, wiki: () => {} })[S.view]();
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
    h('button.primary', { type: 'button', onclick: async () => { await SR.invite(CID, S.data.game.name); reload(); } }, 'Invite player'),
    h('button', { type: 'button', disabled: !ps.length, onclick: () => award(null) }, 'Award Karma / Nuyen…'),
    h('button', { type: 'button', disabled: !ps.length, onclick: () => edge('all', 'refresh') }, 'Refresh everyone’s Edge'),
    h('button', { type: 'button', disabled: !ps.length, onclick: chargeLifestyle, title: 'Start of a new month: every runner pays their lifestyle' }, 'Charge monthly lifestyle'),
    h('button', { type: 'button', onclick: storeSettings, title: 'How much the store pays for gear players sell' }, `Store buys at ${(S.data.game.settings || {}).sellPct ?? 50}%`))));
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
        h('td', h('div.row.tight', miniCM(p.cm), SR.healthTag(p.cm.status))),
        h('td.nowrap', h('div.row.tight', SR.pips(p.edge.cur, p.edge.max),
          h('button.small', { type: 'button', title: 'Take 1 Edge', disabled: !p.edge.cur, onclick: () => edge([p.id], 'lose') }, '−'),
          h('button.small', { type: 'button', title: 'Award 1 Edge (max 7)', disabled: p.edge.cur >= 7, onclick: () => edge([p.id], 'gain') }, '+'),
          h('button.small.ghost', { type: 'button', title: 'Refresh to Edge rating', onclick: () => edge([p.id], 'refresh') }, '↻'))),
        h('td.right.num', p.karma), h('td.right.num.nowrap', { class: p.nuyen < 0 ? 'bad' : '' }, money(p.nuyen)),
        h('td.hint', p.currentMapId ? h('a', { href: `/map/${p.currentMapId}?view=${p.id}` }, mapName(p.currentMapId) || 'map') : 'not placed'),
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

// ================================================================ maps
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
      h('div.row.tight', h('a.btn.small', { href: '/map/' + m.id }, 'Edit'), h('a.btn.small', { href: `/map/${m.id}?play=1` }, 'Play'))));
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
    setInterval(poll, 3000);
  } catch (e) { if (e.message !== 'auth') toast(e.message); }
})();
document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
})();

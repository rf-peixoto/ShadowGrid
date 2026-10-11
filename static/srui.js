/* Shadowrun UI building blocks shared by the player app and the GM pages:
   condition monitors, Edge pips, status tags, the dice roller, the table log and the item editor. */
window.SR = (() => {
'use strict';
let CAT = null;
async function catalog() { if (!CAT) CAT = await api('/api/catalog'); return CAT; }

// ---------------------------------------------------------------- tags & pips
const STATUS_LABEL = { draft: 'Draft', waiting: 'Waiting for approval', approved: 'Approved' };
function statusTag(status) { return h('span.tag.' + status, STATUS_LABEL[status] || status); }
function healthTag(st) { return st && st !== 'OK' ? h('span.tag.status-' + st, st) : null; }
function pips(cur, max, cap = 7) {
  const el = h('span.pips', { title: `Edge ${cur} / ${max}` });
  const n = Math.max(max, cur, 1);
  for (let i = 0; i < Math.min(cap, n); i++) el.append(h('span.pip' + (i < cur ? '.on' : '') + (i >= max ? '.over' : '')));
  return el;
}

// ---------------------------------------------------------------- condition monitor
/* cm = {p, pm, s, sm, ov}; onSet(track, value) makes boxes clickable. */
function monitor(track, cm, { onSet, compact = false, showTools = true } = {}) {
  const isP = track === 'physical';
  const dmg = isP ? cm.p : cm.s, max = isP ? cm.pm : cm.sm, ov = isP ? (cm.ov || 0) : 0;
  const boxes = h('div.boxes' + (onSet ? '' : '.readonly') + (compact ? '.compact' : ''));
  const total = max + ov;
  for (let i = 0; i < total; i++) {
    const over = i >= max;
    const b = h(onSet ? 'button.box' : 'span.box', { type: 'button', title: over ? `Overflow ${i - max + 1} / ${ov}` : `Box ${i + 1}`,
      class: (isP ? 'p' : 's') + (i < dmg ? ' on' : '') + (over ? ' ov' : '') }, compact ? '' : (over ? '+' : (i + 1) % 3 === 0 ? `-${(i + 1) / 3}` : ''));
    if (onSet) b.onclick = () => onSet(track, i < dmg ? i : i + 1);
    boxes.append(b);
  }
  const head = h('div.head', h('span', isP ? 'Physical' : 'Stun'),
    h('b', `${Math.min(dmg, max)} / ${max}`, ov && dmg > max ? h('span.bad', ` +${dmg - max} overflow`) : ''));
  const el = h('div.monitor', head, boxes);
  if (onSet && showTools) {
    el.append(h('div.cm-tools',
      h('button.small', { type: 'button', onclick: () => onSet(track, dmg + 1), title: 'Take 1 box of damage' }, '+1 damage'),
      h('button.small', { type: 'button', onclick: () => onSet(track, Math.max(0, dmg - 1)), title: 'Heal 1 box', disabled: !dmg }, 'Heal 1'),
      h('button.small.ghost', { type: 'button', onclick: () => onSet(track, 0), disabled: !dmg }, 'Clear')));
  }
  return el;
}

// ---------------------------------------------------------------- dice display
function dieEl(d, i, { small = false, selectable = false, selected = false, onClick } = {}) {
  const cls = ['die'];
  if (small) cls.push('sm');
  if (d.h) cls.push('hit'); else if (d.v === 1) cls.push('one');
  if (d.c) cls.push('cancel');
  if (d.w) cls.push('wild');
  if (d.x) cls.push('x');
  if (d.r) cls.push('r');
  if (d.p) cls.push('p');
  if (selected) cls.push('sel');
  const tip = [d.w ? 'Wild Die' + (d.v >= 5 ? ': 3 hits' : d.v === 1 ? ': 5s don’t count' : '') : '', d.c ? 'cancelled by the Wild Die' : '',
    d.x ? 'from an exploding 6' : '', d.r ? 'rerolled with Edge' : '', d.p ? '+1 with Edge' : ''].filter(Boolean).join(', ');
  const el = h(selectable ? 'button' : 'span', { class: cls.join(' '), title: tip || (d.h ? 'Hit' : d.v === 1 ? 'One' : ''), type: 'button' }, d.v);
  if (selectable && onClick) el.onclick = () => onClick(i);
  return el;
}
function verdict(r) {
  if (r.critical) return h('span.verdict.critical', 'CRITICAL GLITCH');
  const base = r.success ? h('span.verdict.success', 'SUCCESS') : h('span.verdict.failure', 'FAILURE');
  if (r.glitch) return h('span', base, ' ', h('span.verdict.glitch', 'GLITCH'));
  return base;
}
function hitsLine(r) {
  const parts = [];
  if (r.threshold) parts.push(`threshold ${r.threshold} · net ${r.net}`);
  if (r.bought) parts.push(`${r.bought} bought`);
  return parts.join(' · ');
}
function breakdown(parts) {
  return (parts || []).map(([k, v], i) => i === 0 ? `${k} ${v}` : `${v >= 0 ? '+' : '−'} ${k} ${Math.abs(v)}`).join('  ');
}

// ---------------------------------------------------------------- table log
function logEntry(r, { mine } = {}) {
  const d = r.data || {};
  const e = h('div.log-entry' + (r.kind === 'note' ? '.note' : '') + (r.hidden ? '.hidden' : ''), { style: { borderLeftColor: r.color } });
  const who = h('span.who', { style: { color: r.color } }, r.who);
  if (r.kind === 'note') { e.append(h('div.line1', who, h('span.what', d.text))); return e; }
  if (r.kind === 'init') {
    e.append(h('div.line1', who, h('span.what', d.label || 'Initiative'), h('span.score', d.total)));
    e.append(h('div.meta', `${d.score} + ${d.dice.join(' + ')}${d.bonus ? ' + ' + d.bonus : ''}`));
    return e;
  }
  e.append(h('div.line1', who, h('span.what', (r.hidden ? '🔒 ' : '') + (d.label || 'Roll')), h('span.score', { title: 'hits' }, d.hits), verdict(d)));
  const dice = h('div.dice-row'); (d.dice || []).forEach((x, i) => dice.append(dieEl(x, i, { small: true })));
  e.append(dice);
  const meta = [`${d.pool} dice`, hitsLine(d), d.boost ? `Edge: ${d.boost.label} (${d.boost.cost})` : ''].filter(Boolean).join(' · ');
  e.append(h('div.meta', { title: breakdown(d.parts) }, meta, ' · ', timeAgo(r.at)));
  return e;
}
function renderLog(el, rolls, opts = {}) {
  const sig = rolls.map(r => r.id + ':' + r.updatedAt).join('|');
  if (el._sig === sig) return;
  el._sig = sig; el.innerHTML = '';
  if (!rolls.length) { el.append(h('p.hint', 'No rolls yet. Every roll shows up here for the whole table.')); return; }
  for (const r of rolls) el.append(logEntry(r, opts));
}

// ---------------------------------------------------------------- dice roller (player)
/* opts: { getSheet: () => sheet, post: (path, body) => Promise, onRolled(res), compact, allies } */
function roller(opts) {
  const S = { key: null, mode: 'pool', wild: false, threshold: '', mod: 0, push: false, wound: true, free: 6, last: null, sel: new Set(), label: '' };
  try { Object.assign(S, JSON.parse(localStorage.getItem('sg.roller') || '{}'), { last: null, sel: new Set() }); } catch { /* ignore */ }
  const root = h('div.roller' + (opts.compact ? '.compact' : ''));
  const save = () => { try { localStorage.setItem('sg.roller', JSON.stringify({ key: S.key, mode: S.mode, wild: S.wild, threshold: S.threshold, wound: S.wound, free: S.free })); } catch { /* ignore */ } };
  function render() {
    const sh = opts.getSheet(); if (!sh) return;
    root.innerHTML = '';
    const pools = sh.pools;
    if (!pools.some(p => p.key === S.key)) S.key = (pools.find(p => p.key === 'skill:Firearms') || pools[0]).key;
    const sel = h('select', { 'aria-label': 'Dice pool', onchange: e => { S.key = e.target.value; save(); render(); } });
    const groups = {};
    for (const p of pools) (groups[p.group] = groups[p.group] || []).push(p);
    for (const [g, list] of Object.entries(groups)) {
      const og = h('optgroup', { label: g });
      list.forEach(p => og.append(option(p.key, `${p.label} (${p.value})`, p.key === S.key)));
      sel.append(og);
    }
    const pool = pools.find(p => p.key === S.key);
    const wound = sh.derived.wound_modifier;
    const totalOf = () => S.mode === 'pool' ? Math.max(0, pool.value + (S.wound ? wound : 0) + (+S.mod || 0)) : Math.max(0, +S.free || 0);
    const total = totalOf();
    const breakdownText = () => breakdown(pool.parts) + (S.wound && wound ? `  Wounds −${-wound}` : '') + (+S.mod ? `  Mod ${S.mod > 0 ? '+' : '−'}${Math.abs(S.mod)}` : '');
    // typing in a number field only refreshes these, so the field keeps focus
    const totalEl = h('span.pool-total', { title: 'Dice you will roll' }, total), breakEl = h('div.breakdown', S.mode === 'pool' ? breakdownText() : '');
    let rollBtn = null;
    const refreshTotals = () => {
      const t = totalOf();
      totalEl.textContent = t;
      if (S.mode === 'pool') breakEl.textContent = breakdownText();
      if (rollBtn) { rollBtn.textContent = `Roll ${t + (S.push ? sh.derived.edge_max : 0)} dice`; rollBtn.disabled = t <= 0 && !S.push; }
    };
    const modeTabs = h('div.tabs-inline',
      h('button.small' + (S.mode === 'pool' ? '.active' : ''), { type: 'button', onclick: () => { S.mode = 'pool'; save(); render(); } }, 'From sheet'),
      h('button.small' + (S.mode === 'free' ? '.active' : ''), { type: 'button', onclick: () => { S.mode = 'free'; save(); render(); } }, 'Free roll'));
    root.append(modeTabs);
    if (S.mode === 'pool') {
      root.append(h('div.pool-line', sel, totalEl));
      root.append(breakEl);
    } else {
      root.append(h('div.free', h('label', 'Dice', h('input', { type: 'number', min: 1, max: 60, value: S.free, oninput: e => { S.free = e.target.value; save(); refreshTotals(); } })),
        h('input.grow', { placeholder: 'What is it for? (optional)', value: S.label, oninput: e => { S.label = e.target.value; } })));
    }
    const edge = sh.char.current_edge, pushCost = CAT.rules.pushCost;
    const optsRow = h('div.opts',
      h('label.check', { title: 'One die is the Wild Die: 5-6 = 3 hits, 1 = your 5s don’t count' }, h('input', { type: 'checkbox', checked: S.wild, onchange: e => { S.wild = e.target.checked; save(); } }), 'Wild Die'),
      h('label', 'Threshold', h('input', { type: 'number', min: 0, max: 30, value: S.threshold, placeholder: '–', oninput: e => { S.threshold = e.target.value; save(); } })));
    if (S.mode === 'pool') {
      optsRow.append(h('label', 'Mod', h('input', { type: 'number', min: -30, max: 30, value: S.mod, oninput: e => { S.mod = e.target.value; refreshTotals(); } })));
      if (wound) optsRow.append(h('label.check', h('input', { type: 'checkbox', checked: S.wound, onchange: e => { S.wound = e.target.checked; save(); render(); } }), `Wounds (${wound})`));
      optsRow.append(h('label.check', { title: `Before rolling: spend ${pushCost} Edge to add your Edge (${sh.derived.edge_max}) to the pool; 6s explode` },
        h('input', { type: 'checkbox', checked: S.push, disabled: edge < pushCost, onchange: e => { S.push = e.target.checked; refreshTotals(); } }), `Push (+${sh.derived.edge_max}, ${pushCost} Edge)`));
    }
    root.append(optsRow);
    rollBtn = h('button.primary', { type: 'button', onclick: roll, disabled: total <= 0 && !S.push }, `Roll ${total + (S.push ? sh.derived.edge_max : 0)} dice`);
    root.append(h('div.actions', rollBtn,
      h('button', { type: 'button', onclick: initiative, title: `Initiative ${sh.derived.initiative_score} + ${sh.derived.initiative_dice}d6` }, 'Initiative')));
    if (S.last) root.append(resultCard(S.last, sh));
  }
  function resultCard(r, sh) {
    const d = r.data;
    const card = h('div.result');
    card.append(h('div.top', h('div.hits', d.hits, h('small', d.hits === 1 ? 'hit' : 'hits')), verdict(d)));
    const canBoost = !d.boost && r.playerId && (Date.now() / 1000 - r.at < 14 * 60);
    const dice = h('div.dice-row');
    d.dice.forEach((x, i) => dice.append(dieEl(x, i, { selectable: canBoost, selected: S.sel.has(i), onClick: idx => { S.sel.has(idx) ? S.sel.delete(idx) : S.sel.add(idx); render(); } })));
    card.append(dice);
    const info = [hitsLine(d), d.wildOne ? 'Wild Die rolled a 1: your 5s don’t count' : '', d.boost ? `Edge: ${d.boost.label}` : ''].filter(Boolean).join(' · ');
    if (info) card.append(h('p.hint.mb0', info));
    if (canBoost) {
      const edge = sh.char.current_edge, n = S.sel.size;
      const b = h('div.boosts');
      b.append(h('p.hint', `Edge Boost (one per roll). You have ${edge} Edge. Click dice to select them.`));
      b.append(h('button', { type: 'button', disabled: !n || edge < n, onclick: () => boost('reroll') }, `Reroll ${n || ''} selected (${n || 1} Edge)`));
      b.append(h('button', { type: 'button', disabled: n !== 1 || edge < 2, onclick: () => boost('plus_one') }, '+1 to selected (2)'));
      b.append(h('button', { type: 'button', disabled: edge < 3, onclick: () => boost('buy_hit') }, 'Buy a hit (3)'));
      b.append(h('button', { type: 'button', disabled: edge < 4, onclick: () => boost('reroll_failed') }, 'Reroll failures (4)'));
      card.append(b);
    }
    return card;
  }
  async function roll() {
    const body = { wild: S.wild, threshold: +S.threshold || 0 };
    if (S.mode === 'pool') Object.assign(body, { key: S.key, mod: +S.mod || 0, wound: S.wound, push: S.push });
    else Object.assign(body, { dice: +S.free || 0, label: S.label.trim() });
    try {
      const res = await opts.post('roll', body);
      S.push = false; S.sel = new Set();
      S.last = res.rolls.find(r => r.id === res.rollId) || null;
      opts.onRolled && opts.onRolled(res);
      render();
    } catch (e) { toast(e.message); }
  }
  async function boost(key) {
    if (!S.last) return;
    try {
      const res = await opts.post(`rolls/${S.last.id}/boost`, { boost: key, dice: [...S.sel] });
      S.sel = new Set(); S.last = res.rolls.find(r => r.id === S.last.id) || S.last;
      opts.onRolled && opts.onRolled(res); render();
    } catch (e) { toast(e.message); }
  }
  async function initiative() {
    const sh = opts.getSheet();
    let plus3 = false;
    if (sh.char.current_edge >= 1) {
      const cb = h('input', { type: 'checkbox' });
      const ok = await UI.modal('Roll initiative', h('div', h('p', `${sh.derived.initiative_score} + ${sh.derived.initiative_dice}d6`),
        h('label.check', cb, 'Spend 1 Edge for +3 Initiative')), { ok: 'Roll', narrow: true });
      if (!ok) return; plus3 = cb.checked;
    }
    try { const res = await opts.post('initiative', { boost: plus3 }); opts.onRolled && opts.onRolled(res); toast(`Initiative ${res.rolls[0].data.total}`); }
    catch (e) { toast(e.message); }
  }
  root.render = render;
  root.setLast = r => { S.last = r; render(); };
  return root;
}

// ---------------------------------------------------------------- Edge spending outside rolls
async function edgeMenu(sh, post, onDone) {
  const list = h('div.col');
  const cur = sh.char.current_edge;
  let picked = null;
  const allySel = h('select', h('option', { value: '' }, 'Pick an ally…'), sh.allies.map(a => option(a.id, a.name)));
  for (const b of CAT.edgeSpend) {
    const id = 'eb-' + b.key;
    list.append(h('label.check.big', h('input', { type: 'radio', name: 'eb', id, disabled: cur < b.cost, onchange: () => { picked = b.key; allySel.hidden = b.key !== 'give'; } }),
      `${b.label}`, h('small', `${b.cost} Edge`)));
  }
  allySel.hidden = true;
  const ok = await UI.modal('Spend Edge', h('div', h('p.hint', `You have ${cur} Edge. Boosts that change a roll are on the roll itself.`), list, allySel), { ok: 'Spend' });
  if (!ok || !picked) return;
  try { const res = await post('edge', { key: picked, to: allySel.value }); toast(res.message); onDone && onDone(res); }
  catch (e) { toast(e.message); }
}

// ---------------------------------------------------------------- item editor (gear / spell / power / focus)
/* kind: gear category or 'Spell' | 'Power' | 'Focus'. Returns the item dict or null. */
async function editItem(kind, item, { title, ok = 'Save', allowPrice = true, lockedFields = false } = {}) {
  item = Object.assign({}, item || {});
  const fields = (CAT.fields[kind] || []).filter(f => allowPrice || f !== 'Price');
  const inputs = {};
  const grid = h('div.form-grid');
  const name = h('input', { value: item.name || '', required: true, maxlength: 80 });
  grid.append(h('label', 'Name', name));
  for (const f of fields) {
    const opts = CAT.options[`${kind}.${f}`];
    let inp;
    if (opts) { inp = h('select', opts.map(o => option(o, o, String(item[f] ?? '') === o))); if (item[f] && !opts.includes(item[f])) inp.prepend(option(item[f], item[f], true)); }
    else inp = h('input', { value: item[f] ?? '', type: f === 'Price' ? 'number' : 'text', min: f === 'Price' ? 0 : undefined });
    inp.disabled = lockedFields;
    inputs[f] = inp; grid.append(h('label', f === 'Price' ? 'Price (¥)' : f, inp));
  }
  const desc = h('textarea', { rows: 3, maxlength: 1000 }, item.description || '');
  const known = new Set(['name', 'description', 'Equipped', 'Bonded', '_custom', ...fields]);
  const extra = Object.entries(item).filter(([k]) => !known.has(k)).map(([k, v]) => `${k}: ${v}`).join('\n');
  const custom = h('textarea', { rows: 3, placeholder: 'One per line, e.g.\nReaction: 1\nInitiative Dice: 1', disabled: lockedFields }, extra);
  let equipped = null;
  if (CAT.equippable.includes(kind)) equipped = h('input', { type: 'checkbox', checked: String(item.Equipped ?? 'Yes').toLowerCase() !== 'no' });
  const body = h('div', grid, h('label.stack', 'Description', desc),
    h('label.stack', 'Custom attributes', custom,
      h('small.hint', 'An attribute name with a number (e.g. “Agility: 1”) is applied to your character for cyberware, bioware and adept powers. “Armor: 3” on a power adds to Armor.')),
    equipped ? h('label.check', equipped, 'Equipped (counts toward Armor / Accuracy and the dice roller)') : null,
    lockedFields ? h('p.hint', 'Your sheet is approved: only the name, description and equipped state can change.') : null);
  const okd = await UI.modal(title || (item.name ? `Edit ${item.name}` : `New ${kind}`), body, { ok });
  if (!okd) return null;
  const out = { name: name.value.trim(), description: desc.value.trim() };
  for (const [f, inp] of Object.entries(inputs)) if (String(inp.value).trim() !== '') out[f] = inp.value.trim();
  for (const line of custom.value.split('\n')) { const i = line.indexOf(':'); if (i > 0) { const k = line.slice(0, i).trim(), v = line.slice(i + 1).trim(); if (k) out[k] = v; } }
  if (equipped) out.Equipped = equipped.checked ? 'Yes' : 'No';
  return out;
}

function itemDetails(item, skip = []) {
  const dl = h('dl.kv');
  for (const [k, v] of Object.entries(item)) {
    if (['name', 'description', 'Price', '_custom', ...skip].includes(k) || v === '' || v === '-') continue;
    dl.append(h('dt', k), h('dd', String(v)));
  }
  return dl;
}

// ---------------------------------------------------------------- GM: invite a player
async function invite(cid, gameName) {
  let res;
  try { res = await api(`/api/games/${cid}/invites`, 'POST', {}); } catch (e) { toast(e.message); return null; }
  const inp = h('input', { value: res.url, readonly: true, style: { width: '100%' }, onfocus: e => e.target.select() });
  const copy = h('button.primary', { type: 'button', onclick: async () => { try { await navigator.clipboard.writeText(res.url); toast('Invite link copied.'); } catch { inp.select(); document.execCommand('copy'); toast('Invite link copied.'); } } }, 'Copy link');
  await UI.modal(`Invite a player${gameName ? ' to ' + gameName : ''}`, h('div',
    h('p', 'Send this link to one player. They choose a username and password, and their account only opens this game.'),
    h('div.row.tight', inp, copy),
    h('p.hint', `Single use · expires ${new Date(res.expiresAt * 1000).toLocaleDateString()} · you can revoke it on the game page.`)), { ok: 'Done', cancel: null });
  return res;
}

return { invite, catalog, get CAT() { return CAT; }, statusTag, healthTag, pips, monitor, dieEl, verdict, logEntry, renderLog, roller, edgeMenu, editItem, itemDetails, breakdown };
})();

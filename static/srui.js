/* Shadowrun UI building blocks shared by the player app and the GM pages:
   condition monitors, Edge pips, status tags, the dice roller, the table log, store helpers and the item editor. */
window.SR = (() => {
'use strict';
let CAT = null;
/* the catalog never changes while the server runs: the page names its version so the browser can keep it */
let catLoad = null;
async function catalog() {
  if (CAT) return CAT;
  if (!catLoad) {
    const m = document.querySelector('meta[name="sg-catalog"]');
    catLoad = api('/api/catalog' + (m && m.content ? '?v=' + encodeURIComponent(m.content) : '')).then(c => { CAT = c; return c; }, e => { catLoad = null; throw e; });
  }
  return catLoad;
}

// ---------------------------------------------------------------- tags & pips
const STATUS_LABEL = { draft: 'Draft', waiting: 'Waiting for approval', approved: 'Approved' };
function statusTag(status) { return h('span.tag.' + status, STATUS_LABEL[status] || status); }
/* What a contact can source: their type's defaults plus the ticked boxes (same rule as the server). */
function contactSupply(ct) { return [...new Set([...((CAT.contactTypeSupply || {})[ct.type] || []), ...(ct.supply || [])])]; }
function healthTag(st) { return st && st !== 'OK' ? h('span.tag.status-' + st, st) : null; }
function pips(cur, max, cap = 7) {
  const el = h('span.pips', { title: `Edge ${cur} / ${max}` });
  const n = Math.max(max, cur, 1);
  for (let i = 0; i < Math.min(cap, n); i++) el.append(h('span.pip' + (i < cur ? '.on' : '') + (i >= max ? '.over' : '')));
  return el;
}
/* status effects as small chips: {Prone: true, Burning: 3} */
function statusChips(statuses, { onRemove } = {}) {
  const names = Object.keys(statuses || {});
  if (!names.length) return null;
  return h('span.status-chips', names.map(n => {
    const v = statuses[n], meta = (CAT && CAT.statuses[n]) || {};
    return h('span.status-chip', { title: `${n}${v !== true ? ' ' + v : ''}: ${meta.desc || ''}` }, `${meta.icon || ''} ${n}${v !== true && v > 0 ? ' ' + v : ''}`,
      onRemove ? h('button.x', { type: 'button', title: 'Remove', onclick: () => onRemove(n) }, '×') : null);
  }));
}

// ---------------------------------------------------------------- condition monitor
/* cm = {p, pm, s, sm, ov, grunt?}; onSet(track, value) makes boxes clickable.
   Physical shows its overflow boxes after the track; filling them all means death. */
function monitor(track, cm, { onSet, compact = false, showTools = true, label } = {}) {
  const isP = track === 'physical';
  const dmg = isP ? cm.p : cm.s, max = isP ? cm.pm : cm.sm, ov = isP ? (cm.ov || 0) : 0;
  const step = cm.grunt ? 2 : 3;
  const boxes = h('div.boxes' + (onSet ? '' : '.readonly') + (compact ? '.compact' : ''));
  const total = max + ov;
  for (let i = 0; i < total; i++) {
    const over = i >= max;
    const b = h(onSet ? 'button.box' : 'span.box', { type: 'button', title: over ? `Overflow ${i - max + 1} / ${ov}${i === total - 1 ? ' (death)' : ''}` : `Box ${i + 1}`,
      class: (isP ? 'p' : 's') + (i < dmg ? ' on' : '') + (over ? ' ov' : '') }, compact ? '' : (over ? '+' : (i + 1) % step === 0 ? `-${(i + 1) / step}` : ''));
    if (onSet) b.onclick = () => onSet(track, i < dmg ? i : i + 1);
    boxes.append(b);
  }
  const head = h('div.head', h('span', label || (cm.grunt ? 'Condition' : isP ? 'Physical' : 'Stun')),
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
const sum = parts => Math.max(0, (parts || []).reduce((a, p) => a + p[1], 0));

// ---------------------------------------------------------------- table log
function attackEntry(r, e, who) {
  const d = r.data;
  e.classList.add('attack');
  e.append(h('div.line1', who, h('span.what', (r.hidden ? '🔒 ' : '') + `${d.attacker} → ${d.target}`),
    h('span.verdict.' + (d.hit ? 'success' : 'failure'), d.hit ? (d.damage ? `${d.damage}${d.type === 'S' ? 'S' : 'P'}` : 'SOAKED') : 'MISS')));
  const row = (label, part) => part ? h('div.atk-row', h('span.k', label), h('span.dice-row', (part.dice || []).map((x, i) => dieEl(x, i, { small: true }))),
    h('b', { title: breakdown(part.parts) }, part.unopposed ? 'unopposed' : `${part.hits} hits`)) : null;
  e.append(...[row(d.weapon + (d.mode ? ` (${d.mode})` : ''), d.attack), row('Defense', d.defense), d.soak ? row('Soak', d.soak) : null].filter(Boolean));
  const meta = [d.range, d.ar != null ? `AR ${d.ar} vs DR ${d.dr}` : null, d.edge_hint ? `${d.edge_hint === 'attacker' ? 'attacker' : 'defender'} may gain 1 Edge` : null,
    d.hit ? `DV ${d.dv}${d.type}` : null, ...(d.notes || []), (d.effects || []).length ? 'statuses: ' + d.effects.map(x => x[0]).join(', ') : null,
    d.targetStatus && d.targetStatus !== 'OK' ? d.target + ': ' + d.targetStatus : null].filter(Boolean).join(' · ');
  e.append(h('div.meta', meta, ' · ', timeAgo(r.at)));
  return e;
}
/* one line for the dice dock header: who rolled what, and the outcome */
/* actions left this round on a tracker entry: ◆ = Major, ● = Minor (dim when used) */
function actionPips(e) {
  if (!e || e.majorLeft == null) return null;
  const minor = Math.max(1, Math.min(5, e.minor || 1));
  const usedMinor = minor - Math.max(0, e.minorLeft);
  const el = h('span.act-pips', { title: `${e.majorLeft > 0 ? '1 Major' : 'no Major'} and ${Math.max(0, e.minorLeft)} of ${minor} Minor actions left${e.fd ? ' · Full Defense' : ''}${e.dirt ? ' · Hit the Dirt (−2)' : ''}` },
    h('i.maj' + (e.majorLeft > 0 ? '' : '.used')));
  for (let k = 0; k < minor; k++) el.append(h('i.min' + (k < usedMinor ? '.used' : '')));
  if (e.fd) el.append(h('b.fd', { title: 'Full Defense: +Willpower on every Defense test this round' }, 'FD'));
  return el;
}
function rollSummary(r) {
  if (!r) return '';
  const d = r.data || {};
  if (r.kind === 'attack') return `${d.attacker} → ${d.target}: ${d.hit ? (d.damage ? `${d.damage}${d.type === 'S' ? 'S' : 'P'} damage` : 'soaked') : 'miss'}`;
  if (r.kind === 'init') return `${r.who}: initiative ${d.total}`;
  if (r.kind === 'note') return `${r.who}: ${d.text}`;
  return `${r.who}: ${d.label || 'Roll'}, ${d.hits} hit${d.hits === 1 ? '' : 's'}${d.threshold ? (d.success ? ' (success)' : ' (failure)') : ''}`;
}
function logEntry(r) {
  const d = r.data || {};
  const e = h('div.log-entry' + (r.kind === 'note' ? '.note' : '') + (r.hidden ? '.hidden' : ''), { style: { borderLeftColor: r.color } });
  const who = h('span.who', { style: { color: r.color } }, r.who);
  if (r.kind === 'note') { e.append(h('div.line1', who, h('span.what', (r.hidden ? '🔒 ' : '') + d.text))); return e; }
  if (r.kind === 'attack') return attackEntry(r, e, who);
  if (r.kind === 'init') {
    e.append(h('div.line1', who, h('span.what', d.label || 'Initiative'), h('span.score', d.total)));
    e.append(h('div.meta', `${d.score} + ${d.dice.join(' + ')}${d.bonus ? ' + ' + d.bonus : ''}` + (d.actions ? ` · 1 Major, ${d.actions.minor} Minor` : '')));
    return e;
  }
  e.append(h('div.line1', who, h('span.what', (r.hidden ? '🔒 ' : '') + (d.label || 'Roll')), h('span.score', { title: 'hits' }, d.hits), verdict(d)));
  const dice = h('div.dice-row'); (d.dice || []).forEach((x, i) => dice.append(dieEl(x, i, { small: true })));
  e.append(dice);
  const meta = [`${d.pool} dice`, hitsLine(d), d.note || '', d.boost ? `Edge: ${d.boost.label} (${d.boost.cost})` : ''].filter(Boolean).join(' · ');
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

// ---------------------------------------------------------------- store helpers
function availText(n, legal) { return n == null ? '—' : `${n}${legal ? `(${legal})` : ''}`; }
const RANGES = ['Close', 'Near', 'Medium', 'Far', 'Extreme'];
function arText(ar) { return (ar || []).map(a => a == null ? '—' : a).join('/'); }
/* one-line summary of an item's game stats (catalog entry or inventory item) */
function itemStats(it) {
  const p = [];
  if (it.dv) p.push(`DV ${it.dv}`);
  if (it.ar) p.push(`AR ${Array.isArray(it.ar) ? arText(it.ar) : it.ar}`);
  if (it.modes) p.push(it.modes);
  if (it.ammo) p.push(`Ammo ${it.ammo}`);
  if (it.dv_gz) p.push(`DV ${it.dv_gz}/${it.dv_close}/${it.dv_near}`, `Blast ${it.blast}`);
  if (it.dr) p.push(`Defense +${it.dr}`);
  if (it.essence != null && it.essence !== '' && (it.implant || it.essenceN != null)) p.push(`Essence ${it.essence}`);
  if (it.device_rating) p.push(`DR ${it.device_rating}`);
  if (it.attack != null && it.sleaze != null) p.push(`A/S ${it.attack}/${it.sleaze}`);
  if (it.data_processing != null && it.firewall != null) p.push(`DP/FW ${it.data_processing}/${it.firewall}`);
  if (it.program_slots) p.push(`${it.program_slots} slots`);
  if (it.handling) p.push(`Hand ${it.handling}`, `Acc ${it.accel}`, `Spd ${it.speed_interval}/${it.top_speed}`, `Bod ${it.body}`, `Arm ${it.armor}`, `Pil ${it.pilot}`, `Sen ${it.sensor}`);
  for (const a of ['Body', 'Agility', 'Reaction', 'Strength', 'Willpower', 'Logic', 'Intuition', 'Charisma']) if (it[a]) p.push(`+${it[a]} ${a.slice(0, 3).toUpperCase()}`);
  if (it.init_dice) p.push(`+${it.init_dice}D6 Init`);
  if (it.capacity) p.push(`Cap ${it.capacity}`);
  if (it.capacity_cost) p.push(`[${it.capacity_cost}]`);
  return p.join(' · ');
}

// ---------------------------------------------------------------- dice roller (player)
/* opts: { getSheet: () => sheet, post: (path, body) => Promise, onRolled(res), compact } */
function roller(opts) {
  const S = { key: null, mode: 'pool', wild: false, threshold: '', mod: 0, push: false, wound: true, free: 6, last: null, sel: new Set(), label: '',
    fire: {}, range: 'Near', drain: 0, patient: '', assisted: false, targetRating: 3 };
  try { Object.assign(S, JSON.parse(localStorage.getItem('sg.roller') || '{}'), { last: null, sel: new Set() }); } catch { /* ignore */ }
  const root = h('div.roller' + (opts.compact ? '.compact' : ''));
  const save = () => { try { localStorage.setItem('sg.roller', JSON.stringify({ key: S.key, mode: S.mode, wild: S.wild, threshold: S.threshold, wound: S.wound, free: S.free, fire: S.fire, range: S.range, targetRating: S.targetRating })); } catch { /* ignore */ } };
  function render() {
    const sh = opts.getSheet(); if (!sh) return;
    root.innerHTML = '';
    const pools = sh.pools;
    if (!pools.some(p => p.key === S.key)) S.key = (pools.find(p => p.key.startsWith('weapon:') && p.key !== 'weapon:unarmed') || pools.find(p => p.key === 'skill:Firearms') || pools[0]).key;
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
      if (rollBtn) { rollBtn.textContent = rollLabel(t); rollBtn.disabled = t <= 0 && !S.push; }
    };
    const modeTabs = h('div.tabs-inline',
      h('button.small' + (S.mode === 'pool' ? '.active' : ''), { type: 'button', onclick: () => { S.mode = 'pool'; save(); render(); } }, 'From sheet'),
      h('button.small' + (S.mode === 'free' ? '.active' : ''), { type: 'button', onclick: () => { S.mode = 'free'; save(); render(); } }, 'Free roll'));
    root.append(modeTabs);
    let weaponInfo = null;
    if (S.mode === 'pool') {
      root.append(h('div.pool-line', sel, totalEl));
      root.append(breakEl);
      if (pool.weapon) {
        const fm = (pool.modes || []);
        let fmode = S.fire[S.key];
        if (!fm.includes(fmode)) fmode = fm[0] || null;
        const fmCat = CAT.store.firingModes;
        const modeSel = fm.length ? h('select', { 'aria-label': 'Firing mode', onchange: e => { S.fire[S.key] = e.target.value; save(); render(); } },
          fm.map(m => option(m, `${m} · ${fmCat[m].name} (${fmCat[m].rounds} rd)`, m === fmode))) : null;
        const rangeSel = h('select', { 'aria-label': 'Range', onchange: e => { S.range = e.target.value; save(); render(); } },
          RANGES.map((r, i) => option(r, `${r} (${CAT.store.rangeMeters[r]})${pool.ar && pool.ar[i] == null ? ' – out of range' : ''}`, r === S.range)));
        const i = RANGES.indexOf(S.range), m = fmode ? fmCat[fmode] : null;
        const arNow = pool.ar && pool.ar[i] != null ? Math.max(0, pool.ar[i] + (m ? m.ar : 0)) : null;
        const dvm = /^(\d+)(.*)$/.exec(pool.dv || ''), dvNow = dvm ? `${+dvm[1] + (m ? m.dv : 0)}${dvm[2]}` : pool.dv;
        const ammo = pool.clip ? `${pool.loaded}/${pool.clip} loaded` : pool.consumable ? `${pool.qty} left` : '';
        const need = m && pool.clip ? m.rounds : 0;
        weaponInfo = h('div.weapon-line', modeSel, rangeSel,
          h('span.chip', h('span.k', 'AR'), h('b', arNow == null ? '—' : arNow)), h('span.chip', h('span.k', 'DV'), h('b', dvNow)),
          ammo ? h('span.chip' + (pool.clip && pool.loaded < (need || 1) ? '.bad' : ''), ammo) : null,
          pool.clip && pool.loaded < pool.clip ? h('button.small', { type: 'button', onclick: () => reloadWeapon(S.key.slice(7)), title: 'Fill the magazine from your ammo' }, 'Reload') : null);
        root.append(weaponInfo);
        S._fmode = fmode;
      } else S._fmode = null;
      if (pool.spell) root.append(h('div.weapon-line', h('span.hint', `Drain ${pool.drain}${+S.drain ? ' + ' + S.drain : ''} is rolled after casting.`),
        h('label', 'Extra drain', h('input', { type: 'number', min: 0, max: 20, value: S.drain, title: 'Amp Up (+2 per extra DV) or Increase Area (+1 per +2 m)', oninput: e => { S.drain = e.target.value; } }))));
      if (pool.form) root.append(h('p.hint', `Fading ${pool.fade} is rolled after threading.`));
      if (pool.matrix) {
        const opposed = pool.defense && pool.defense !== 4;
        root.append(h('div.weapon-line',
          h('span.tag' + (pool.legal ? '' : '.illegal'), pool.legal ? 'Legal' : 'Illegal'),
          opposed ? h('label', { title: 'Device or host rating: it defends with rating × 2 dice. 0 = the GM rolls the defense.' }, 'Target rating',
            h('input', { type: 'number', min: 0, max: 12, value: S.targetRating, style: { width: '4rem' }, oninput: e => { S.targetRating = e.target.value; save(); } })) : null,
          h('span.hint', pool.legal ? (Array.isArray(pool.defense) ? `vs ${pool.defense.join(' + ')}` : '') :
            `vs ${Array.isArray(pool.defense) ? pool.defense.join(' + ') : pool.defense === 'rating' ? 'rating × 2' : pool.defense || '—'} · the defender’s hits raise your Overwatch Score`)));
      }
      if (pool.heal) {
        const natural = pool.heal.startsWith('natural');
        const line = h('div.weapon-line');
        if (!natural) {
          const allies = sh.allies || [];
          if (!allies.some(a => a.id === S.patient)) S.patient = '';
          line.append(h('label', 'Patient', h('select', { onchange: e => { S.patient = e.target.value; } }, option('', 'Myself', !S.patient), allies.map(a => option(a.id, a.name, a.id === S.patient)))));
          if (pool.heal === 'medkit') line.append(h('span.chip' + (pool.supplies ? '' : '.bad'), `${pool.supplies} supplies`));
          if (pool.heal === 'magic') line.append(h('span.hint', `Drain ${pool.drain} after casting.`));
          line.append(h('span.hint', 'Threshold 5 − the patient’s Essence. Works once per set of injuries.'));
        } else line.append(h('label.check', h('input', { type: 'checkbox', checked: S.assisted, onchange: e => { S.assisted = e.target.checked; } }), 'A Biotech-trained helper watches (+2)'));
        root.append(line);
      }
    } else {
      root.append(h('div.free', h('label', 'Dice', h('input', { type: 'number', min: 1, max: 60, value: S.free, oninput: e => { S.free = e.target.value; save(); refreshTotals(); } })),
        h('input.grow', { placeholder: 'What is it for? (optional)', value: S.label, oninput: e => { S.label = e.target.value; } })));
    }
    const edge = sh.char.current_edge, pushCost = CAT.rules.pushCost;
    const healing = S.mode === 'pool' && pool && pool.heal;
    const optsRow = h('div.opts', healing ? null : [
      pool && pool.wild ? h('span.tag', { title: 'Overclock: one of its dice is the Wild Die' }, 'Wild Die (Overclock)')
        : h('label.check', { title: 'One die is the Wild Die: 5-6 = 3 hits, 1 = your 5s don’t count' }, h('input', { type: 'checkbox', checked: S.wild, onchange: e => { S.wild = e.target.checked; save(); } }), 'Wild Die'),
      h('label', 'Threshold', h('input', { type: 'number', min: 0, max: 30, value: S.threshold, placeholder: '–', oninput: e => { S.threshold = e.target.value; save(); } }))]);
    if (S.mode === 'pool') {
      optsRow.append(h('label', 'Mod', h('input', { type: 'number', min: -30, max: 30, value: S.mod, oninput: e => { S.mod = e.target.value; refreshTotals(); } })));
      if (wound) optsRow.append(h('label.check', h('input', { type: 'checkbox', checked: S.wound, onchange: e => { S.wound = e.target.checked; save(); render(); } }), `Wounds (${wound})`));
      optsRow.append(h('label.check', { title: `Before rolling: spend ${pushCost} Edge to add your Edge (${sh.derived.edge_max}) to the pool; 6s explode` },
        h('input', { type: 'checkbox', checked: S.push && !(pool && pool.noEdge), disabled: edge < pushCost || !!(pool && (pool.noEdge || (pool.heal || '').startsWith('natural'))), onchange: e => { S.push = e.target.checked; refreshTotals(); } }), `Push (+${sh.derived.edge_max}, ${pushCost} Edge)`));
      if (pool && pool.noEdge) optsRow.append(h('span.hint', 'No Edge without a medkit.'));
    }
    root.append(optsRow);
    function rollLabel(t) {
      const verb = pool && S.mode === 'pool' ? (pool.weapon ? 'Attack' : pool.spell ? 'Cast' : pool.form ? 'Thread' : pool.heal ? (pool.heal.startsWith('natural') ? 'Rest' : 'Heal') : 'Roll') : 'Roll';
      return `${verb}: ${t + (S.push ? sh.derived.edge_max : 0)} dice`;
    }
    rollBtn = h('button.primary', { type: 'button', onclick: roll, disabled: total <= 0 && !S.push }, rollLabel(total));
    const dv = sh.derived;
    root.append(h('div.actions', rollBtn,
      h('button', { type: 'button', onclick: initiative, title: `Initiative ${dv.initiative_score} + ${dv.initiative_dice}d6 · 1 Major, ${dv.minor_actions} Minor` }, 'Initiative')));
    if (S.last) root.append(resultCard(S.last, sh));
  }
  function resultCard(r, sh) {
    const d = r.data;
    const card = h('div.result');
    card.append(h('div.top', h('div.hits', d.hits, h('small', d.hits === 1 ? 'hit' : 'hits')), verdict(d)));
    const canBoost = !d.boost && !d.heal && r.playerId && (Date.now() / 1000 - r.at < 14 * 60);
    const dice = h('div.dice-row');
    d.dice.forEach((x, i) => dice.append(dieEl(x, i, { selectable: canBoost, selected: S.sel.has(i), onClick: idx => { S.sel.has(idx) ? S.sel.delete(idx) : S.sel.add(idx); render(); } })));
    card.append(dice);
    const info = [hitsLine(d), d.note || '', d.wildOne ? 'Wild Die rolled a 1: your 5s don’t count' : '', d.boost ? `Edge: ${d.boost.label}` : ''].filter(Boolean).join(' · ');
    if (info) card.append(h('p.hint.mb0', info));
    if (canBoost) {
      const free = d.free_edge || 0, edge = sh.char.current_edge + free, n = S.sel.size;
      const b = h('div.boosts');
      b.append(h('p.hint', `Edge Boost (one per roll). You have ${sh.char.current_edge} Edge${free ? ` + ${free} for this roll only (program)` : ''}. Click dice to select them.`));
      b.append(h('button', { type: 'button', disabled: !n || edge < n, onclick: () => boost('reroll') }, `Reroll ${n || ''} selected (${n || 1} Edge)`));
      b.append(h('button', { type: 'button', disabled: n !== 1 || edge < 2, onclick: () => boost('plus_one') }, '+1 to selected (2)'));
      b.append(h('button', { type: 'button', disabled: edge < 3, onclick: () => boost('buy_hit') }, 'Buy a hit (3)'));
      b.append(h('button', { type: 'button', disabled: edge < 4, onclick: () => boost('reroll_failed') }, 'Reroll failures (4)'));
      card.append(b);
    }
    return card;
  }
  async function roll() {
    const sh = opts.getSheet(), pool = S.mode === 'pool' ? sh.pools.find(p => p.key === S.key) : null;
    if (pool && pool.heal) {
      try {
        const res = await opts.post('heal', { method: pool.heal, target: S.patient || undefined, push: S.push && !pool.noEdge, mod: +S.mod || 0, wound: S.wound, assisted: S.assisted });
        S.push = false; S.sel = new Set();
        S.last = res.rolls.find(r => r.id === res.rollId) || null;
        toast(res.message, 4500);
        opts.onRolled && opts.onRolled(res);
        render();
      } catch (e) { toast(e.message, 4500); }
      return;
    }
    const body = { wild: S.wild, threshold: +S.threshold || 0 };
    if (S.mode === 'pool') Object.assign(body, { key: S.key, mod: +S.mod || 0, wound: S.wound, push: S.push, mode: S._fmode, range: S.range, drain: +S.drain || 0, targetRating: +S.targetRating || 0 });
    else Object.assign(body, { dice: +S.free || 0, label: S.label.trim() });
    try {
      const res = await opts.post('roll', body);
      S.push = false; S.sel = new Set();
      S.last = res.rolls.find(r => r.id === res.rollId) || null;
      opts.onRolled && opts.onRolled(res);
      render();
    } catch (e) { toast(e.message, 4000); }
  }
  async function reloadWeapon(uid) {
    try {
      const sh = await opts.post('sheet/action', { action: 'reload', uid });
      toast(sh.message, 3000);
      opts.onRolled && opts.onRolled({ sheet: sh });
      render();
    } catch (e) { toast(e.message, 4500); }
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
    const sh = opts.getSheet(), dv = sh.derived;
    const kinds = [['physical', `Physical: ${dv.initiative_score} + ${dv.initiative_dice}d6`]];
    if (dv.matrix && dv.matrix.device) kinds.push(['matrix', `Matrix (${dv.matrix.mode}): ${dv.matrix.init_score} + ${dv.matrix.init_dice}d6`]);
    if (dv.astral_initiative) kinds.push(['astral', `Astral: ${dv.astral_initiative.score} + ${dv.astral_initiative.dice}d6`]);
    const kindSel = h('select', kinds.map(([k, l]) => option(k, l)));
    const cb = h('input', { type: 'checkbox', disabled: sh.char.current_edge < 1 });
    const ok = await UI.modal('Roll initiative', h('div', kinds.length > 1 ? h('label.stack', 'Initiative', kindSel) : h('p', kinds[0][1]),
      h('p.hint', `Each round: 1 Major and ${dv.minor_actions} Minor actions (1 + 1 per Initiative Die, max 5).`),
      h('label.check', cb, 'Spend 1 Edge for +3 Initiative')), { ok: 'Roll', narrow: true });
    if (!ok) return;
    try { const res = await opts.post('initiative', { boost: cb.checked, kind: kindSel.value }); opts.onRolled && opts.onRolled(res); toast(`Initiative ${res.rolls[0].data.total}`); }
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

// ---------------------------------------------------------------- custom item editor
const CUSTOM_FIELDS = {
  Melee: ['dv', 'ar', 'skill', 'spec'], Ranged: ['dv', 'ar', 'modes', 'ammo', 'ammo_class', 'skill', 'spec'],
  'Ammo & Explosives': ['dv_gz', 'dv_close', 'dv_near', 'blast'], Armor: ['dr'],
  Electronics: ['device_rating', 'data_processing', 'firewall', 'program_slots'],
  'Cyberdecks & Software': ['device_rating', 'attack', 'sleaze', 'program_slots'],
  Cyberware: ['essence', 'dr', 'Body', 'Agility', 'Reaction', 'Strength', 'init_dice'],
  Bioware: ['essence', 'dr', 'Body', 'Agility', 'Reaction', 'Strength', 'Willpower', 'Logic', 'Intuition', 'Charisma'],
  Magic: ['focus', 'force'], Vehicles: ['handling', 'accel', 'speed_interval', 'top_speed', 'body', 'armor', 'pilot', 'sensor', 'seats'],
  Drones: ['handling', 'accel', 'speed_interval', 'top_speed', 'body', 'armor', 'pilot', 'sensor'],
};
const FIELD_LABEL = { dv: 'Damage (e.g. 3P)', ar: 'Attack Ratings (C/N/M/F/E)', skill: 'Skill', spec: 'Specialization', modes: 'Modes (SS/SA/BF/FA)',
  ammo: 'Ammo (e.g. 15(c))', ammo_class: 'Ammo class', dv_gz: 'DV ground zero', dv_close: 'DV close', dv_near: 'DV near', blast: 'Blast',
  dr: 'Defense Rating bonus', device_rating: 'Device Rating', data_processing: 'Data Processing', firewall: 'Firewall', program_slots: 'Program slots',
  attack: 'Attack', sleaze: 'Sleaze', essence: 'Essence cost', init_dice: 'Initiative dice', focus: 'Focus type', force: 'Force',
  handling: 'Handling', accel: 'Acceleration', speed_interval: 'Speed interval', top_speed: 'Top speed', body: 'Body', armor: 'Armor',
  pilot: 'Pilot', sensor: 'Sensor', seats: 'Seats' };
/* Custom item (GM gifts, draft homebrew). Returns the item dict or null. */
async function editItem(item, { title, ok = 'Save', cat, statsLocked = false } = {}) {
  item = Object.assign({}, item || {});
  const catSel = h('select', CAT.store.categories.map(c => option(c, c, c === (item.cat || cat || 'Survival'))));
  catSel.disabled = statsLocked;
  const name = h('input', { value: item.name || '', required: true, maxlength: 80 });
  const cost = h('input', { type: 'number', min: 0, value: item.cost ?? 0, disabled: statsLocked });
  const qty = h('input', { type: 'number', min: 1, value: item.qty ?? 1, disabled: statsLocked });
  const avail = h('input', { value: item.avail != null && item.avail !== '' ? availText(item.avail, item.legal) : '', placeholder: 'e.g. 4(L)', disabled: statsLocked });
  const desc = h('textarea', { rows: 3, maxlength: 1000 }, item.desc || '');
  const grid = h('div.form-grid');
  const inputs = {};
  function drawFields() {
    grid.innerHTML = '';
    for (const f of CUSTOM_FIELDS[catSel.value] || []) {
      let inp;
      if (f === 'skill') inp = h('select', option('', '—'), Object.keys(CAT.skills).map(s => option(s, s, item[f] === s)));
      else if (f === 'focus') inp = h('select', option('', '—'), Object.keys(CAT.focusBond).map(s => option(s, s, item[f] === s)));
      else inp = h('input', { value: item[f] ?? '' });
      inp.disabled = statsLocked;
      inputs[f] = inp; grid.append(h('label', FIELD_LABEL[f] || f, inp));
    }
  }
  catSel.onchange = () => { for (const k of Object.keys(inputs)) delete inputs[k]; drawFields(); };
  drawFields();
  const body = h('div', h('div.form-grid', h('label', 'Name', name), h('label', 'Category', catSel), h('label', 'Price (¥ each)', cost), h('label', 'Quantity', qty),
    h('label', 'Availability', avail)), grid, h('label.stack', 'Description', desc),
    statsLocked ? h('p.hint', 'Only the name and description of this item can change.') : null);
  const okd = await UI.modal(title || (item.name ? `Edit ${item.name}` : 'Custom item'), body, { ok });
  if (!okd) return null;
  const out = { name: name.value.trim(), desc: desc.value.trim(), cat: catSel.value, cost: +cost.value || 0, qty: +qty.value || 1, avail: avail.value.trim() };
  for (const [f, inp] of Object.entries(inputs)) if (String(inp.value).trim() !== '') out[f] = inp.value.trim();
  return out;
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

return { actionPips, invite, catalog, contactSupply, rollSummary, get CAT() { return CAT; }, statusTag, healthTag, pips, statusChips, monitor, dieEl, verdict, logEntry, renderLog,
  roller, edgeMenu, editItem, itemStats, availText, arText, breakdown, sum, RANGES };
})();

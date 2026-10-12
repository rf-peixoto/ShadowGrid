/* Printable character sheet (filled from the server, or blank). Uses the browser's print dialog,
   which also saves to PDF. */
(async () => {
  'use strict';
  const url = document.body.dataset.sheetUrl;
  const root = document.getElementById('sheet');
  const CORE = ['Body', 'Agility', 'Reaction', 'Strength', 'Willpower', 'Logic', 'Intuition', 'Charisma'];
  let CAT, SH = null;
  try {
    CAT = await SR.catalog();
    if (url) SH = await api(url);
  } catch (e) { root.innerHTML = ''; root.append(h('p.loading', 'Could not load the sheet: ' + e.message)); return; }

  const blank = !SH;
  const c = SH ? SH.char : null, d = SH ? SH.derived : null;
  const v = (x, fallback = '') => (blank || x === undefined || x === null ? fallback : x);
  const box = (title, ...kids) => h('section.box', h('h2', title), ...kids);
  const kv = rows => h('dl.kv', rows.map(([k, val, cls]) => [h('dt', k), h('dd' + (cls ? '.' + cls : ''), val === '' ? '' : String(val))]).flat());
  const rows = (n, cols) => Array.from({ length: n }, () => h('tr', Array.from({ length: cols }, () => h('td'))));
  const pool = key => { const p = SH && SH.pools.find(x => x.key === key); return p ? p.value : ''; };

  function monitor(label, boxes, filled, { every = 3, overflow = 0, ovFilled = 0 } = {}) {
    const m = h('div.monitor');
    for (let i = 1; i <= boxes; i++) {
      const el = h('i' + (i <= filled ? '.full' : ''));
      if (every && i % every === 0) { el.classList.add('mark'); el.dataset.m = `−${i / every}`; }
      m.append(el);
    }
    for (let i = 1; i <= overflow; i++) m.append(h('i.ov' + (i <= ovFilled ? '.full' : '')));
    return [h('div.monitor-label', h('span', label), h('span.hint', blank ? 'cross out the boxes you don’t have' : `${filled}/${boxes}${overflow ? ` · overflow ${ovFilled}/${overflow}` : ''}`)), m];
  }
  const label = i => i.name + (i.rating && !String(i.name).endsWith(` ${i.rating}`) ? ` ${i.rating}` : '');
  const pips = (cur, max) => h('span.pips', Array.from({ length: max }, (_, i) => h('i' + (i < cur ? '.on' : ''))));

  // ------------------------------------------------------------ page 1: the runner
  function page1(allSkills) {
    const p = h('div.page');
    const sub = blank ? '' : [c.metatype, c.role, c.magic_type !== 'Mundane' ? c.magic_type : ''].filter(Boolean).join(' · ');
    p.append(h('header.masthead', h('h1', blank ? h('span.blank', ' ') : (c.name || 'Unnamed runner'), sub ? h('div.hint', sub) : null),
      h('div.brand', 'SHADOWRUN · SIXTH WORLD', h('small', 'ShadowGrid character sheet'))));

    const personal = box('Personal data', kv([
      ['Name', v(c && c.name)], ['Metatype', v(c && c.metatype)], ['Role', v(c && c.role)],
      ['Magic / Res.', v(c && c.magic_type)], ['Tradition', v(c && (c.tradition || c.aspect))], ['Lifestyle', v(c && c.lifestyle)],
      ['Age', v(c && c.age)], ['Reputation', v(c && c.reputation)], ['Heat', v(c && c.heat)],
      ['Karma', v(c && c.karma), 'num'], ['Nuyen', blank ? '' : money(c.nuyen), 'num']]));

    const at = h('table.attr-table', h('thead', h('tr', h('th', 'Attribute'), h('th.num', 'Base'), h('th.num', 'Rating'), h('th.num', 'Max'))));
    const tb = h('tbody');
    const attrs = [...CORE, 'Edge'];
    if (blank || c.magic_type !== 'Mundane') attrs.push(blank || c.magic_type !== 'Technomancer' ? 'Magic' : 'Resonance');
    if (blank) attrs.push('Resonance');
    for (const a of attrs) tb.append(h('tr', h('td', a), h('td.num', v(d && d.base[a])), h('td.num', v(d && d.attributes[a])), h('td.num', v(d && d.max[a]))));
    at.append(tb);
    const attributes = box('Attributes', at);

    const derived = box('Derived', kv([
      ['Initiative', blank ? '' : `${d.initiative_score} + ${d.initiative_dice}D6`, 'num'],
      ['Actions', blank ? '' : `1 Major + ${d.minor_actions} Minor`],
      ['Defense Rating', v(d && d.defense_rating), 'num'], ['Essence', v(d && d.essence), 'num'],
      ['Composure', v(d && d.composure), 'num'], ['Judge Intentions', v(d && d.judge_intentions), 'num'],
      ['Memory', v(d && d.memory), 'num'], ['Lift / Carry', blank ? '' : `${d.lift_carry} (${d.lift_kg} kg)`],
      ['Movement', blank ? '' : `${d.movement.walk}/${d.movement.sprint} m, +${d.movement.per_hit}/hit`],
      ['Unarmed', blank ? '' : `DV ${d.unarmed.dv}${d.unarmed.type} · AR ${d.unarmed.ar}`],
      ['Vision', blank ? '' : (d.vision || []).join(', ') || 'Normal']]),
      h('div.monitor-label.edge', h('span', 'Edge'), blank ? h('span.hint', 'max 7') : h('span.hint', `${c.current_edge}/${d.edge_max}`)),
      pips(blank ? 0 : c.current_edge, blank ? 7 : d.edge_max));

    const pm = blank ? 18 : d.physical_boxes, sm = blank ? 12 : d.stun_boxes;
    const monitors = box('Condition monitors',
      ...monitor('Physical', pm, blank ? 0 : Math.min(c.physical_damage, pm), { overflow: blank ? 12 : d.overflow_boxes, ovFilled: blank ? 0 : Math.max(0, c.physical_damage - pm) }),
      ...monitor('Stun', sm, blank ? 0 : c.stun_damage),
      h('p.hint', 'Every 3 boxes on a track: −1 die. Dashed boxes are Physical overflow.'));

    const quals = box('Qualities', blank ? h('div.lines', Array.from({ length: 6 }, () => h('div'))) :
      h('ul.plain', (d.qualities || []).map(q => h('li', q.name + (q.level > 1 ? ` ${q.level}` : '') + (q.choice ? ` (${q.choice})` : '') + (q.racial ? ' · racial' : '')))));

    // skills
    const st = h('table', h('thead', h('tr', h('th', 'Skill'), h('th', 'Attribute'), h('th.num', 'Rank'), h('th', 'Specialization / expertise'), h('th.num', 'Pool'))));
    const sb = h('tbody');
    for (const [name, sk] of Object.entries(CAT.skills)) {
      const rank = blank ? 0 : (c.skills[name] || 0);
      if (!blank && !rank && !allSkills) continue;
      const spec = blank ? '' : [c.specs[name] ? `${c.specs[name]} +2` : '', c.expertise[name] ? `${c.expertise[name]} +3` : ''].filter(Boolean).join(' · ');
      sb.append(h('tr' + (!blank && !rank ? '.untrained' : ''), h('td', name), h('td.hint', sk.attr || ''), h('td.num', blank ? '' : rank || '—'), h('td', spec), h('td.num', blank ? '' : pool('skill:' + name))));
    }
    st.append(sb);
    const skills = box('Skills', st);
    const know = box('Knowledge and languages', blank ? h('table', h('tbody', rows(7, 2))) :
      h('ul.plain', [...(c.knowledge || []).map(k => h('li', k)), ...(c.languages || []).map(l => h('li', `${l.name} (${l.level})`))]));

    p.append(h('div.grid.g3', personal, attributes, derived), h('div.grid.g2', { style: { marginTop: '3mm' } }, monitors, quals),
      h('div.grid', { style: { marginTop: '3mm' } }, skills), h('div.grid', { style: { marginTop: '3mm' } }, know));
    return p;
  }

  // ------------------------------------------------------------ page 2: gear, contacts, magic, notes
  function page2() {
    const p = h('div.page');
    p.append(h('header.masthead', h('h1', blank ? 'Gear, contacts and magic' : `${c.name || 'Runner'}: gear and contacts`), h('div.brand', 'SHADOWRUN · SIXTH WORLD')));
    const inv = blank ? [] : c.inventory || [];
    const weapons = inv.filter(i => i.cat === 'Ranged' || i.cat === 'Melee' || (i.cat === 'Ammo & Explosives' && i.dv_gz));
    const wt = h('table', h('thead', h('tr', h('th', 'Weapon'), h('th.num', 'DV'), h('th', 'AR (C/N/M/F/E)'), h('th', 'Modes'), h('th', 'Ammo'), h('th.num', 'Pool'))));
    const wb = h('tbody');
    for (const w of weapons) wb.append(h('tr', h('td', w.name), h('td.num', w.dv || (w.dv_gz ? `${w.dv_gz}` : '')), h('td.ar', Array.isArray(w.ar) ? w.ar.map(a => a ?? '—').join('/') : (w.ar || '')),
      h('td', w.modes || ''), h('td.num', w.clip ? `${(w.loaded && w.loaded.rounds) || 0}/${w.clip}${w.loaded && w.loaded.type && w.loaded.type !== 'Regular' ? ' ' + w.loaded.type : ''}` : (w.qty > 1 ? `×${w.qty}` : '')), h('td.num', pool('weapon:' + w.uid))));
    if (blank || weapons.length < 4) wb.append(...rows(blank ? 6 : 2, 6));
    wt.append(wb);

    const worn = inv.filter(i => i.cat === 'Armor' || i.implant);
    const at = h('table', h('thead', h('tr', h('th', 'Armor and augmentations'), h('th', 'Effect'), h('th.num', 'Ess.'))));
    at.append(h('tbody', worn.map(i => h('tr', h('td', label(i) + (i.grade && i.grade !== 'Standard' && !i.name.includes(i.grade) ? ` (${i.grade})` : '')), h('td.hint', SR.itemStats(i)), h('td.num', i.implant ? i.essence : ''))), ...rows(blank ? 6 : 1, 3)));

    const rest = inv.filter(i => !weapons.includes(i) && !worn.includes(i));
    const gear = box('Other gear', blank ? h('div.lines', Array.from({ length: 10 }, () => h('div'))) :
      h('ul.plain', rest.map(i => h('li', label(i) + (i.qty > 1 ? ` ×${i.qty}` : '')))));

    const ct = h('table', h('thead', h('tr', h('th', 'Contact'), h('th', 'Type'), h('th.num', 'Conn'), h('th.num', 'Loy'))));
    ct.append(h('tbody', (blank ? [] : c.contacts || []).map(x => h('tr', h('td', x.name), h('td', x.type || ''), h('td.num', x.connection), h('td.num', x.loyalty))), ...rows(blank ? 6 : 1, 4)));

    const blocks = [box('Weapons', wt), box('Armor and augmentations', at), gear, box('Contacts', ct)];
    const awakened = blank || ['Magician', 'Aspected Magician', 'Adept', 'Mystic Adept'].includes(c.magic_type);
    if (awakened) {
      const sp = h('table', h('thead', h('tr', h('th', 'Spell / power'), h('th', 'Type'), h('th', 'Range'), h('th', 'Duration'), h('th.num', 'Drain'))));
      sp.append(h('tbody', ...(blank ? [] : [...(c.spells || []).map(s => h('tr', h('td', s.name), h('td', s.category || ''), h('td', s.range || ''), h('td', s.duration || ''), h('td.num', s.drain ?? ''))),
        ...(c.powers || []).map(pw => h('tr', h('td', pw.name + (pw.level > 1 ? ` ${pw.level}` : '')), h('td', 'Adept power'), h('td'), h('td'), h('td')))]), ...rows(blank ? 8 : 1, 5)));
      blocks.push(box('Magic', blank ? null : h('p.hint', `Drain pool ${d.drain_pool} · spell AR ${d.spell_ar} · initiate grade ${c.initiation_grade}`), sp));
    }
    if (!blank && c.magic_type === 'Technomancer') {
      blocks.push(box('Resonance', h('p.hint', `Fading pool ${d.fading_pool} · submersion grade ${c.submersion_grade}`),
        h('ul.plain', (c.complex_forms || []).map(f => h('li', `${f.name} (fading ${f.fading ?? ''})`)))));
    }
    if (blank || (d.matrix && d.matrix.device)) {
      const m = d && d.matrix;
      blocks.push(box('Matrix', kv([['Device', blank ? '' : ((c.inventory || []).find(i => i.uid === m.device) || { name: m.device === 'living' ? 'Living persona' : m.device }).name], ['A / S / D / F', blank ? '' : `${m.attack} / ${m.sleaze} / ${m.data_processing} / ${m.firewall}`, 'num'],
        ['Programs', blank ? '' : (m.programs || []).join(', ')]]), ...(blank ? monitor('Matrix damage', 12, 0, { every: 0 }) : monitor('Matrix damage', m.boxes, m.damage, { every: 0 }))));
    }
    const vehicles = blank ? [] : inv.filter(i => i.handling);
    if (blank || vehicles.length) {
      const vt = h('table', h('thead', h('tr', h('th', 'Vehicle / drone'), h('th', 'Hand'), h('th', 'Acc'), h('th', 'Spd'), h('th', 'Bod'), h('th', 'Arm'), h('th', 'Pil'), h('th', 'Sen'))));
      vt.append(h('tbody', vehicles.map(x => h('tr', h('td', x.name), h('td.num', x.handling), h('td.num', x.accel), h('td.num', `${x.speed_interval}/${x.top_speed}`), h('td.num', x.body), h('td.num', x.armor), h('td.num', x.pilot), h('td.num', x.sensor))), ...rows(blank ? 4 : 0, 8)));
      blocks.push(box('Vehicles and drones', vt));
    }
    blocks.push(box('Notes', blank ? h('div.lines', Array.from({ length: 8 }, () => h('div'))) : h('div.notes', [c.background, c.notes].filter(Boolean).join('\n\n') || ' ')));
    const g = h('div.grid.g2');
    blocks.forEach((b, i) => { if (i === 0) b.classList.add('span2'); g.append(b); });
    p.append(g);
    return p;
  }

  function draw() {
    root.innerHTML = '';
    root.append(page1(document.getElementById('opt-skills').checked));
    if (document.getElementById('opt-gear').checked) root.append(page2());
    document.title = blank ? 'Blank character sheet · ShadowGrid' : `${c.name || 'Runner'} · character sheet`;
  }
  document.getElementById('opt-gear').onchange = draw;
  document.getElementById('opt-skills').onchange = draw;
  document.getElementById('opt-skills').checked = blank;
  document.getElementById('opt-skills').disabled = blank;
  document.getElementById('btn-print').onclick = () => window.print();
  draw();
})();

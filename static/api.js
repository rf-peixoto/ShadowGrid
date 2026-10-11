/* Shared client helpers: JSON API with CSRF header, toasts, DOM builder, dialogs. */
window.api = async function api(path, method = 'GET', body) {
  const res = await fetch(path, {
    method, headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'GridMap' },
    body: body === undefined ? undefined : (typeof body === 'string' ? body : JSON.stringify(body)),
  });
  if (res.status === 401) { location.href = '/login?next=' + encodeURIComponent(location.pathname); throw new Error('auth'); }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new Error((data && data.error) || res.statusText);
  return data;
};
window.toast = function toast(msg, ms = 2600) {
  let el = document.getElementById('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
  el.textContent = msg; el.classList.add('show');
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove('show'), ms);
};
window.escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* h('div.card#id', {onclick, title, ...}, child, 'text', [children]) */
window.h = function h(sel, attrs, ...kids) {
  const m = /^([a-z0-9]+)?((?:[.#][\w-]+)*)$/i.exec(sel) || [];
  const el = document.createElement(m[1] || 'div');
  for (const part of (m[2] || '').match(/[.#][\w-]+/g) || []) {
    if (part[0] === '.') el.classList.add(part.slice(1)); else el.id = part.slice(1);
  }
  if (attrs !== null && attrs !== undefined && (typeof attrs !== 'object' || attrs instanceof Node || Array.isArray(attrs))) { kids.unshift(attrs); attrs = null; }
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'class') el.className += ' ' + v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (['value', 'checked', 'disabled', 'selected', 'hidden', 'open', 'textContent', 'innerHTML'].includes(k)) el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  const add = c => { if (c === null || c === undefined || c === false) return; if (Array.isArray(c)) c.forEach(add); else el.append(c instanceof Node ? c : document.createTextNode(String(c))); };
  kids.forEach(add);
  return el;
};
window.money = n => `${Math.round(Number(n) || 0).toLocaleString('en-US')}¥`;
window.timeAgo = t => {
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 60) return 'just now'; if (s < 3600) return Math.floor(s / 60) + ' min ago';
  if (s < 86400) return Math.floor(s / 3600) + ' h ago'; return new Date(t * 1000).toLocaleDateString();
};
window.option = (value, label, selected) => h('option', { value, selected: !!selected }, label ?? value);

/* Promise-based modal dialogs built on <dialog>. */
window.UI = (() => {
  function modal(title, body, { ok = 'Save', cancel = 'Cancel', danger = false, wide = false, narrow = false, onOpen } = {}) {
    return new Promise(resolve => {
      const d = h('dialog', { class: wide ? 'wide' : narrow ? 'narrow' : '' });
      const form = h('form', { method: 'dialog' });
      form.append(h('h2', title), body);
      const okBtn = ok ? h('button', { value: 'ok', class: danger ? 'danger primary' : 'primary' }, ok) : null;
      form.append(h('div.row.end', cancel ? h('button', { value: 'cancel', type: 'button', onclick: () => d.close('cancel') }, cancel) : null, okBtn));
      d.append(form); document.body.append(d);
      form.addEventListener('submit', e => {
        if (e.submitter && e.submitter.value === 'ok' && !form.checkValidity()) { e.preventDefault(); form.reportValidity(); }
      });
      d.addEventListener('close', () => { resolve(d.returnValue === 'ok'); setTimeout(() => d.remove(), 0); });
      d.showModal();
      if (onOpen) onOpen(d);
      const first = body.querySelector && body.querySelector('input:not([type=hidden]):not([type=checkbox]), select, textarea');
      if (first) first.focus();
    });
  }
  const confirm = (text, opts = {}) => modal(opts.title || 'Are you sure?', h('p', text), { ok: opts.ok || 'Confirm', danger: opts.danger, narrow: true });
  async function prompt(title, label, { value = '', type = 'text', ok = 'OK', hint = '', min, required = true } = {}) {
    const inp = h('input', { type, value, min, required });
    const okd = await modal(title, h('div', h('label.stack', label, inp), hint ? h('p.hint', hint) : null), { ok, narrow: true });
    return okd ? inp.value : null;
  }
  function info(title, content) { return modal(title, content, { ok: 'Close', cancel: null, narrow: true }); }
  return { modal, confirm, prompt, info };
})();

/* Tiny Markdown-ish renderer for wiki topics (**bold** lines become headings, "- " lines become lists). */
window.renderWiki = function renderWiki(text) {
  const out = h('div');
  let list = null;
  for (const raw of String(text || '').split('\n')) {
    const line = raw.trimEnd();
    if (/^\*\*(.+)\*\*$/.test(line)) { list = null; out.append(h(out.childNodes.length ? 'h3' : 'h2', line.slice(2, -2))); continue; }
    if (line.startsWith('- ')) { if (!list) { list = h('ul'); out.append(list); } list.append(h('li', line.slice(2))); continue; }
    list = null;
    if (line.trim()) out.append(h('p', line));
  }
  return out;
};

/* Sign-in and invite pages: solve the proof of work, then post the form. */
(() => {
  const bits = +document.body.dataset.bits;
  const status = document.getElementById('login-status');
  const $ = id => document.getElementById(id);
  const toGate = () => { location.href = '/gate?next=' + encodeURIComponent(location.pathname + location.search); };
  async function solve() {
    const r = await fetch('/api/login/challenge');
    if (r.status === 403) { toGate(); throw new Error('gate'); }
    const ch = await r.json();
    const counter = await GridPow.solve(ch.challenge, ch.bits || bits);
    return { challenge: ch.challenge, counter };
  }
  async function submit(form, btn, url, payload) {
    btn.disabled = true; status.textContent = 'Checking your browser…';
    let pow;
    try { pow = await solve(); } catch (e) {
      if (e.message === 'gate') return;
      status.textContent = e instanceof TypeError ? 'Could not reach the server. Check the address and your connection.' : `The browser check failed: ${e.message}`;
      btn.disabled = false; return;
    }
    try {
      status.textContent = 'Signing in…';
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'ShadowGrid' },
        body: JSON.stringify({ ...payload, ...pow }) });
      const data = await res.json().catch(() => ({}));
      if (res.status === 403 && data.gate) { toGate(); return; }
      if (!res.ok) { status.textContent = data.error || 'Something went wrong.'; btn.disabled = false; return; }
      location.href = data.next || '/';
    } catch (e) { if (e.message !== 'gate') { status.textContent = 'Could not reach the server.'; btn.disabled = false; } }
  }
  const lf = $('login-form');
  if (lf) lf.onsubmit = e => {
    e.preventDefault();
    const next = new URLSearchParams(location.search).get('next') || '';
    submit(lf, $('btn-login'), '/api/login', { username: $('username').value.trim(), password: $('password').value, next });
  };
  const inf = $('invite-form');
  if (inf) inf.onsubmit = e => {
    e.preventDefault();
    if ($('password').value !== $('password2').value) { status.textContent = 'The two passwords are different.'; $('password2').focus(); return; }
    submit(inf, $('btn-join'), '/api/invite/' + encodeURIComponent(document.body.dataset.token), { username: $('username').value.trim(), password: $('password').value });
  };
})();

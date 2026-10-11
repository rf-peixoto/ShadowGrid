/* Sign-in and invite pages: solve the proof of work, then post the form. */
(() => {
  const bits = +document.body.dataset.bits;
  const status = document.getElementById('login-status');
  const $ = id => document.getElementById(id);
  async function solve() {
    const ch = await (await fetch('/api/login/challenge')).json();
    const counter = await GridPow.solve(ch.challenge, ch.bits || bits, n => { status.textContent = `Checking your browser… (${n})`; });
    return { challenge: ch.challenge, counter };
  }
  async function submit(form, btn, url, payload) {
    btn.disabled = true; status.textContent = 'Checking your browser…';
    try {
      const pow = await solve();
      status.textContent = 'Signing in…';
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'GridMap' },
        body: JSON.stringify({ ...payload, ...pow }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { status.textContent = data.error || 'Something went wrong.'; btn.disabled = false; return; }
      location.href = data.next || '/';
    } catch (e) { status.textContent = 'Could not reach the server.'; btn.disabled = false; }
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

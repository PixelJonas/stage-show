/* ===================== FX 2026-11-19 =====================
   Particle layer of a stage show. Copy it unchanged; API: choreography.md of the stage-show skill. */
const FX = (() => {
  const cv = document.getElementById('fx');
  if (!cv || !cv.getContext) throw new Error('FX: no <canvas id="fx"> before this script');
  const num = (v, d) => (v = parseFloat(v)) > 0 ? v : d;
  const ctx = cv.getContext('2d'), N = Math.round(num(cv.dataset.n, 240)), R = num(cv.dataset.r, 4), P = [], FORM = {}, NAMES = new Set();
  cv.width = 1920; cv.height = 1080;                // stage size until the first FX.resize
  const rnd = (a, b) => a + Math.random() * (b - a);
  for (let i = 0; i < N; i++) { const hx = rnd(0, 1920), hy = rnd(0, 1080); P.push({ x: hx, y: hy, hx, hy, ph: rnd(0, 6.3), a: 0 }); }   // each dot starts at home: no sweep at load
  function sample(draw, n = N) {                    // about n points, evenly spread, in stage px, inside whatever draw(g) paints
    const m = document.createElement('canvas'); m.width = 480; m.height = 270;
    const g = m.getContext('2d', { willReadFrequently: true }); g.scale(.25, .25); draw(g);
    const px = g.getImageData(0, 0, 480, 270).data, hit = [];
    for (let i = 3; i < px.length; i += 4) if (px[i] > 127) hit.push([(i - 3) / 4 % 480, (i - 3) / 4 / 480 | 0]);
    const s = Math.max(1, Math.sqrt(hit.length / n)), cell = v => Math.floor(v / s);      // grid spacing that leaves about n points
    const pts = hit.filter(([x, y]) => cell(x) !== cell(x - 1) && cell(y) !== cell(y - 1)).map(([x, y]) => [x * 4 + 2, y * 4 + 2]);
    for (let i = pts.length - 1; i > 0; i--) { const j = Math.random() * (i + 1) | 0; [pts[i], pts[j]] = [pts[j], pts[i]]; }
    return pts.slice(0, n);                         // shuffled, so particles cross on their way in
  }
  let mode = 'drift', color = '#888';
  function frame(now) {
    const f = FORM[mode], still = window.STAGE?.still, k = still ? 1 : .03;   // reduced motion: land at once instead of travelling
    ctx.clearRect(0, 0, 1920, 1080);
    ctx.fillStyle = color;
    P.forEach((p, i) => {
      let tx = p.hx, ty = p.hy, ta = .3;
      if (f) { if (f[i]) { [tx, ty] = f[i]; ta = .9; } else ta = 0; }   // particles beyond the formation fade out
      else if (mode === 'none') ta = 0;
      else if (!still) { tx += Math.sin(now * .00015 + p.ph) * 30; ty += Math.cos(now * .00013 + p.ph) * 25; }
      p.x += (tx - p.x) * k; p.y += (ty - p.y) * k; p.a += (ta - p.a) * .05;
      if (p.a < .01) return;
      ctx.globalAlpha = p.a; ctx.beginPath(); ctx.arc(p.x, p.y, R, 0, 6.283); ctx.fill();
    });
    ctx.globalAlpha = 1;
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  return {
    form(name, make) {
      NAMES.add(name);
      Promise.resolve().then(make).then(pts => { if (!pts.length) throw new Error('no points'); FORM[name] = pts.slice(0, N); },
        e => console.error('FX.form', name, e));
    },
    text: (str, font, n) => document.fonts.load(font, str).then(() =>
      sample(g => { g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(str, 960, 540); }, n)),
    path: (d, x, y, k, n) => sample(g => { g.transform(k, 0, 0, k, x, y); g.fill(new Path2D(d)); }, n),
    set(m) {
      if (m !== 'drift' && m !== 'none' && !NAMES.has(m)) console.error('FX: no formation', m);
      mode = m; color = getComputedStyle(document.documentElement).getPropertyValue('--fx').trim() || color;
    },
    resize(k) { const d = Math.min(devicePixelRatio || 1, 2); cv.width = 1920 * k * d; cv.height = 1080 * k * d; ctx.setTransform(k * d, 0, 0, k * d, 0, 0); }
  };
})();

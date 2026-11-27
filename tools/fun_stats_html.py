r"""Render the fun career stats JSON (from fun_stats.py) into a self-contained local HTML page.

usage: python fun_stats_html.py STATS.json OUT.html
No external resources (everything stays local).
"""
import html, json, os, sys

S = json.load(open(sys.argv[1], encoding="utf-8"))
if "player" not in S:  # stats written before fun_stats.py stored the player
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ddconfig import ME
    S["player"] = ME
DATA = json.dumps(S, ensure_ascii=False).replace("</", "<\\/")
PLAYER = html.escape(S["player"])

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PLAYER__ Career Stats</title>
<style>
:root {
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --ring: rgba(11,11,11,0.10);
  --s1: #2a78d6; --s1soft: #86b6ef; --red: #e34948; --accent: #eb6834;
  --badge-bg: #fff1e0; --badge-ink: #8a3a00;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
    --s1: #3987e5; --s1soft: #1c5cab; --red: #e66767; --accent: #d95926;
    --badge-bg: #3a2414; --badge-ink: #ffb784;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --ring: rgba(255,255,255,0.10);
  --s1: #3987e5; --s1soft: #1c5cab; --red: #e66767; --accent: #d95926;
  --badge-bg: #3a2414; --badge-ink: #ffb784;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--page); color: var(--ink);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 32px 16px 64px; }
header h1 { font-size: 34px; line-height: 1.1; margin: 0 0 6px; letter-spacing: -0.02em; }
header p { margin: 0; color: var(--ink2); }
.kicker { text-transform: uppercase; letter-spacing: .12em; font-size: 12px; color: var(--accent); font-weight: 700; margin-bottom: 8px; }
h2 { font-size: 20px; margin: 44px 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--ink2); margin: 0 0 14px; font-size: 14px; }
.card { background: var(--surface); border: 1px solid var(--ring); border-radius: 12px; padding: 18px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-top: 24px; }
.tile .v { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; }
.tile .l { color: var(--ink2); font-size: 13px; margin-top: 4px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 760px) { .grid2 { grid-template-columns: 1fr; } header h1 { font-size: 27px; } }
.card h3 { margin: 0 0 2px; font-size: 15px; }
.card .note { color: var(--muted); font-size: 12.5px; margin: 0 0 12px; }
svg { display: block; width: 100%; height: auto; overflow: visible; }
svg text { fill: var(--muted); font-size: 11px; font-family: inherit; }
.hbar { display: grid; grid-template-columns: minmax(90px, 34%) 1fr auto; gap: 10px; align-items: center; margin: 5px 0; font-size: 13.5px; }
.hbar .n { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hbar .track { height: 12px; position: relative; }
.hbar .fill { position: absolute; left: 0; top: 0; bottom: 0; background: var(--s1); border-radius: 0 4px 4px 0; min-width: 2px; }
.hbar .num { font-variant-numeric: tabular-nums; color: var(--ink2); min-width: 46px; text-align: right; }
.me { color: var(--accent); font-weight: 700; }
.riv { display: grid; grid-template-columns: 1fr minmax(80px, 150px) 1fr; gap: 8px; align-items: center; margin: 4px 0; font-size: 13.5px; }
.riv .side { height: 12px; position: relative; }
.riv .k { position: absolute; left: 0; top: 0; bottom: 0; background: var(--s1); border-radius: 0 4px 4px 0; }
.riv .d { position: absolute; right: 0; top: 0; bottom: 0; background: var(--red); border-radius: 4px 0 0 4px; }
.riv .nm { text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.riv .nm small { display: block; color: var(--muted); font-size: 11.5px; font-variant-numeric: tabular-nums; }
.legend { display: flex; gap: 16px; font-size: 12.5px; color: var(--ink2); margin-bottom: 10px; flex-wrap: wrap; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
.ladder { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; }
.ladder .card { padding: 14px; }
.ladder .v { font-size: 24px; font-weight: 700; }
.ladder .l { font-size: 12.5px; color: var(--ink2); }
.recs { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.rec .t { font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--accent); font-weight: 700; }
.rec .v { font-size: 22px; font-weight: 700; margin: 4px 0 2px; }
.rec .d { font-size: 12.5px; color: var(--ink2); word-break: break-word; }
table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
th, td { text-align: left; padding: 8px 8px; border-bottom: 1px solid var(--grid); }
th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }
td.r, th.r { text-align: right; font-variant-numeric: tabular-nums; }
.badge { display: inline-block; font-size: 11px; font-weight: 700; letter-spacing: .06em; padding: 2px 7px; border-radius: 999px;
  background: var(--badge-bg); color: var(--badge-ink); }
.badge.int { background: transparent; color: var(--muted); border: 1px solid var(--grid); }
.scroll { overflow-x: auto; }
#tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--ring);
  box-shadow: 0 4px 16px rgba(0,0,0,.18); border-radius: 8px; padding: 7px 10px; font-size: 12.5px; opacity: 0; transition: opacity .08s; z-index: 9; }
#tip b { display: block; }
.hit { cursor: default; }
footer { margin-top: 48px; color: var(--muted); font-size: 12.5px; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="kicker">UT99 · just for fun</div>
  <h1>__PLAYER__: the career in numbers</h1>
  <p id="span"></p>
</header>
<div class="tiles" id="tiles"></div>

<h2>When you played</h2>
<p class="sub">Hours recorded per month (all demos you appear in).</p>
<div class="card"><svg id="months"></svg></div>
<div class="grid2" style="margin-top:14px">
  <div class="card"><h3>Hour of the day</h3><p class="note">Hours played by the time the demo started (local time).</p><svg id="clock"></svg></div>
  <div class="card"><h3>Day of the week</h3><p class="note">Hours played per weekday.</p><svg id="wdays"></svg></div>
</div>

<h2>Who you hunted, who hunted you</h2>
<p class="sub">Top 12 each, counted over every scanned demo.</p>
<div class="grid2">
  <div class="card"><h3>Favourite victims</h3><p class="note">Players you fragged most.</p><div id="victims"></div></div>
  <div class="card"><h3>Nemeses</h3><p class="note">Players who fragged you most.</p><div id="nemesis"></div></div>
</div>
<div class="card" style="margin-top:14px">
  <h3>Rivalries</h3>
  <p class="note">The players you traded the most frags with (at least 150 between you).</p>
  <div class="legend"><span><i style="background:var(--s1)"></i>you fragged them</span><span><i style="background:var(--red)"></i>they fragged you</span></div>
  <div id="rivals"></div>
</div>

<h2>Multi-kills &amp; sprees</h2>
<p class="sub">Announcer calls for you.</p>
<div class="ladder" id="ladder"></div>

<h2>Records</h2>
<p class="sub">Single best moments, from the scans.</p>
<div class="recs" id="records"></div>

<h2>Maps</h2>
<p class="sub">Your 15 most played maps, by hours.</p>
<div class="card"><div id="maps"></div></div>

<div class="grid2" style="margin-top:14px">
  <div class="card"><h3>Regulars</h3><p class="note">Players in the most of your demos.</p><div id="regulars"></div></div>
  <div class="card"><h3>Game modes</h3><p class="note">Scanned demos per detected mode, by hours.</p><div id="modes"></div></div>
</div>

<h2>The archives</h2>
<p class="sub"><span class="badge">EXTERNAL</span> archives live on another drive (it may be unplugged). Plug it in before a project plays one of those demos.</p>
<div class="card scroll"><table id="arch"></table></div>

<footer id="foot"></footer>
</div>
<div id="tip"></div>
<script>
const S = __DATA__;
const $ = id => document.getElementById(id);
const fmt = n => Number(n).toLocaleString('en-US');
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ME = S.player;
const T = S.totals;

// tooltip
const tip = $('tip');
document.addEventListener('mousemove', e => {
  const t = e.target.closest('[data-tip]');
  if (!t) { tip.style.opacity = 0; return; }
  tip.innerHTML = t.dataset.tip; tip.style.opacity = 1;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
});

const months = S.months.filter(m => m.hours > 0);
const first = months[0]?.month, last = months[months.length - 1]?.month;
const mname = m => { if (!m) return ''; const [y, mo] = m.split('-'); return new Date(+y, +mo - 1, 1).toLocaleString('en-US', {month: 'short', year: 'numeric'}); };
$('span').textContent = `${fmt(T.meDemos)} demos from ${mname(first)} to ${mname(last)}, ${fmt(T.nights)} gaming nights. Every frag counted from the demo kill feed.`;

const tiles = [
  [fmt(Math.round(T.meHours)) + ' h', 'played on record'],
  [fmt(T.kills), 'frags'],
  [fmt(T.deaths), 'deaths'],
  [T.kd.toFixed(2), 'frags per death'],
  [fmt(T.combos), 'shock combo kills'],
  [fmt(T.caps), 'flag captures'],
  [fmt(T.saves), 'flag carriers stopped near their base'],
  [fmt(T.uniquePlayers), 'different player names met'],
];
$('tiles').innerHTML = tiles.map(([v, l]) => `<div class="card tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join('');

// vertical bar chart (single series)
function vbars(svg, items, opt) {
  const W = opt.w || 1080, H = opt.h || 220, pl = 36, pb = 26, pt = 8;
  const max = Math.max(...items.map(d => d.v), 1);
  const step = niceStep(max), top = Math.ceil(max / step) * step;
  const iw = W - pl, bw = iw / items.length, gap = Math.max(2, bw * 0.22);
  let g = '';
  for (let v = 0; v <= top; v += step) {
    const y = pt + (H - pb - pt) * (1 - v / top);
    g += `<line x1="${pl}" x2="${W}" y1="${y}" y2="${y}" stroke="var(${v ? '--grid' : '--axis'})" stroke-width="1"/>`;
    g += `<text x="${pl - 6}" y="${y + 4}" text-anchor="end">${fmt(v)}</text>`;
  }
  items.forEach((d, i) => {
    const x = pl + i * bw + gap / 2, w = bw - gap, h = (H - pb - pt) * d.v / top, y = H - pb - h;
    const r = Math.min(4, w / 2, h);
    if (h > 0) g += `<path d="M${x},${H - pb} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${H - pb} Z" fill="var(--s1)"/>`;
    g += `<rect class="hit" x="${pl + i * bw}" y="${pt}" width="${bw}" height="${H - pb - pt}" fill="transparent" data-tip="${esc(d.tip)}"/>`;
    if (d.label) g += `<text x="${x + w / 2}" y="${H - 8}" text-anchor="middle">${esc(d.label)}</text>`;
  });
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = g;
}
function niceStep(max) { const raw = max / 4, p = Math.pow(10, Math.floor(Math.log10(raw))); const n = raw / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p; }

// months: fill gaps between first and last month
const allM = [];
if (first) { let [y, m] = first.split('-').map(Number); const [ly, lm] = last.split('-').map(Number);
  while (y < ly || (y === ly && m <= lm)) { allM.push(`${y}-${String(m).padStart(2, '0')}`); if (++m > 12) { m = 1; y++; } } }
const byM = Object.fromEntries(S.months.map(m => [m.month, m]));
vbars($('months'), allM.map(k => {
  const m = byM[k] || {hours: 0, kills: 0}; const [y, mo] = k.split('-');
  return {v: m.hours, label: mo === '01' || k === first ? `${new Date(+y, +mo - 1).toLocaleString('en-US', {month: 'short'})} ${y}` : (+mo % 3 === 1 ? new Date(+y, +mo - 1).toLocaleString('en-US', {month: 'short'}) : ''),
    tip: `<b>${mname(k)}</b>${m.hours.toFixed(1)} h · ${fmt(m.kills)} frags`};
}), {h: 240});
vbars($('clock'), S.hours.map((v, h) => ({v, label: h % 3 === 0 ? String(h).padStart(2, '0') : '', tip: `<b>${String(h).padStart(2, '0')}:00–${String(h).padStart(2, '0')}:59</b>${v.toFixed(1)} h started`})), {w: 520, h: 200});
vbars($('wdays'), S.weekdays.map(d => ({v: d.hours, label: d.day, tip: `<b>${d.day}</b>${d.hours.toFixed(1)} h`})), {w: 520, h: 200});

function hbars(el, rows, unit) {
  const max = Math.max(...rows.map(r => r[1]), 1);
  el.innerHTML = rows.map(([n, v, extra]) => `<div class="hbar" data-tip="<b>${esc(n)}</b>${fmt(v)} ${unit}${extra ? ' · ' + extra : ''}">
    <span class="n ${n === ME ? 'me' : ''}">${esc(n)}</span><span class="track"><span class="fill" style="width:${100 * v / max}%"></span></span><span class="num">${fmt(v)}</span></div>`).join('');
}
hbars($('victims'), S.victims.slice(0, 12), 'frags');
hbars($('nemesis'), S.nemesis.slice(0, 12), 'deaths');
hbars($('regulars'), S.regulars.slice(0, 10), 'demos together');
hbars($('modes'), S.modes.filter(m => m.mode !== '?' && m.hours >= 0.5).sort((a, b) => b.hours - a.hours).map(m => [m.mode, Math.round(m.hours), fmt(m.demos) + ' demos']), 'h');
hbars($('maps'), S.maps.map(m => [m.map, Math.round(m.hours), fmt(m.kills) + ' frags']), 'h');

const rmax = Math.max(...S.rivals.map(r => Math.max(r.kills, r.deaths)), 1);
$('rivals').innerHTML = S.rivals.slice(0, 14).map(r => `<div class="riv" data-tip="<b>${esc(r.name)}</b>you fragged them ${fmt(r.kills)}×<br>they fragged you ${fmt(r.deaths)}×">
  <span class="side"><span class="d" style="width:${100 * r.deaths / rmax}%"></span></span>
  <span class="nm">${esc(r.name)}<small>${fmt(r.kills)} : ${fmt(r.deaths)}</small></span>
  <span class="side"><span class="k" style="width:${100 * r.kills / rmax}%"></span></span></div>`).join('');

const order = ['Double Kill', 'Triple Kill', 'Multi Kill', 'Mega Kill', 'Ultra Kill', 'Monster Kill', 'Ludicrous Kill', 'Holy Shit'];
const mk = Object.fromEntries(S.multis);
const sp = Object.fromEntries(S.sprees);
const lad = order.filter(k => mk[k]).map(k => [fmt(mk[k]), k]);
['on a killing spree', 'on a rampage', 'dominating', 'unstoppable', 'godlike', 'wicked sick'].forEach(k => { if (sp[k]) lad.push([fmt(sp[k]), k[0].toUpperCase() + k.slice(1)]); });
$('ladder').innerHTML = lad.map(([v, l]) => `<div class="card"><div class="v">${v}</div><div class="l">${esc(l)}</div></div>`).join('');

const R = S.records, recs = [];
const at = r => `${esc(r.demo.replace(/\.dem$/, ''))} at ${r.t} s`;
if (R.bestNight) recs.push(['Best night', `${fmt(R.bestNight.kills)} frags`, `${R.bestNight.date} · ${R.bestNight.hours} h · ${fmt(R.bestNight.deaths)} deaths`]);
if (R.topDemo) recs.push(['Most frags in one demo', `${fmt(R.topDemo.kills)} frags`, `${esc(R.topDemo.map)} · ${R.topDemo.minutes} min · ${fmt(R.topDemo.deaths)} deaths`]);
if (R.kdDemo) recs.push(['Best K/D (40+ frags)', `${(R.kdDemo.kills / Math.max(1, R.kdDemo.deaths)).toFixed(1)} : 1`, `${esc(R.kdDemo.map)} · ${fmt(R.kdDemo.kills)} frags, ${fmt(R.kdDemo.deaths)} deaths`]);
if (R.longestShot) recs.push(['Longest shot', `${fmt(R.longestShot.metrics.distance)} uu`, `on ${esc(R.longestShot.victims.join(', '))} · ${at(R.longestShot)}`]);
if (R.highestAirKill) recs.push(['Highest air kill', `${fmt(R.highestAirKill.metrics.victimHeight)} uu up`, `on ${esc(R.highestAirKill.victims.join(', '))} · ${at(R.highestAirKill)}`]);
if (R.movingCombo) recs.push(['Most mobile combo', `${fmt(R.movingCombo.metrics.ballTravel)} uu ball`, `you moved ${fmt(R.movingCombo.metrics.shooterMoveH)} uu across, ${fmt(R.movingCombo.metrics.shooterMoveV)} up · ${at(R.movingCombo)}`]);
if (R.biggestCombo) recs.push(['Biggest combo', `${R.biggestCombo.victims.length} frags`, `${esc(R.biggestCombo.victims.join(', '))} · ${at(R.biggestCombo)}`]);
if (R.bestCap) recs.push(['Bloodiest cap', `${R.bestCap.metrics.frags} frags`, `${R.bestCap.metrics.run} s run · ${at(R.bestCap)}`]);
if (R.longestDemo) recs.push(['Longest demo', `${Math.round(R.longestDemo.minutes)} min`, `${esc(R.longestDemo.map)} · ${fmt(R.longestDemo.kills)} frags`]);
recs.push(['Flag work', `${fmt(T.grabs)} flag grabs`, `${fmt(T.caps)} captured · ${fmt(T.returns)} returned · ${fmt(T.covers)} carrier covers · ${fmt(T.botKills)} bot frags on the side`]);
$('records').innerHTML = recs.map(([t, v, d]) => `<div class="card rec"><div class="t">${t}</div><div class="v">${v}</div><div class="d">${d}</div></div>`).join('');

$('arch').innerHTML = `<tr><th>Archive</th><th>Storage</th><th class="r">Demos</th><th class="r">GB</th><th class="r">Scanned</th><th>Folder</th></tr>` +
  S.archives.map(a => `<tr><td>${esc(a.name)}</td><td>${a.external ? `<span class="badge">EXTERNAL</span>${a.connected ? '' : ' <span class="badge">not connected</span>'}` : '<span class="badge int">internal</span>'}</td>
  <td class="r">${fmt(a.files)}</td><td class="r">${a.gb}</td><td class="r">${fmt(a.scanned)}</td><td><code>${esc(a.folder)}</code></td></tr>`).join('');
$('foot').textContent = `Generated ${S.generated} from ${fmt(T.demos)} scanned demos (${fmt(Math.round(T.hours))} h, ${fmt(T.allKills)} frags by everyone). Unscanned: stubs, demos with missing maps, BunnyTrack.`;
</script>
</body>
</html>
"""
open(sys.argv[2], "w", encoding="utf-8").write(PAGE.replace("__PLAYER__", PLAYER).replace("__DATA__", DATA))
print("wrote", sys.argv[2])

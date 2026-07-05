/* Fret Check — reads window.FAMILIES / DEALS / META (from data/data.js).
   No frameworks, no network calls: everything is precomputed. */

const $ = (id) => document.getElementById(id);
const money = (n) => "$" + Math.round(n).toLocaleString("en-US");
const NS = "http://www.w3.org/2000/svg";

/* ---------- tabs ---------- */
function showTab(which) {
  $("panel-dash").hidden = which !== "dash";
  $("panel-deals").hidden = which !== "deals";
  $("tab-dash").classList.toggle("active", which === "dash");
  $("tab-deals").classList.toggle("active", which === "deals");
}
$("tab-dash").onclick = () => showTab("dash");
$("tab-deals").onclick = () => showTab("deals");

/* ---------- tiny SVG helpers (single hue, thin marks, direct labels) ---------- */
function svgEl(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

/* Vertical bars with a $ label above each bar and a small n below —
   for the ≤8-bar era and condition charts. */
function barChart(mount, items, valueKey, labelKey) {
  mount.innerHTML = "";
  const W = 460, H = 190, top = 26, bottom = 34;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart" });
  const max = Math.max(...items.map(d => d[valueKey]));
  const slot = W / items.length;
  const barW = Math.min(52, slot * 0.55);
  items.forEach((d, i) => {
    const h = (d[valueKey] / max) * (H - top - bottom);
    const x = slot * i + (slot - barW) / 2;
    const y = H - bottom - h;
    const bar = svgEl("rect", { x, y, width: barW, height: h, rx: 3, class: "bar" });
    bar.appendChild(svgEl("title", {})).textContent =
      `${d[labelKey]} — typical ${money(d[valueKey])} (${d.n.toLocaleString()} listings)`;
    svg.appendChild(bar);
    const val = svgEl("text", { x: x + barW / 2, y: y - 7, class: "t-val", "text-anchor": "middle" });
    val.textContent = money(d[valueKey]);
    svg.appendChild(val);
    const lab = svgEl("text", { x: x + barW / 2, y: H - bottom + 15, class: "t-lab", "text-anchor": "middle" });
    lab.textContent = d[labelKey];
    svg.appendChild(lab);
    const n = svgEl("text", { x: x + barW / 2, y: H - bottom + 29, class: "t-n", "text-anchor": "middle" });
    n.textContent = d.n.toLocaleString();
    svg.appendChild(n);
  });
  svg.appendChild(svgEl("line", { x1: 0, x2: W, y1: H - bottom, y2: H - bottom, class: "baseline" }));
  mount.appendChild(svg);
}

/* Histogram of asking prices with a median tick and an optional
   "your price" marker. */
function histChart(mount, fam, yourPrice) {
  mount.innerHTML = "";
  const { lo, hi, counts } = fam.hist;
  const W = 720, H = 150, top = 26, bottom = 22;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart" });
  const max = Math.max(...counts);
  const bw = W / counts.length;
  counts.forEach((c, i) => {
    const h = max ? (c / max) * (H - top - bottom) : 0;
    const b0 = lo + (i / counts.length) * (hi - lo);
    const b1 = lo + ((i + 1) / counts.length) * (hi - lo);
    const bar = svgEl("rect", {
      x: i * bw + 1, y: H - bottom - h, width: bw - 2, height: h, rx: 2, class: "bar-soft",
    });
    bar.appendChild(svgEl("title", {})).textContent =
      `${money(b0)}–${money(b1)}: ${c.toLocaleString()} listings`;
    svg.appendChild(bar);
  });
  const px = (v) => Math.min(W, Math.max(0, (v - lo) / (hi - lo) * W));
  const mx = px(fam.median);
  svg.appendChild(svgEl("line", { x1: mx, x2: mx, y1: top - 12, y2: H - bottom, class: "medline" }));
  const mlab = svgEl("text", {
    x: mx, y: 11, class: "t-val",
    "text-anchor": mx > W - 90 ? "end" : mx < 90 ? "start" : "middle",
  });
  mlab.textContent = `typical ${money(fam.median)}`;
  svg.appendChild(mlab);
  if (yourPrice) {
    const yx = px(yourPrice);
    svg.appendChild(svgEl("path", {
      d: `M ${yx - 7} ${H - bottom + 14} L ${yx + 7} ${H - bottom + 14} L ${yx} ${H - bottom + 2} Z`,
      class: "youmark",
    }));
  }
  svg.appendChild(svgEl("line", { x1: 0, x2: W, y1: H - bottom, y2: H - bottom, class: "baseline" }));
  const l0 = svgEl("text", { x: 2, y: H - 6, class: "t-n" }); l0.textContent = money(lo);
  const l1 = svgEl("text", { x: W - 2, y: H - 6, class: "t-n", "text-anchor": "end" }); l1.textContent = money(hi);
  svg.appendChild(l0); svg.appendChild(l1);
  mount.appendChild(svg);
}

/* ---------- dashboard ---------- */
const familySel = $("family");
let current = null;

function initFamilies() {
  const names = Object.keys(FAMILIES).sort();
  familySel.innerHTML = "";
  for (const name of names) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = `${name}  (${FAMILIES[name].n.toLocaleString()})`;
    familySel.appendChild(o);
  }
  familySel.value = names.includes("Fender Stratocaster (American)")
    ? "Fender Stratocaster (American)" : names[0];
  renderDash();
}

function renderDash() {
  const fam = FAMILIES[familySel.value];
  current = fam;
  $("s-median").textContent = money(fam.median);
  $("s-range").textContent = `${money(fam.p25)}–${money(fam.p75)}`;
  $("s-n").textContent = fam.n.toLocaleString();
  $("s-n-label").textContent = `for sale right now · #${fam.rank} most-listed guitar`;
  if (fam.days_median != null) {
    $("s-days").textContent = fam.days_median;
    const vs = fam.days_median <= META.market_days_median ? "sells faster than" : "sits longer than";
    $("s-days-label").textContent =
      `median days on market — ${vs} the market's ${META.market_days_median}`;
  } else {
    $("s-days").textContent = "–";
    $("s-days-label").textContent = "median days on market";
  }

  histChart($("hist"), fam, parseFloat($("price-in").value) || null);
  judge();

  $("card-era").hidden = fam.by_era.length < 2;
  if (fam.by_era.length >= 2) barChart($("era-chart"), fam.by_era, "median", "era");
  $("card-cond").hidden = fam.by_cond.length < 2;
  if (fam.by_cond.length >= 2) barChart($("cond-chart"), fam.by_cond, "median", "cond");

  const box = $("fam-deals");
  box.innerHTML = "";
  if (fam.deals.length) {
    $("fam-deal-note").textContent =
      `${fam.deal_count.toLocaleString()} listings in this group are priced below even its cheap ` +
      `quartile; here are the top ${fam.deals.length}. Asking prices — read before you believe.`;
    fam.deals.forEach(d => box.appendChild(dealCard(d)));
  } else {
    $("fam-deal-note").textContent =
      "No listing in this group currently clears our deal bar (meaningfully cheaper than even " +
      "the cheap end of its own market, no damage admitted in the title).";
  }
}

/* Rough percentile from the five known cut points, interpolated between. */
function percentile(row, price) {
  const pts = [[row.p10, 10], [row.p25, 25], [row.median, 50], [row.p75, 75], [row.p90, 90]];
  if (price <= pts[0][0]) return 9;
  if (price >= pts[4][0]) return 91;
  for (let i = 0; i < pts.length - 1; i++) {
    const [v1, p1] = pts[i], [v2, p2] = pts[i + 1];
    if (price <= v2) return p1 + (price - v1) / (v2 - v1) * (p2 - p1);
  }
  return 50;
}

function judge() {
  const v = $("verdict");
  const price = parseFloat($("price-in").value);
  if (!current || !price) { v.hidden = true; return; }
  v.hidden = false;
  const pct = percentile(current, price);
  const cheaper = Math.round(100 - pct);
  if (pct <= 9) {
    v.textContent = `Below almost every comparable listing — genuinely cheap, or the photos are hiding something.`;
    v.className = "verdict good";
  } else if (pct <= 35) {
    v.textContent = `Good price — cheaper than about ${cheaper}% of these.`;
    v.className = "verdict good";
  } else if (pct <= 65) {
    v.textContent = `Typical — right in the middle of this market.`;
    v.className = "verdict mid";
  } else if (pct <= 90) {
    v.textContent = `High — about ${Math.round(pct)}% of these cost less.`;
    v.className = "verdict high";
  } else {
    v.textContent = `Above nearly all comparable listings. Someone's feeling optimistic.`;
    v.className = "verdict high";
  }
}

familySel.onchange = renderDash;
$("price-in").oninput = () => { histChart($("hist"), current, parseFloat($("price-in").value) || null); judge(); };

/* ---------- deal feed ---------- */
function dealCard(d) {
  const el = document.createElement("div");
  el.className = "deal";
  const img = d.photo ? `<img src="${d.photo}" alt="" loading="lazy">` : `<img alt="">`;
  const days = d.days_listed == null ? ""
    : d.days_listed <= 1 ? " · listed today"
    : ` · listed ${d.days_listed} days ago`;
  el.innerHTML = `
    ${img}
    <div class="body">
      <a class="title" href="${d.url}" target="_blank" rel="noopener">${d.title}</a>
      <div class="meta">${d.bin} · ${d.comps.toLocaleString()} comparable listings${days}</div>
    </div>
    <div class="money">
      <div class="price">${money(d.price)}</div>
      <div class="typical">typical ${money(d.median)}</div>
      <div class="badge">${Math.round(d.discount * 100)}% below</div>
    </div>`;
  return el;
}

function renderDeals() {
  const q = $("deal-search").value.trim().toLowerCase();
  const sort = $("deal-sort").value;
  let list = DEALS.slice();
  if (q) list = list.filter(d => (d.title + " " + d.bin).toLowerCase().includes(q));
  if (sort === "cheap") list.sort((a, b) => a.price - b.price);
  if (sort === "fresh") list.sort((a, b) => (a.days_listed ?? 9e9) - (b.days_listed ?? 9e9));
  const box = $("deal-list");
  box.innerHTML = "";
  list.forEach(d => box.appendChild(dealCard(d)));
  if (!list.length) box.innerHTML = `<p class="context">Nothing matches that filter.</p>`;
}
$("deal-search").oninput = renderDeals;
$("deal-sort").onchange = renderDeals;

/* ---------- boot ---------- */
$("meta-line").textContent =
  `${META.guitars.toLocaleString()} used guitars for sale on Reverb, priced against ` +
  `their own kind · ${META.generated}`;
initFamilies();
renderDeals();

/* Fret Check — reads window.MARKET / DEALS / META (from data/data.js).
   No frameworks, no network calls: everything is precomputed. */

const $ = (id) => document.getElementById(id);
const money = (n) => "$" + Math.round(n).toLocaleString("en-US");

/* ---------- tabs ---------- */
function showTab(which) {
  $("panel-check").hidden = which !== "check";
  $("panel-deals").hidden = which !== "deals";
  $("tab-check").classList.toggle("active", which === "check");
  $("tab-deals").classList.toggle("active", which === "deals");
}
$("tab-check").onclick = () => showTab("check");
$("tab-deals").onclick = () => showTab("deals");

/* ---------- price check ---------- */
const familySel = $("family"), eraSel = $("era"), condSel = $("cond");

function rowsFor(family) { return MARKET[family] || []; }

function fillSelect(sel, values, anyLabel) {
  sel.innerHTML = "";
  const any = document.createElement("option");
  any.value = ""; any.textContent = anyLabel;
  sel.appendChild(any);
  for (const v of values) {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    sel.appendChild(o);
  }
}

function initFamilies() {
  const names = Object.keys(MARKET).sort();
  familySel.innerHTML = "";
  for (const name of names) {
    const o = document.createElement("option");
    o.value = name; o.textContent = name;
    familySel.appendChild(o);
  }
  familySel.value = names.includes("Fender Stratocaster (American)")
    ? "Fender Stratocaster (American)" : names[0];
  onFamily();
}

function onFamily() {
  const rows = rowsFor(familySel.value);
  const eras = [...new Set(rows.map(r => r.era).filter(Boolean))].sort();
  const conds = [...new Set(rows.map(r => r.cond).filter(Boolean))]
    .sort((a, b) => ["Excellent", "Good", "Rough"].indexOf(a) - ["Excellent", "Good", "Rough"].indexOf(b));
  fillSelect(eraSel, eras, "any era");
  fillSelect(condSel, conds, "any condition");
  render();
}

/* Same fallback order the scoring engine uses: most specific group with
   enough guitars wins. Returns [row, wasFallback]. */
function pickRow(family, era, cond) {
  const rows = rowsFor(family);
  const find = (e, c) => rows.find(r => r.era === e && r.cond === c);
  const want = find(era || null, cond || null);
  if (want) return [want, false];
  return [find(null, cond || null) || find(era || null, null) || find(null, null), true];
}

function render() {
  const family = familySel.value;
  const era = eraSel.value || null, cond = condSel.value || null;
  const [row, fell] = pickRow(family, era, cond);
  if (!row) { $("range-card").hidden = true; return; }
  $("range-card").hidden = false;

  const label = [family, row.era, row.cond].filter(Boolean).join(" · ");
  $("range-context").textContent =
    `${label} — ${row.n.toLocaleString()} listings on Reverb right now` +
    (fell ? " (closest group with enough listings to compare honestly)" : "");
  $("range-median").textContent = money(row.median);
  $("lab-p10").textContent = money(row.p10);
  $("lab-p90").textContent = money(row.p90);

  // geometry: linear scale from a hair below p10 to a hair above p90
  const lo = row.p10 * 0.94, hi = row.p90 * 1.06;
  const pos = (v) => Math.min(100, Math.max(0, (v - lo) / (hi - lo) * 100));
  $("band").style.left = pos(row.p25) + "%";
  $("band").style.width = (pos(row.p75) - pos(row.p25)) + "%";
  $("tick-median").style.left = pos(row.median) + "%";

  currentRow = row;
  judge();  // re-judge any typed price against the new group
}

let currentRow = null;

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
  if (!currentRow || !price) { v.hidden = true; return; }
  v.hidden = false;

  const marker = $("marker-you");
  const lo = currentRow.p10 * 0.94, hi = currentRow.p90 * 1.06;
  marker.hidden = false;
  marker.style.left = Math.min(100, Math.max(0, (price - lo) / (hi - lo) * 100)) + "%";

  const pct = percentile(currentRow, price);
  const cheaper = Math.round(100 - pct);
  if (pct <= 9) {
    v.textContent = `${money(price)} is below almost every comparable listing (cheaper than ~90%+). ` +
      `Genuinely cheap — or there's something the photos aren't saying. Read twice.`;
    v.className = "verdict good";
  } else if (pct <= 35) {
    v.textContent = `Good price — cheaper than about ${cheaper}% of comparable listings.`;
    v.className = "verdict good";
  } else if (pct <= 65) {
    v.textContent = `Typical price — right in the middle of the market (cheaper than about ${cheaper}% of comps).`;
    v.className = "verdict mid";
  } else if (pct <= 90) {
    v.textContent = `On the high side — about ${Math.round(pct)}% of comparable listings cost less.`;
    v.className = "verdict high";
  } else {
    v.textContent = `${money(price)} is above nearly all comparable listings. Someone's feeling optimistic.`;
    v.className = "verdict high";
  }
}

familySel.onchange = onFamily;
eraSel.onchange = render;
condSel.onchange = render;
$("price-in").oninput = judge;

/* ---------- deal feed ---------- */
function dealCard(d) {
  const el = document.createElement("div");
  el.className = "deal";
  const img = d.photo
    ? `<img src="${d.photo}" alt="" loading="lazy">`
    : `<img alt="">`;
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
  `${META.guitars.toLocaleString()} used guitars on Reverb, compared within ` +
  `${META.groups.toLocaleString()} groups of like-for-like listings · ${META.generated}`;
initFamilies();
renderDeals();

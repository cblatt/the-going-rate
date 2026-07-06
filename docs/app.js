/* The Going Rate — reads window.FAMILIES / DEALS / META (from data/data.js).
   No frameworks, no network calls: everything is precomputed. */

const $ = (id) => document.getElementById(id);
const money = (n) => "$" + Math.round(n).toLocaleString("en-US");
const NS = "http://www.w3.org/2000/svg";

/* ---------- tabs ---------- */
function showTab(which) {
  for (const t of ["dash", "insights", "deals", "data", "story"]) {
    $("panel-" + t).hidden = t !== which;
    $("tab-" + t).classList.toggle("active", t === which);
  }
}
$("tab-dash").onclick = () => showTab("dash");
$("tab-deals").onclick = () => showTab("deals");
$("tab-insights").onclick = () => showTab("insights");
$("tab-data").onclick = () => { showTab("data"); loadListings(); };
$("tab-story").onclick = () => showTab("story");

/* ---------- tiny SVG helpers (single hue, thin marks, direct labels) ---------- */
function svgEl(tag, attrs) {
  const el = document.createElementNS(NS, tag);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

/* Vertical bars with a $ label above each bar and a small n below —
   for the ≤8-bar era and condition charts. */
function barChart(mount, items, valueKey, labelKey, fmt = money) {
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
      `${d[labelKey]} — ${fmt(d[valueKey])} (${d.n.toLocaleString()} listings)`;
    svg.appendChild(bar);
    const val = svgEl("text", { x: x + barW / 2, y: y - 7, class: "t-val", "text-anchor": "middle" });
    val.textContent = fmt(d[valueKey]);
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
  const bars = [];
  counts.forEach((c, i) => {
    const h = max ? (c / max) * (H - top - bottom) : 0;
    const bar = svgEl("rect", {
      x: i * bw + 1, y: H - bottom - h, width: bw - 2, height: h, rx: 2, class: "bar-soft",
    });
    bars.push(bar);
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
  for (const f of [0.25, 0.5, 0.75]) {
    const t = svgEl("text", { x: W * f, y: H - 6, class: "t-n", "text-anchor": "middle" });
    t.textContent = money(lo + f * (hi - lo));
    svg.appendChild(t);
  }

  // Immediate hover: the price band + count under the cursor. (The native
  // <title> tooltip was there before but its delay made it undiscoverable.)
  const tip = document.createElement("div");
  tip.className = "charttip";
  tip.hidden = true;
  mount.appendChild(tip);
  let hl = -1;
  svg.addEventListener("mousemove", (ev) => {
    const r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(counts.length - 1,
      Math.floor((ev.clientX - r.left) / r.width * counts.length)));
    if (hl !== i) {
      if (hl >= 0) bars[hl].classList.remove("hl");
      bars[i].classList.add("hl");
      hl = i;
    }
    const b0 = lo + (i / counts.length) * (hi - lo);
    const b1 = lo + ((i + 1) / counts.length) * (hi - lo);
    tip.textContent = `${money(b0)}–${money(b1)} · ` +
      `${counts[i].toLocaleString()} listing${counts[i] === 1 ? "" : "s"}`;
    tip.hidden = false;
    const box = mount.getBoundingClientRect();
    tip.style.left = Math.max(0, Math.min(ev.clientX - box.left + 14,
      box.width - tip.offsetWidth - 4)) + "px";
    tip.style.top = (ev.clientY - box.top - 36) + "px";
  });
  svg.addEventListener("mouseleave", () => {
    tip.hidden = true;
    if (hl >= 0) bars[hl].classList.remove("hl");
    hl = -1;
  });
  mount.appendChild(svg);
}

/* Two bars per item — a pale and a full one, both 0..1 shares with % labels.
   For the brand listings-vs-dollars chart. */
function dualBarChart(mount, items, aKey, bKey, labelKey) {
  mount.innerHTML = "";
  const W = 460, H = 190, top = 24, bottom = 22;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart" });
  const max = Math.max(...items.flatMap(d => [d[aKey], d[bKey]]));
  const slot = W / items.length;
  const barW = Math.min(24, slot * 0.3);
  const pctLab = (v) => Math.round(v * 100) + "%";
  items.forEach((d, i) => {
    const cx = slot * i + slot / 2;
    for (const [k, cls, x] of [[aKey, "bar-neutral", cx - barW - 2], [bKey, "bar", cx + 2]]) {
      const h = max ? (d[k] / max) * (H - top - bottom) : 0;
      const y = H - bottom - h;
      svg.appendChild(svgEl("rect", { x, y, width: barW, height: h, rx: 3, class: cls }));
      const t = svgEl("text", { x: x + barW / 2, y: y - 6, class: "t-n", "text-anchor": "middle" });
      t.textContent = pctLab(d[k]);
      svg.appendChild(t);
    }
    const lab = svgEl("text", { x: cx, y: H - bottom + 15, class: "t-lab", "text-anchor": "middle" });
    lab.textContent = d[labelKey];
    svg.appendChild(lab);
  });
  svg.appendChild(svgEl("line", { x1: 0, x2: W, y1: H - bottom, y2: H - bottom, class: "baseline" }));
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

function priceIn() {
  const v = parseFloat($("price-in").value);
  return v > 0 ? v : null;
}

function renderDash() {
  const fam = FAMILIES[familySel.value];
  current = fam;
  renderHero();
  histChart($("hist"), fam, priceIn());

  $("card-era").hidden = fam.by_era.length < 2;
  if (fam.by_era.length >= 2) barChart($("era-chart"), fam.by_era, "median", "era");
  $("card-cond").hidden = fam.by_cond.length < 2;
  if (fam.by_cond.length >= 2) barChart($("cond-chart"), fam.by_cond, "median", "cond");

  renderCallouts(fam);
  renderFamDeals(fam);
}

/* The check itself: no price = the market's answer, a price = the verdict. */
function renderHero() {
  const fam = current;
  const price = priceIn();
  const a = $("hero-answer");
  if (!price) {
    a.className = "hero-answer";
    a.textContent = `Typical asking price: ${money(fam.median)}`;
  } else {
    const pct = percentile(fam, price);
    const cheaper = Math.round(100 - pct);
    if (pct <= 9) {
      a.textContent = `${money(price)} is below almost every comparable listing — genuinely cheap, or the photos are hiding something.`;
      a.className = "hero-answer good";
    } else if (pct <= 35) {
      a.textContent = `${money(price)} is a good price — cheaper than about ${cheaper}% of these.`;
      a.className = "hero-answer good";
    } else if (pct <= 65) {
      a.textContent = `${money(price)} is typical — right in the middle of this market.`;
      a.className = "hero-answer mid";
    } else if (pct <= 90) {
      a.textContent = `${money(price)} is high — about ${Math.round(pct)}% of these cost less.`;
      a.className = "hero-answer high";
    } else {
      a.textContent = `${money(price)} is above nearly all comparable listings. Someone's feeling optimistic.`;
      a.className = "hero-answer high";
    }
  }
  $("hero-caption").textContent =
    `middle half ${money(fam.p25)}–${money(fam.p75)} · ${fam.n.toLocaleString()} for sale right now · ` +
    `#${fam.rank} most-listed guitar on Reverb`;
}

/* One-line insights about this family, next to the charts they explain. */
function renderCallouts(fam) {
  const items = [];
  if (fam.days_median != null) {
    const m = META.market_days_median;
    items.push(fam.days_median <= m
      ? `Sells in a median <strong>${fam.days_median} days</strong>, faster than the market's ${m} — liquid, easy to resell.`
      : `Sits a median <strong>${fam.days_median} days</strong> vs the market's ${m} — sellers here wait; negotiate without shame.`);
  }
  const eras = {};
  fam.by_era.forEach(e => { eras[e.era] = e.median; });
  if (eras["1970s"] && eras["2010s"]) {
    const mult = eras["1970s"] / eras["2010s"];
    items.push(mult >= 1.3
      ? `A 1970s one typically asks <strong>${mult.toFixed(1)}×</strong> a 2010s one (${money(eras["1970s"])} vs ${money(eras["2010s"])}) — the old ones are the asset.`
      : `A 1970s one asks only ${mult.toFixed(1)}× a 2010s one — vintage buys you little here; buy modern and save.`);
  }
  const conds = {};
  fam.by_cond.forEach(c => { conds[c.cond] = c.median; });
  if (conds["Excellent"] && conds["Good"]) {
    const save = 1 - conds["Good"] / conds["Excellent"];
    items.push(save >= 0.08
      ? `“Good” condition typically saves <strong>${Math.round(save * 100)}%</strong> vs “Excellent” (${money(conds["Good"])} vs ${money(conds["Excellent"])}) — the player's copy is the value buy.`
      : `Condition barely moves the price here (${money(conds["Good"])} Good vs ${money(conds["Excellent"])} Excellent) — might as well get the clean one.`);
  }
  for (const r of fam.regions || []) {
    const pct = Math.round(r.gap * 100);
    items.push(pct >= 0
      ? `${r.region} sellers typically ask <strong>+${pct}%</strong> vs US sellers (${money(r.abroad)} vs ${money(r.us)}) — buy domestic.`
      : `${r.region} sellers typically ask <strong>${pct}%</strong> vs US sellers (${money(r.abroad)} vs ${money(r.us)}) — imports add shipping and duty, but a gap this size may cover it.`);
  }
  $("card-callouts").hidden = !items.length;
  const ul = $("callouts");
  ul.innerHTML = "";
  for (const html of items) {
    const li = document.createElement("li");
    li.innerHTML = html;
    ul.appendChild(li);
  }
}

const FAM_DEALS_SHOWN = 25;

function renderFamDeals(fam) {
  const box = $("fam-deals");
  const more = $("fam-deals-more");
  box.innerHTML = "";
  $("card-deals").scrollTop = 0;
  if (fam.deals.length) {
    $("fam-deal-note").textContent =
      `${fam.deal_count.toLocaleString()} listings in this group are priced below even its cheap ` +
      `quartile. Asking prices — read before you believe.`;
    const prefix = familySel.value;
    fam.deals.slice(0, FAM_DEALS_SHOWN).forEach(d => box.appendChild(dealCard(d, prefix)));
    more.textContent = `show all ${fam.deal_count.toLocaleString()} in this group ↓`;
    more.hidden = fam.deal_count <= FAM_DEALS_SHOWN;
    more.onclick = () => showAllFamDeals(prefix);
  } else {
    $("fam-deal-note").textContent =
      "No listing in this group currently clears our deal bar (meaningfully cheaper than even " +
      "the cheap end of its own market, no damage admitted in the title).";
    more.hidden = true;
  }
}

/* Full deal pools live in data/famdeals.js (~3 MB) — fetched once, on the
   first "show all" click, never on page load. */
let famDealsLoading = false;

function showAllFamDeals(name) {
  const more = $("fam-deals-more");
  const render = () => {
    const box = $("fam-deals");
    box.innerHTML = "";
    (window.FAM_DEALS[name] || []).forEach(d => box.appendChild(dealCard(d, name)));
    more.hidden = true;
  };
  if (window.FAM_DEALS) { render(); return; }
  if (famDealsLoading) return;
  famDealsLoading = true;
  more.textContent = "loading…";
  const s = document.createElement("script");
  s.src = "data/famdeals.js";
  s.onload = render;
  s.onerror = () => { more.textContent = "couldn't load the full list"; };
  document.body.appendChild(s);
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

familySel.onchange = renderDash;
$("price-in").oninput = () => { renderHero(); histChart($("hist"), current, priceIn()); };

/* ---------- deal feed ---------- */
function dealCard(d, binPrefix) {
  const el = document.createElement("div");
  el.className = "deal";
  const img = d.photo ? `<img src="${d.photo}" alt="" loading="lazy">` : `<img alt="">`;
  const days = d.days_listed == null ? ""
    : d.days_listed <= 1 ? " · listed today"
    : ` · listed ${d.days_listed} days ago`;
  // inside a family's own card the bin's family prefix is redundant — drop it
  let bin = d.bin;
  if (binPrefix && bin.startsWith(binPrefix)) bin = bin.slice(binPrefix.length).replace(/^ · /, "");
  const comps = `${d.comps.toLocaleString()} ${binPrefix ? "comps" : "comparable listings"}`;
  el.innerHTML = `
    ${img}
    <div class="body">
      <a class="title" href="${d.url}" target="_blank" rel="noopener">${d.title}</a>
      <div class="meta">${bin ? bin + " · " : ""}${comps}${days}</div>
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

/* ---------- market overview ---------- */
function row(cells, cls) {
  const tr = document.createElement("tr");
  if (cls) tr.className = cls;
  for (const c of cells) {
    const td = document.createElement("td");
    if (typeof c === "object") { td.innerHTML = c.html; if (c.cls) td.className = c.cls; }
    else td.textContent = c;
    tr.appendChild(td);
  }
  return tr;
}

function shortName(f) {
  return f.replace(/^(Fender|Gibson|Squier|Epiphone|PRS) /, "");
}

/* Family name cell with its example photo (links to a real listing). */
function famCell(name, display) {
  const f = FAMILIES[name];
  const img = f && f.photo
    ? `<a href="${f.example_url}" target="_blank" rel="noopener" title="${(f.example_title || "").replace(/"/g, "&quot;")}"><img class="thumb" src="${f.photo}" loading="lazy" alt=""></a>`
    : `<span class="thumb ph"></span>`;
  return { html: `<span class="famcell">${img}<span>${display || name}</span></span>` };
}

function renderInsights() {
  // hero stats: the market itself
  const mk = INSIGHTS.market;
  $("m-total").textContent = "$" + Math.round(mk.total_value / 1e6) + "M";
  $("m-median").textContent = money(mk.median);
  const lead = mk.brands.reduce((a, b) => (b.dollars > a.dollars ? b : a));
  $("m-brand").textContent = lead.brand;
  $("m-brand-label").textContent =
    `biggest brand by dollars — ${Math.round(lead.dollars * 100)}% of value on ` +
    `${Math.round(lead.units * 100)}% of listings`;

  // overpricing vs time-on-market
  barChart($("overpricing-chart"), INSIGHTS.overpricing, "days", "label", v => v + "d");

  // brand share: listings vs dollars
  dualBarChart($("brands-chart"),
    mk.brands.map(b => ({ ...b, brand: b.brand === "Prs" ? "PRS" : b.brand })),
    "units", "dollars", "brand");

  // seller vocabulary
  const wt = $("words-table");
  wt.appendChild(row(["title says…", "listings", "prices at", "days sitting"], "thead"));
  for (const w of INSIGHTS.words) {
    const pos = Math.round(w.pct * 100);
    wt.appendChild(row([w.word, w.n.toLocaleString(),
      { html: `<strong>${pos}th</strong> pctile`, cls: pos >= 55 ? "hot" : pos <= 45 ? "save" : "" },
      w.days == null ? "–" : w.days]));
  }

  // geographic gaps
  $("ins-regions").hidden = !INSIGHTS.regions.length;
  const rt = $("regions-table");
  rt.appendChild(row(["guitar", "region", "there", "US", "gap"], "thead"));
  for (const r of INSIGHTS.regions) {
    const pct = Math.round(r.gap * 100);
    rt.appendChild(row([famCell(r.family), r.region, money(r.abroad), money(r.us),
      { html: `<strong>${pct > 0 ? "+" : ""}${pct}%</strong>`, cls: pct < 0 ? "save" : "hot" }]));
  }

  const vt = $("vintage-table");
  vt.appendChild(row(["guitar", "1970s", "2010s", "multiple"], "thead"));
  for (const r of INSIGHTS.vintage) {
    vt.appendChild(row([famCell(r.family), money(r.old), money(r.new),
      { html: `<strong>${r.multiple}×</strong>` }]));
  }
  if (INSIGHTS.vintage_flat.length) {
    vt.appendChild(row([{ html: "<em>…and where vintage buys you nothing:</em>" }, "", "", ""], "divider"));
    for (const r of INSIGHTS.vintage_flat) {
      vt.appendChild(row([famCell(r.family), money(r.old), money(r.new), `${r.multiple}×`]));
    }
  }

  const ct = $("cond-table");
  ct.appendChild(row(["guitar", "Excellent", "Good", "you save"], "thead"));
  for (const r of INSIGHTS.condition) {
    ct.appendChild(row([famCell(r.family), money(r.exc), money(r.good),
      { html: `<strong>−${Math.round(r.save * 100)}%</strong>`, cls: "save" }]));
  }

  const lt = $("liq-table");
  lt.appendChild(row([{ html: "<em>fast movers</em>" }, "days", ""], "divider"));
  for (const r of INSIGHTS.liquidity.fast) {
    lt.appendChild(row([famCell(r.family), r.days, `${r.n.toLocaleString()} listed`]));
  }
  lt.appendChild(row([{ html: "<em>shelf sitters — negotiate</em>" }, "days", ""], "divider"));
  for (const r of INSIGHTS.liquidity.slow) {
    lt.appendChild(row([famCell(r.family), r.days, `${r.n.toLocaleString()} listed`]));
  }

  const dt = $("density-table");
  dt.appendChild(row(["guitar", "underpriced share", "count"], "thead"));
  for (const r of INSIGHTS.density) {
    dt.appendChild(row([famCell(r.family),
      { html: `<strong>${Math.round(r.share * 100)}%</strong>`, cls: "save" },
      `${r.deal_count} of ${r.n.toLocaleString()}`]));
  }
}

/* ---------- raw data tab (56k rows — loaded only when opened) ---------- */
let listingsLoading = false;

function loadListings() {
  if (window.LISTINGS) { renderData(); return; }
  if (listingsLoading) return;
  listingsLoading = true;
  $("data-count").textContent = "loading 56,000 rows…";
  const s = document.createElement("script");
  s.src = "data/listings.js";
  s.onload = renderData;
  s.onerror = () => { $("data-count").textContent = "couldn't load data/listings.js"; };
  document.body.appendChild(s);
}

function renderData() {
  const q = $("data-search").value.trim().toLowerCase();
  // columns: id, family, title, price, cond, era, days_listed, pct, discount
  let rows = window.LISTINGS;
  if (q) rows = rows.filter(r => (r[1] + " " + r[2]).toLowerCase().includes(q));
  const CAP = 300;
  $("data-count").textContent =
    `${rows.length.toLocaleString()} listings` +
    (rows.length > CAP ? ` — showing the first ${CAP} (narrow with the filter, or grab the CSV)` : "");
  const t = $("data-table");
  t.innerHTML = "";
  t.appendChild(row(["guitar", "listing", "price", "cond", "era", "days", "pctile"], "thead"));
  for (const r of rows.slice(0, CAP)) {
    t.appendChild(row([
      r[1],
      { html: `<a class="rawlink" href="https://reverb.com/item/${r[0]}" target="_blank" rel="noopener">${r[2]}</a>` },
      money(r[3]), r[4], r[5] || "–", r[6] ?? "–",
      Math.round(r[7] * 100) + "%",
    ]));
  }
}
$("data-search").oninput = () => { if (window.LISTINGS) renderData(); };

/* ---------- boot ---------- */
$("meta-line").innerHTML =
  `The blue book for used guitars — ${META.guitars.toLocaleString()} for sale ` +
  `on <a href="https://reverb.com" target="_blank" rel="noopener">Reverb</a> right now, ` +
  `each priced against its own kind`;
initFamilies();
renderInsights();
renderDeals();

// deep link: #deals / #insights / #data / #story opens that tab directly
const hash = location.hash.slice(1);
if (["deals", "insights", "data", "story"].includes(hash)) {
  showTab(hash);
  if (hash === "data") loadListings();
}

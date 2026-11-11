// Theme switch on every page; search, filters and sorting for the product table on the home page.
// The table is complete without this script. Filter values come from the row's data attributes, sort keys from the
// cells (data-v when present, else the text). Filters and sorting live in the address, so a view can be linked:
// #kind=browser&src=open&sort=core&dir=asc
(() => {
  // Light / dark: the button flips the current look and saves it; without a saved choice the system decides.
  const html = document.documentElement;
  const dark = () => html.dataset.theme ? html.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.querySelectorAll("[data-adb-theme]").forEach((b) => b.addEventListener("click", () => {
    html.dataset.theme = dark() ? "light" : "dark";
    try { localStorage.setItem("adb-theme", html.dataset.theme); } catch (e) { /* storage blocked */ }
  }));

  const root = document.querySelector(".adb-products");
  if (!root) return;
  const $ = (sel) => root.querySelector(sel);
  const list = $("[data-adb-list]");
  const empty = $(".adb-empty");  // shown when no row matches
  const count = $("[data-adb-count]");
  const reset = $("[data-adb-reset]");
  const q = $("[data-adb-q]");
  const filters = [...root.querySelectorAll("[data-adb-f]")]; // <select data-adb-f="st|kind|engine|src|entity|free|country">
  const sortButtons = [...root.querySelectorAll("[data-adb-sort]")];
  const MULTI = new Set(["kind", "engine"]); // row attributes that hold several space-separated values

  // Sort keys; "" (no value) always sorts last.
  const FLAG = /^[\u{1F1E6}-\u{1F1FF}]{2}\s*/u;
  const KIND = {
    text: (s) => s.toLowerCase(),
    country: (s) => s.replace(FLAG, ""),
    num: (s) => s,
  };
  const kinds = sortButtons.map((b) => KIND[b.dataset.adbSort] || KIND.text);
  const rows = [...list.querySelectorAll("tr[data-st]")].map((el) => {
    const keys = [...el.cells].map((td, i) => {
      const v = td.dataset.v !== undefined ? td.dataset.v : td.textContent.trim();
      return kinds[i] ? kinds[i](v) : v;
    });
    return { el, keys, name: keys[0], search: (el.dataset.q || "") + " " + keys[0] };
  });
  const sortIndex = (key) => sortButtons.findIndex((b) => b.dataset.adbKey === key);
  let sort = { key: "product", dir: "asc" };

  const match = (row, key, want) => {
    if (!want) return true;
    const have = row.el.dataset[key] || "";
    return MULTI.has(key) ? have.split(" ").includes(want) : have === want;
  };

  const readHash = () => {
    const p = new URLSearchParams(location.hash.slice(1));
    q.value = p.get("q") || "";
    filters.forEach((f) => {
      const v = p.get(f.dataset.adbF) || "";
      f.value = [...f.options].some((o) => o.value === v) ? v : "";
    });
    const key = p.get("sort");
    sort = sortIndex(key) >= 0 ? { key, dir: p.get("dir") === "desc" ? "desc" : "asc" } : { key: "product", dir: "asc" };
  };

  const writeHash = () => {
    const p = new URLSearchParams();
    if (q.value.trim()) p.set("q", q.value.trim());
    filters.forEach((f) => f.value && p.set(f.dataset.adbF, f.value));
    if (sort.key !== "product" || sort.dir !== "asc") { p.set("sort", sort.key); p.set("dir", sort.dir); }
    const hash = p.toString();
    history.replaceState(null, "", hash ? "#" + hash : location.pathname + location.search);
  };

  const apply = () => {
    const terms = q.value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const row of rows) {
      const ok = filters.every((f) => match(row, f.dataset.adbF, f.value)) && terms.every((t) => row.search.includes(t));
      row.el.hidden = !ok;
      if (ok) shown++;
    }
    empty.hidden = shown > 0;
    count.textContent = shown;
    reset.hidden = !(q.value.trim() || filters.some((f) => f.value));
    sortButtons.forEach((b) => (b.dataset.adbKey === sort.key ? b.setAttribute("data-dir", sort.dir) : b.removeAttribute("data-dir")));
  };

  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  const order = () => {
    const i = sortIndex(sort.key);
    const sign = sort.dir === "desc" ? -1 : 1;
    rows.sort((a, b) => {
      const x = a.keys[i], y = b.keys[i];
      if (!x !== !y) return x ? -1 : 1;
      return collator.compare(x, y) * sign || collator.compare(a.name, b.name);
    });
    const frag = document.createDocumentFragment();
    rows.forEach((r) => frag.appendChild(r.el));
    list.appendChild(frag);
  };

  const update = () => { apply(); writeHash(); };

  sortButtons.forEach((b) => b.addEventListener("click", () => {
    const key = b.dataset.adbKey;
    sort = { key, dir: sort.key === key && sort.dir === "asc" ? "desc" : "asc" };
    order();
    update();
  }));
  filters.forEach((f) => f.addEventListener("change", update));
  let timer;
  q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(update, 150); });
  reset.addEventListener("click", () => { q.value = ""; filters.forEach((f) => (f.value = "")); update(); });

  // Links in the summary line set one filter: <a data-adb-set="src=open">
  document.querySelectorAll("[data-adb-set]").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    const [key, value] = a.dataset.adbSet.split("=");
    q.value = "";
    filters.forEach((f) => (f.value = f.dataset.adbF === key ? value : ""));
    update();
    root.scrollIntoView({ behavior: "smooth", block: "start" });
  }));

  // "/" focuses the search box, Escape clears it.
  document.addEventListener("keydown", (e) => {
    const el = document.activeElement;
    const typing = el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
    if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) { e.preventDefault(); q.focus(); }
  });
  q.addEventListener("keydown", (e) => { if (e.key === "Escape" && q.value) { q.value = ""; update(); } });
  window.addEventListener("hashchange", () => { readHash(); order(); apply(); });

  readHash();
  if (sort.key !== "product" || sort.dir !== "asc") order();
  apply();
})();

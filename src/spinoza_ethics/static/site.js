
(function () {
  const data = window.SPINOZA_SITE_DATA || { anchors: {}, backlinks: {}, records: [] };
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function samePathTarget(href) {
    try {
      const url = new URL(href, location.href);
      return url.origin === location.origin ? url.pathname + url.hash : null;
    } catch {
      return null;
    }
  }

  function snippetFor(target) {
    const id = target && target.split("#")[1];
    const el = id ? document.getElementById(id) : null;
    if (!el) return null;
    return el.textContent.replace(/\s+/g, " ").trim().slice(0, 520);
  }

  function renderCard(target, linkText) {
    const panel = $("#selection-card");
    if (!panel || !target) return;
    const rec = data.anchors[target] || {};
    const hereSnippet = snippetFor(target);
    const backs = data.backlinks[target] || [];
    const targetLink = `<a href="${target}">${escapeHtml(rec.label || linkText || target)}</a>`;
    const backItems = backs.slice(0, 12).map(b => `<li><a href="${b.from || '/' + b.file}">${escapeHtml(b.label || b.doc)}</a> <span>${escapeHtml(b.doc || "")}</span></li>`).join("");
    panel.innerHTML = `
      <div class="preview-card">
        <h3>${targetLink}</h3>
        <p>${escapeHtml(rec.doc || "Linked target")}</p>
        ${hereSnippet ? `<p>${escapeHtml(hereSnippet)}</p>` : ""}
        <p><button type="button" data-copy="${target}">Copy target link</button></p>
      </div>
      <div class="preview-card">
        <h3>Referenced by ${backs.length}</h3>
        ${backs.length ? `<ul>${backItems}</ul>` : `<p>No recorded backlinks in this build.</p>`}
      </div>
    `;
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[ch]));
  }

  document.addEventListener("click", event => {
    const copy = event.target.closest("[data-copy], .copy-anchor");
    if (copy) {
      const target = copy.dataset.copy || (location.pathname + location.hash);
      navigator.clipboard && navigator.clipboard.writeText(location.origin + target);
      copy.textContent = "Copied";
      setTimeout(() => { copy.textContent = copy.classList.contains("copy-anchor") ? "Copy link" : "Copy target link"; }, 1200);
      return;
    }
    const a = event.target.closest("a[href]");
    if (!a) return;
    const target = samePathTarget(a.getAttribute("href"));
    if (target && (a.classList.contains("reference-link") || data.backlinks[target])) {
      renderCard(target, a.textContent.trim());
    }
  });

  document.addEventListener("mouseover", event => {
    const a = event.target.closest("a.reference-link[href]");
    if (!a) return;
    const target = samePathTarget(a.getAttribute("href"));
    if (target) renderCard(target, a.textContent.trim());
  });

  const toggle = $("#toggle-apparatus");
  if (toggle) {
    toggle.addEventListener("click", () => $("#apparatus-panel")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  const search = $("#site-search");
  if (search) {
    search.addEventListener("input", () => {
      $$(".search-hit").forEach(el => el.classList.remove("search-hit"));
      const q = search.value.trim().toLowerCase();
      if (!q) return;
      const hit = $$("p, h1, h2, h3, h4, li").find(el => el.textContent.toLowerCase().includes(q));
      if (hit) {
        hit.classList.add("search-hit");
        hit.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  const list = $("#apparatus-list");
  if (list) {
    const entries = Object.entries(data.backlinks)
      .filter(([, refs]) => refs.length)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 500);
    list.innerHTML = entries.map(([target, refs]) => {
      const rec = data.anchors[target] || {};
      const refsHtml = refs.slice(0, 10).map(r => `<li><a href="${r.from || '/' + r.file}">${escapeHtml(r.label || r.doc)}</a> <span>${escapeHtml(r.doc || "")}</span></li>`).join("");
      return `<article class="apparatus-entry"><h2><a href="${target}">${escapeHtml(rec.label || target)}</a></h2><p>${escapeHtml(rec.doc || "")} · ${refs.length} incoming reference${refs.length === 1 ? "" : "s"}</p><ul>${refsHtml}</ul></article>`;
    }).join("");
  }

  if (location.hash) {
    const target = location.pathname + location.hash;
    if (data.backlinks[target]) renderCard(target, "");
  }
})();

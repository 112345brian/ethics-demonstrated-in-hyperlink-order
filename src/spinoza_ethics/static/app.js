





(function () {
  const data = window.SPINOZA_SITE_DATA || { anchors: {}, backlinks: {}, outgoing: {}, search: [], records: [], coreFiles: [], ethicsNodes: [], nodeForAnchor: {} };
  // Every value in `data` (and every value derived from it) is a canonical,
  // *unprefixed* site-root path -- the deploy base path is added only when a
  // path is written into a real href/fetch/pushState, and stripped back off
  // when a real browser path is used to look something up in `data`.
  const BASE = window.SPINOZA_BASE_PATH || "";
  function withBase(path) {
    if (!BASE || !path || path.charAt(0) !== "/") return path;
    return path === BASE || path.startsWith(BASE + "/") ? path : BASE + path;
  }
  function stripBase(path) {
    if (!BASE || !path) return path;
    if (path === BASE) return "/";
    return path.startsWith(BASE + "/") ? path.slice(BASE.length) : path;
  }
  const state = {
    currentPath: "/text/part0029_split_001.html",
    currentHash: "",
    selectedTarget: "",
    activeTab: "target",
    lastSearch: "",
    contextPinned: false,
    columns: localStorage.getItem("spinoza:columns") === "1",
    marginalia: localStorage.getItem("spinoza:marginalia") !== "0",
    marginaliaMode: localStorage.getItem("spinoza:marginaliaMode") || "proof",
  };
  const docCache = new Map();
  let hoverTimer = 0;
  let hoverCard = null;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    }[ch]));
  }

  function normalizeHref(href, basePath = location.pathname) {
    try {
      const url = new URL(href, location.origin + basePath);
      if (url.origin !== location.origin) return href;
      return url.pathname + url.hash;
    } catch {
      return href || "";
    }
  }

  function splitTarget(target) {
    const [path, hash = ""] = target.split("#");
    return { path: path || state.currentPath, hash: hash ? "#" + hash : "" };
  }

  async function fetchDoc(path) {
    if (docCache.has(path)) return docCache.get(path);
    const response = await fetch(path, { cache: "force-cache" });
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    docCache.set(path, doc);
    return doc;
  }

  async function loadDocument(target, push = true) {
    const parts = splitTarget(target);
    state.currentPath = parts.path || state.currentPath;
    state.currentHash = parts.hash || "";
    const reader = $("#app-document");
    if (!reader) return;
    reader.innerHTML = '<p class="app-loading">Loading source...</p>';
    const doc = await fetchDoc(withBase(state.currentPath));
    const article = doc.querySelector(".source-text") || doc.body;
    reader.innerHTML = article.innerHTML;
    reader.querySelectorAll("script, .topbar, .apparatus-panel, .doc-tools").forEach(el => el.remove());
    reader.querySelectorAll("a[href]").forEach(a => {
      // Resolve against the real (base-prefixed) page URL: a bare-fragment
      // href like "#cite-ID3" must resolve to a fetchable, prefixed path.
      a.href = normalizeHref(a.getAttribute("href"), withBase(state.currentPath));
      if (a.classList.contains("cite") || a.classList.contains("gloss")) {
        a.classList.add("reference-link");
      }
    });
    buildMarginalia(reader);
    applyReaderModes();
    if (push) {
      const appUrl = withBase("/index.html") + "?doc=" + encodeURIComponent(state.currentPath + state.currentHash);
      history.pushState({ target: state.currentPath + state.currentHash }, "", appUrl);
      localStorage.setItem("spinoza:lastTarget", state.currentPath + state.currentHash);
    }
    requestAnimationFrame(() => {
      if (state.currentHash) {
        const id = CSS.escape(state.currentHash.slice(1));
        const el = reader.querySelector("#" + id);
        if (el) el.scrollIntoView({ block: "start" });
      }
      selectTarget(state.currentPath + state.currentHash);
    });
  }

  async function targetSnippet(target) {
    const parts = splitTarget(target);
    const doc = await fetchDoc(parts.path);
    const id = parts.hash ? parts.hash.slice(1) : "";
    let el = id ? doc.getElementById(id) : doc.querySelector(".source-text");
    if (el && el.tagName === "A" && !el.textContent.trim()) el = el.parentElement || el;
    if (!el) return "";
    let text = el.textContent.replace(/\s+/g, " ").trim();
    if (text.length < 80 && el.parentElement) {
      text = el.parentElement.textContent.replace(/\s+/g, " ").trim();
    }
    return text.slice(0, 900);
  }

  function selectTarget(target) {
    state.selectedTarget = target || state.currentPath + state.currentHash;
    renderBreadcrumbs(state.selectedTarget);
    renderContextRail(state.selectedTarget);
    renderPanel();
  }

  function currentSectionHref() {
    const visible = $$("#app-document [id]").find(el => {
      const rect = el.getBoundingClientRect();
      return rect.top >= 70 && rect.top < window.innerHeight * 0.58;
    });
    return state.currentPath + (visible ? "#" + visible.id : state.currentHash);
  }

  function linkList(items, emptyText) {
    if (!items || !items.length) return `<p>${escapeHtml(emptyText)}</p>`;
    const seen = new Set();
    const unique = [];
    for (const item of items) {
      const href = item.from || item.target || item.href || "#";
      const key = `${href}|${item.label || item.text || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(item);
    }
    return `<ul class="panel-list">${unique.slice(0, 80).map(item => {
      const href = item.from || item.target || item.href || "#";
      const label = item.label || item.text || href;
      return `<li><a href="${withBase(href)}" data-app-link>${escapeHtml(label)}</a><span class="result-doc">${escapeHtml(item.doc || "")}</span></li>`;
    }).join("")}</ul>`;
  }

  function cleanPanelLabel(text) {
    return String(text || "").replace(/\[\d+\]\s*/g, "").replace(/\s+/g, " ").trim();
  }

  function isGlossaryBacklink(item) {
    return /\bgloss\b/.test(item?.classes || "");
  }

  function sourceSummaryItem(item) {
    const source = item.from || item.href || "#";
    const canonical = canonicalTarget(source);
    const node = data.ethicsNodes.find(n => n.href === canonical);
    const anchor = data.anchors[source] || data.anchors[canonical] || {};
    if (node) {
      return {
        href: node.href,
        text: `${node.code} · ${node.type}`,
        doc: cleanPanelLabel(node.label || anchor.label || item.doc || ""),
        structural: true,
      };
    }
    return {
      href: source,
      text: cleanPanelLabel(anchor.label || item.label || source),
      doc: documentLabel(item.file || anchor.file || source.split("#")[0]),
      structural: false,
    };
  }

  function groupedMentionList(items) {
    const groups = new Map();
    for (const item of items || []) {
      const summary = sourceSummaryItem(item);
      const group = groups.get(summary.href) || { ...summary, count: 0, labels: new Set() };
      group.count += 1;
      if (item.label) group.labels.add(cleanPanelLabel(item.label).toLowerCase());
      groups.set(summary.href, group);
    }
    return [...groups.values()].sort((a, b) => {
      if (a.structural !== b.structural) return a.structural ? -1 : 1;
      return b.count - a.count || a.text.localeCompare(b.text, undefined, { numeric: true });
    }).map(group => {
      const labels = [...group.labels].filter(Boolean).slice(0, 4).join(", ");
      const suffix = group.count > 1 ? ` · ${group.count} mentions` : " · 1 mention";
      return {
        href: group.href,
        text: group.text,
        doc: `${group.doc || ""}${labels ? ` · terms: ${labels}` : ""}${suffix}`,
      };
    });
  }

  function incomingPanelHtml(target, rec, incoming) {
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const targetNode = data.ethicsNodes.find(n => n.href === nodeTarget || n.href === target);
    const glossaryLinks = incoming.filter(isGlossaryBacklink);
    const formalLinks = incoming.filter(item => !isGlossaryBacklink(item));
    const glossaryHeavy = glossaryLinks.length >= 8 && glossaryLinks.length >= formalLinks.length;
    if (targetNode && !glossaryHeavy) {
      const structuralUses = relationItems(targetNode.href, "in").filter(item => data.ethicsNodes.some(n => n.href === item.href));
      return `<h2>Used By</h2><p>${escapeHtml(targetNode.code)} · ${escapeHtml(targetNode.type)}</p>${linkList(structuralUses, "No incoming structural references recorded for this node.")}`;
    }
    if (glossaryHeavy) {
      const formal = formalLinks.map(sourceSummaryItem);
      const mentions = groupedMentionList(glossaryLinks);
      const combined = formal.concat(mentions);
      return `
        <h2>Mentions</h2>
        <p>${escapeHtml(cleanPanelLabel(rec.label || target))}</p>
        <p class="panel-note">Collapsed ${glossaryLinks.length} inline glossary mention${glossaryLinks.length === 1 ? "" : "s"} into distinct source locations. Use Search when you need every raw occurrence.</p>
        ${linkList(combined, "No incoming references recorded for this exact anchor.")}
      `;
    }
    return `<h2>References To This</h2><p>${escapeHtml(cleanPanelLabel(rec.label || target))}</p>${linkList(groupedMentionList(incoming), "No incoming references recorded for this exact anchor.")}`;
  }

  function applyReaderModes() {
    document.body.classList.toggle("columns-on", state.columns);
    document.body.classList.toggle("marginalia-on", state.marginalia);
    const columnButton = $("#toggle-columns");
    const marginaliaButton = $("#toggle-marginalia");
    const marginaliaMode = $("#marginalia-mode");
    if (columnButton) columnButton.setAttribute("aria-pressed", state.columns ? "true" : "false");
    if (marginaliaButton) marginaliaButton.setAttribute("aria-pressed", state.marginalia ? "true" : "false");
    if (marginaliaMode) marginaliaMode.value = state.marginaliaMode;
  }

  function marginaliaKind(link, label) {
    if (link.classList.contains("gloss") || link.dataset.refKind === "gloss") return "";
    if (/^\d+[a-z]?$/i.test(label) || /fn|note/i.test(link.getAttribute("href") || "")) return "note";
    return "proof";
  }

  function buildMarginalia(reader) {
    reader.querySelectorAll(".margin-note").forEach(note => note.remove());
    for (const block of $$("p, li, blockquote", reader)) {
      const refs = [];
      const seen = new Set();
      for (const a of $$("a.reference-link[href], a.cite[href]", block)) {
        const label = a.textContent.replace(/\s+/g, " ").trim();
        const kind = marginaliaKind(a, label);
        if (!kind) continue;
        if (state.marginaliaMode === "proof" && kind !== "proof") continue;
        if (state.marginaliaMode === "notes" && kind !== "note") continue;
        const href = normalizeHref(a.getAttribute("href"), withBase(state.currentPath));
        if (seen.has(href)) continue;
        seen.add(href);
        refs.push({ href, label });
      }
      if (!refs.length) continue;
      const note = document.createElement("aside");
      note.className = "margin-note";
      note.innerHTML = refs.slice(0, 5).map(ref => `<a href="${ref.href}" data-app-link>${escapeHtml(ref.label || ref.href)}</a>`).join("");
      block.appendChild(note);
    }
  }

  function canonicalTarget(target) {
    if (!target) return "";
    if (data.nodeForAnchor[target]) return data.nodeForAnchor[target];
    const direct = data.ethicsNodes.find(n => n.href === target);
    if (direct) return direct.href;
    return target;
  }

  function ethicsNodeForTarget(target) {
    const canonical = canonicalTarget(target);
    return data.ethicsNodes.find(n => n.href === canonical) || nearestEthicsNodeFor(target);
  }

  function nodeSortKey(node) {
    const part = nodePartLabel(node).replace("Part ", "");
    const partOrder = { I: 1, II: 2, III: 3, IV: 4, V: 5 }[part] || 0;
    const kindOrder = { definition: 1, axiom: 2, proposition: 3, demonstration: 4, corollary: 5, scholium: 6 }[node.type] || 9;
    const number = Number((node.code.match(/\d+/) || [0])[0]);
    return [partOrder, number, kindOrder, node.code].join(".");
  }

  function orderedEthicsNodes() {
    return [...data.ethicsNodes].sort((a, b) => nodeSortKey(a).localeCompare(nodeSortKey(b), undefined, { numeric: true }));
  }

  function neighboringNodes(node) {
    if (!node) return { previous: null, next: null, siblings: [] };
    const peers = orderedEthicsNodes().filter(n => nodePartLabel(n) === nodePartLabel(node) && n.type === node.type);
    const index = peers.findIndex(n => n.href === node.href);
    return {
      previous: index > 0 ? peers[index - 1] : null,
      next: index >= 0 && index < peers.length - 1 ? peers[index + 1] : null,
      siblings: peers.slice(Math.max(0, index - 4), index).concat(peers.slice(index + 1, index + 5)),
    };
  }

  function relationItems(target, direction) {
    const canonical = canonicalTarget(target);
    const source = direction === "out" ? (data.outgoing[canonical] || data.outgoing[target] || []) : (data.backlinks[canonical] || data.backlinks[target] || []);
    const seen = new Set();
    return source.map(item => {
      const href = canonicalTarget(direction === "out" ? item.target : item.from);
      const node = data.ethicsNodes.find(n => n.href === href);
      return {
        href,
        text: node ? `${node.code} · ${node.type}` : (item.label || href),
        doc: node ? node.label : (item.doc || item.file || ""),
        label: item.label,
      };
    }).filter(item => {
      if (!item.href || seen.has(item.href)) return false;
      seen.add(item.href);
      return true;
    });
  }

  function compactNodeLink(node, rel) {
    if (!node) return "";
    return `<a class="trail-card ${rel || ""}" href="${nodePageHref(node)}"><span>${escapeHtml(rel || "")}</span><strong>${escapeHtml(node.code)}</strong></a>`;
  }

  function nodePageHref(node) {
    return node ? withBase(`/nodes/${encodeURIComponent(node.code)}.html`) : "#";
  }

  function normalizeNodeCode(raw) {
    const compact = String(raw || "").trim().toUpperCase().replace(/[\s._-]+/g, "");
    if (data.ethicsNodes.some(n => n.code === compact)) return compact;
    const match = compact.match(/^([1-5])([DAP])(\d+)$/);
    if (!match) return compact;
    const roman = { "1": "I", "2": "II", "3": "III", "4": "IV", "5": "V" }[match[1]];
    return `${roman}${match[2]}${match[3]}`;
  }

  function nodeByCode(raw) {
    const code = normalizeNodeCode(raw);
    return data.ethicsNodes.find(n => n.code === code) || null;
  }

  function nodePartLabel(node) {
    if (!node) return "";
    if (node.code.startsWith("IIP") || node.code.startsWith("IID") || node.code.startsWith("IIA")) return "Part II";
    if (node.code.startsWith("IIIP") || node.code.startsWith("IIID")) return "Part III";
    if (node.code.startsWith("IV")) return "Part IV";
    if (node.code.startsWith("V")) return "Part V";
    return "Part I";
  }

  function documentLabel(path) {
    const normalized = path.replace(/^\//, "");
    const rec = data.records.find(r => r.file === normalized);
    return rec?.title || path.split("/").pop();
  }

  function nearestEthicsNodeFor(target) {
    const exact = data.ethicsNodes.find(n => n.href === target);
    if (exact) return exact;
    const parts = splitTarget(target);
    const sameFile = data.ethicsNodes.filter(n => n.href.startsWith(parts.path + "#"));
    if (!sameFile.length) return null;
    const currentId = parts.hash.slice(1);
    const current = currentId ? $("#app-document #" + CSS.escape(currentId)) : null;
    if (!current) return sameFile[0] || null;
    let nearest = null;
    for (const el of $$("#app-document [id]")) {
      const match = sameFile.find(n => n.id === el.id);
      if (match) nearest = match;
      if (el === current) break;
    }
    return nearest || sameFile[0] || null;
  }

  function renderBreadcrumbs(target = state.selectedTarget || currentSectionHref()) {
    const mount = $("#wiki-breadcrumbs");
    if (!mount) return;
    const parts = splitTarget(target);
    const node = nearestEthicsNodeFor(target);
    const crumbs = [
      { label: "Ethics", href: "/text/part0029_split_001.html#ch6d" },
      node ? { label: nodePartLabel(node), href: node.href } : { label: documentLabel(parts.path), href: parts.path },
    ];
    if (node) {
      crumbs.push({ label: node.type, href: node.href });
      crumbs.push({ label: node.code, href: node.href, current: true });
    } else if (parts.hash) {
      crumbs.push({ label: parts.hash.slice(1), href: target, current: true });
    }
    mount.innerHTML = crumbs.map((crumb, index) => {
      const sep = index ? '<span class="crumb-sep">/</span>' : "";
      const cls = crumb.current ? ' class="crumb-current"' : "";
      return `${sep}<a${cls} href="${withBase(crumb.href)}" data-app-link>${escapeHtml(crumb.label)}</a>`;
    }).join("") + renderTrailStrip(node);
  }

  function renderTrailStrip(node) {
    if (!node) return "";
    const { previous, next } = neighboringNodes(node);
    return `<span class="crumb-spacer"></span><span class="crumb-trail">${compactNodeLink(previous, "Prev")}${compactNodeLink(node, "Current")}${compactNodeLink(next, "Next")}</span>`;
  }

  function nearestEthicsTarget(target) {
    if (data.nodeForAnchor[target]) return data.nodeForAnchor[target];
    if (data.anchors[target]?.id?.startsWith("cite-")) return target;
    const hash = target.split("#")[1];
    if (!hash) return target;
    const ids = $$("#app-document [id]");
    const current = $("#app-document #" + CSS.escape(hash));
    if (!current) return target;
    let best = null;
    for (const el of ids) {
      if (el === current || (el.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING)) {
        if (el.id && el.id.startsWith("cite-")) best = state.currentPath + "#" + el.id;
      }
    }
    return best || target;
  }

  function renderProofMap(target) {
    const panel = $("#panel-content");
    const nodeTarget = nearestEthicsTarget(target);
    const rec = data.anchors[nodeTarget] || data.anchors[target] || {};
    const outgoing = data.outgoing[nodeTarget] || data.outgoing[target] || [];
    const incoming = data.backlinks[nodeTarget] || data.backlinks[target] || [];
    const deps = outgoing.filter(o => o.target && data.ethicsNodes.some(n => n.href === o.target));
    const uses = incoming.filter(i => i.from && /part0029|part0030|part0031|part0032/.test(i.file || ""));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget);
    const { previous, next, siblings } = neighboringNodes(node);
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || rec.id || "Current node")}</h2>
      <p><span class="result-doc">${escapeHtml(node?.type || rec.doc || "Ethics structure")}</span></p>
      <p>${escapeHtml(rec.label || node?.label || target)}</p>
      <h3>Trail</h3>
      <div class="trail-row">${compactNodeLink(previous, "Previous")}${compactNodeLink(node, "Current")}${compactNodeLink(next, "Next")}</div>
      <h3>Uses</h3>
      ${linkList(deps, "No explicit linked dependencies recorded for this node.")}
      <h3>Used by</h3>
      ${linkList(uses, "No later linked uses recorded for this exact node.")}
      <h3>Siblings</h3>
      ${linkList(siblings.map(n => ({ href: n.href, text: `${n.code} · ${n.type}`, doc: n.label })), "No sibling nodes available.")}
    `;
  }

  function renderRelations(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const uses = relationItems(nodeTarget, "out").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const usedBy = relationItems(nodeTarget, "in").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const { previous, next, siblings } = neighboringNodes(node);
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Relations")}</h2>
      <p><span class="result-doc">${escapeHtml(node ? `${nodePartLabel(node)} · ${node.type}` : target)}</span></p>
      <p>${escapeHtml(node?.label || data.anchors[target]?.label || target)}</p>
      <h3>Trail</h3>
      <div class="trail-row">${compactNodeLink(previous, "Previous")}${compactNodeLink(node, "Current")}${compactNodeLink(next, "Next")}</div>
      <h3>Uses</h3>
      ${linkList(uses, "No structural parents are recorded for this node.")}
      <h3>Used By</h3>
      ${linkList(usedBy, "No structural children are recorded for this node.")}
      <h3>Siblings</h3>
      ${linkList(siblings.map(n => ({ href: n.href, text: `${n.code} · ${n.type}`, doc: n.label })), "No sibling sequence nodes available.")}
    `;
  }

  function renderContextRail(target) {
    const mount = $("#context-rail");
    if (!mount) return;
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const uses = relationItems(nodeTarget, "out").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const usedBy = relationItems(nodeTarget, "in").filter(i => data.ethicsNodes.some(n => n.href === i.href));
    const { previous, next } = neighboringNodes(node);
    mount.innerHTML = `
      <button type="button" class="rail-handle" data-rail-tab="relations" aria-label="Open relations">Relations</button>
      <div class="rail-body">
        <strong>${escapeHtml(node?.code || "Ethics")}</strong>
        <span>${escapeHtml(node ? `${nodePartLabel(node)} · ${node.type}` : "Current target")}</span>
        <div class="rail-counts">
          <button type="button" data-rail-tab="relations">${uses.length} uses</button>
          <button type="button" data-rail-tab="relations">${usedBy.length} used by</button>
        </div>
        <div class="rail-jump">${compactNodeLink(previous, "Prev")}${compactNodeLink(next, "Next")}</div>
      </div>
    `;
  }

  function ethicsOnly(items) {
    return items.filter(item => data.ethicsNodes.some(n => n.href === item.href));
  }

  function transitiveItems(startTarget, direction, maxDepth = 8) {
    const start = canonicalTarget(nearestEthicsTarget(startTarget));
    const queue = [{ href: start, depth: 0, path: [] }];
    const seen = new Set([start]);
    const rows = [];
    while (queue.length) {
      const current = queue.shift();
      if (current.depth >= maxDepth) continue;
      for (const item of ethicsOnly(relationItems(current.href, direction))) {
        if (seen.has(item.href)) continue;
        seen.add(item.href);
        const node = data.ethicsNodes.find(n => n.href === item.href);
        const path = current.path.concat(node?.code || item.text || item.href);
        rows.push({ ...item, depth: current.depth + 1, path });
        queue.push({ href: item.href, depth: current.depth + 1, path });
      }
    }
    return rows;
  }

  function chainList(items, emptyText, rootCode, direction) {
    if (!items.length) return `<p>${escapeHtml(emptyText)}</p>`;
    const arrow = direction === "out" ? "←" : "→";
    const relation = direction === "out" ? "upstream" : "downstream";
    return `<ol class="chain-list">${items.slice(0, 120).map(item => `
      <li style="--depth:${Math.min(item.depth, 8)}">
        <a href="${withBase(item.href)}" data-app-link>${escapeHtml((item.text || item.href).split(" · ")[0])}</a>
        <span class="result-doc">${escapeHtml(`${item.depth} step${item.depth === 1 ? "" : "s"} ${relation}${item.path?.length ? " · " + [rootCode || "current"].concat(item.path.map(part => String(part).split(" · ")[0])).join(" " + arrow + " ") : ""}`)}</span>
      </li>
    `).join("")}</ol>`;
  }

  function renderChains(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const ancestors = transitiveItems(nodeTarget, "out");
    const descendants = transitiveItems(nodeTarget, "in");
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Dependency Chains")}</h2>
      <p><span class="result-doc">${ancestors.length} transitive ancestor${ancestors.length === 1 ? "" : "s"} · ${descendants.length} transitive descendant${descendants.length === 1 ? "" : "s"}</span></p>
      <h3>All Ancestors</h3>
      ${chainList(ancestors, "No transitive ancestors recorded.", node?.code || "", "out")}
      <h3>All Descendants</h3>
      ${chainList(descendants, "No transitive descendants recorded.", node?.code || "", "in")}
    `;
  }

  function renderMatrix(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const rowNodes = ethicsOnly(relationItems(nodeTarget, "out")).slice(0, 28);
    const colNodes = [{ href: nodeTarget, text: node ? `${node.code} · ${node.type}` : "Current", doc: node?.label || "" }]
      .concat(ethicsOnly(relationItems(nodeTarget, "in")).slice(0, 10));
    const depSets = new Map(colNodes.map(col => [col.href, new Set(ethicsOnly(relationItems(col.href, "out")).map(item => item.href))]));
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Usage Matrix")}</h2>
      <p><span class="result-doc">Rows are dependencies. Columns are this node and direct users.</span></p>
      <div class="matrix-scroll">
        <table class="usage-matrix">
          <thead><tr><th>Dependency</th>${colNodes.map(col => `<th><a href="${withBase(col.href)}" data-app-link>${escapeHtml((col.text || col.href).split(" · ")[0])}</a></th>`).join("")}</tr></thead>
          <tbody>
            ${rowNodes.map(row => `<tr><th><a href="${withBase(row.href)}" data-app-link>${escapeHtml((row.text || row.href).split(" · ")[0])}</a></th>${colNodes.map(col => `<td class="${depSets.get(col.href)?.has(row.href) ? "has-edge" : ""}">${depSets.get(col.href)?.has(row.href) ? "use" : ""}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function graphNodeLabel(item) {
    return escapeHtml((item.text || item.href || "").split(" · ")[0]);
  }

  function renderGraph(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const deps = ethicsOnly(relationItems(nodeTarget, "out")).slice(0, 10);
    const usedBy = ethicsOnly(relationItems(nodeTarget, "in")).slice(0, 10);
    const left = deps.map((item, i) => ({ ...item, x: 90, y: 42 + i * 34 }));
    const right = usedBy.map((item, i) => ({ ...item, x: 370, y: 42 + i * 34 }));
    const centerY = Math.max(95, 42 + Math.max(left.length, right.length) * 17);
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Graph")}</h2>
      <p><span class="result-doc">Local neighborhood: dependencies point into the selected node; users point out.</span></p>
      <svg class="node-graph" viewBox="0 0 460 ${Math.max(210, centerY * 2)}" role="img" aria-label="Node dependency graph">
        ${left.map(n => `<line x1="${n.x + 54}" y1="${n.y}" x2="220" y2="${centerY}" />`).join("")}
        ${right.map(n => `<line x1="240" y1="${centerY}" x2="${n.x - 54}" y2="${n.y}" />`).join("")}
        ${left.map(n => `<a href="${withBase(n.href)}" data-app-link><circle cx="${n.x}" cy="${n.y}" r="18" class="dep-node"/><text x="${n.x}" y="${n.y + 4}" text-anchor="middle">${graphNodeLabel(n)}</text></a>`).join("")}
        <a href="${nodePageHref(node)}"><circle cx="230" cy="${centerY}" r="26" class="focus-node"/><text x="230" y="${centerY + 5}" text-anchor="middle">${escapeHtml(node?.code || "node")}</text></a>
        ${right.map(n => `<a href="${withBase(n.href)}" data-app-link><circle cx="${n.x}" cy="${n.y}" r="18" class="use-node"/><text x="${n.x}" y="${n.y + 4}" text-anchor="middle">${graphNodeLabel(n)}</text></a>`).join("")}
      </svg>
    `;
  }

  function renderDossier(target) {
    const panel = $("#panel-content");
    const nodeTarget = canonicalTarget(nearestEthicsTarget(target));
    const node = data.ethicsNodes.find(n => n.href === nodeTarget) || ethicsNodeForTarget(target);
    const raw = data.outgoing[nodeTarget] || data.outgoing[target] || [];
    const notes = [];
    const glossary = [];
    const resources = [];
    for (const edge of raw) {
      const href = edge.target || edge.href;
      if (!href || data.ethicsNodes.some(n => n.href === canonicalTarget(href))) continue;
      const item = { href, text: edge.label || href, doc: edge.doc || edge.file || "" };
      if (href.includes("part0033.html")) notes.push(item);
      else if ((edge.classes || "").includes("gloss")) glossary.push(item);
      else if (href.startsWith("/text/")) resources.push(item);
    }
    panel.innerHTML = `
      <h2>${escapeHtml(node?.code || "Study Dossier")}</h2>
      <p><span class="result-doc">${notes.length} note${notes.length === 1 ? "" : "s"} · ${glossary.length} glossary term${glossary.length === 1 ? "" : "s"} · ${resources.length} resource${resources.length === 1 ? "" : "s"}</span></p>
      <h3>Curley / Editorial Notes</h3>
      ${linkList(notes, "No linked editorial notes recorded for this node.")}
      <h3>Glossary Terms</h3>
      ${linkList(glossary, "No linked glossary terms recorded for this node.")}
      <h3>Other Linked Resources</h3>
      ${linkList(resources, "No other linked resources recorded for this node.")}
    `;
  }

  function positionHoverCard(event) {
    if (!hoverCard) return;
    const pad = 14;
    const rect = hoverCard.getBoundingClientRect();
    let left = event.clientX + 18;
    let top = event.clientY + 18;
    if (left + rect.width + pad > window.innerWidth) left = Math.max(pad, event.clientX - rect.width - 18);
    if (top + rect.height + pad > window.innerHeight) top = Math.max(pad, window.innerHeight - rect.height - pad);
    hoverCard.style.left = left + "px";
    hoverCard.style.top = top + "px";
  }

  function hideHoverCard() {
    clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(() => {
      if (hoverCard) hoverCard.remove();
      hoverCard = null;
    }, 140);
  }

  function showHoverCard(target, label, event) {
    // `target` is a real (base-prefixed) site path -- correct as-is for the
    // rendered "Open"/copy-link href. `key` strips the base back off for the
    // data.* lookups and for data-pin, which selectTarget expects as a
    // data-model key.
    const key = stripBase(target);
    clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(async () => {
      const rec = data.anchors[key] || {};
      const incoming = data.backlinks[key] || [];
      const outgoing = data.outgoing[key] || [];
      const snippet = await targetSnippet(target);
      if (!hoverCard) {
        hoverCard = document.createElement("div");
        hoverCard.className = "hover-card";
        document.body.appendChild(hoverCard);
        hoverCard.addEventListener("mouseenter", () => clearTimeout(hoverTimer));
        hoverCard.addEventListener("mouseleave", hideHoverCard);
      }
      hoverCard.innerHTML = `
        <h2>${escapeHtml(rec.label || label || key)}</h2>
        <span class="result-doc">${escapeHtml(rec.doc || key)}</span>
        ${snippet ? `<p>${escapeHtml(snippet)}</p>` : `<p>No readable preview available for this anchor.</p>`}
        <p>${incoming.length} backlink${incoming.length === 1 ? "" : "s"} · ${outgoing.length} outgoing link${outgoing.length === 1 ? "" : "s"}</p>
        <div class="hover-actions">
          <a href="${target}" data-app-link>Open</a>
          <button type="button" data-copy="${target}">Copy link</button>
          <button type="button" data-pin="${key}">Pin in panel</button>
        </div>
      `;
      positionHoverCard(event);
    }, 180);
  }

  function renderPanel() {
    const panel = $("#panel-content");
    if (!panel) return;
    const target = state.selectedTarget || currentSectionHref();
    const rec = data.anchors[target] || {};
    const incoming = data.backlinks[target] || [];
    const outgoing = data.outgoing[target] || data.outgoing[currentSectionHref()] || [];
    $$(".panel-tabs button").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === state.activeTab));

    if (["relations", "context", "proof", "incoming", "outgoing"].includes(state.activeTab)) {
      state.activeTab = "relations";
      $$(".panel-tabs button").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === state.activeTab));
      renderRelations(target);
      return;
    }
    if (state.activeTab === "dossier") {
      renderDossier(target);
      return;
    }
    if (state.activeTab === "chains") {
      renderChains(target);
      return;
    }
    if (["graph", "matrix"].includes(state.activeTab)) {
      state.activeTab = "graph";
      $$(".panel-tabs button").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === state.activeTab));
      renderGraph(target);
      return;
    }
    if (state.activeTab === "search") {
      renderSearchResults(state.lastSearch || $("#global-search")?.value || "");
      return;
    }
    const targetText = rec.label || target;
    const exact = target.split("#")[1] ? $("#app-document #" + CSS.escape(target.split("#")[1])) : null;
    const visibleSnippet = exact ? exact.textContent.replace(/\s+/g, " ").trim().slice(0, 700) : "";
    panel.innerHTML = `
      <h2>${escapeHtml(targetText)}</h2>
      <p><span class="result-doc">${escapeHtml(rec.doc || state.currentPath)}</span></p>
      ${visibleSnippet ? `<p>${escapeHtml(visibleSnippet)}</p>` : ""}
      <p><a href="${withBase(target)}" data-app-link>Open target</a></p>
    `;
  }

  function renderSearchResults(query) {
    const panel = $("#panel-content");
    if (!panel) return;
    state.lastSearch = query.trim();
    if (!state.lastSearch) {
      panel.innerHTML = `<h2>Search</h2><p>Type in the search field to search the Ethics-centered corpus and referenced context.</p>`;
      return;
    }
    const q = state.lastSearch.toLowerCase();
    const results = data.search.filter(row => row.text.toLowerCase().includes(q) || row.doc.toLowerCase().includes(q)).slice(0, 120);
    panel.innerHTML = `<h2>Search</h2><p>${results.length} result${results.length === 1 ? "" : "s"} for “${escapeHtml(state.lastSearch)}”.</p>${linkList(results, "No matches.")}`;
  }

  function renderEthicsContents() {
    const mount = $("#ethics-node-contents");
    if (!mount) return;
    const groups = new Map();
    for (const node of data.ethicsNodes) {
      const part = node.code.startsWith("IIP") || node.code.startsWith("IID") || node.code.startsWith("IIA") ? "Part II"
        : node.code.startsWith("IIIP") || node.code.startsWith("IIID") ? "Part III"
        : node.code.startsWith("IV") ? "Part IV"
        : node.code.startsWith("V") ? "Part V"
        : "Part I";
      if (!groups.has(part)) groups.set(part, []);
      groups.get(part).push(node);
    }
    mount.innerHTML = Array.from(groups.entries()).map(([part, nodes]) => `
      <section class="node-group">
        <h3>${escapeHtml(part)}</h3>
        ${nodes.map(node => `<a href="${nodePageHref(node)}" title="${escapeHtml(node.label)}"><span class="node-code">${escapeHtml(node.code)}</span><span class="node-label">${escapeHtml(node.type)}</span></a>`).join("")}
      </section>
    `).join("");
  }

  function init() {
    const params = new URLSearchParams(location.search);
    const initial = params.get("doc") || localStorage.getItem("spinoza:lastTarget") || "/text/part0029_split_001.html#ch6d";
    applyReaderModes();
    loadDocument(initial, false);

    document.addEventListener("click", event => {
      const tab = event.target.closest(".panel-tabs button[data-tab]");
      if (tab) {
        state.activeTab = tab.dataset.tab;
        renderPanel();
        return;
      }
      const railTab = event.target.closest("[data-rail-tab]");
      if (railTab) {
        state.activeTab = railTab.dataset.railTab;
        renderPanel();
        return;
      }
      const copy = event.target.closest("[data-copy]");
      if (copy) {
        const target = copy.dataset.copy;
        navigator.clipboard && navigator.clipboard.writeText(location.origin + target);
        copy.textContent = "Copied";
        window.setTimeout(() => { copy.textContent = "Copy link"; }, 1200);
        return;
      }
      const pin = event.target.closest("[data-pin]");
      if (pin) {
        selectTarget(pin.dataset.pin);
        hideHoverCard();
        return;
      }
      const a = event.target.closest("a[href]");
      if (!a) return;
      // normalizeHref resolves the rendered href against the real (base-
      // prefixed) page URL into a site path; strip the base back off before
      // treating it as a data-model key.
      const href = stripBase(normalizeHref(a.getAttribute("href"), withBase(state.currentPath)));
      if (href.startsWith("/text/") || href.startsWith("/titlepage")) {
        event.preventDefault();
        selectTarget(href);
        loadDocument(href, true);
      }
    });

    document.addEventListener("mouseover", event => {
      const a = event.target.closest("a.reference-link[href], a[data-app-link][href]");
      if (!a) return;
      // sitePath: a real, base-prefixed browser path -- used for the hover
      // card's own href/copy-link. dataKey: the same path with the deploy
      // base stripped -- used for every data.* lookup.
      const sitePath = normalizeHref(a.getAttribute("href"), withBase(state.currentPath));
      const dataKey = stripBase(sitePath);
      selectTarget(dataKey);
      showHoverCard(sitePath, a.textContent.trim(), event);
    });

    document.addEventListener("mousemove", event => {
      if (hoverCard) positionHoverCard(event);
    });

    document.addEventListener("mouseout", event => {
      const a = event.target.closest("a.reference-link[href], a[data-app-link][href]");
      if (a) hideHoverCard();
    });

    $("#global-search")?.addEventListener("input", event => {
      state.activeTab = "search";
      renderSearchResults(event.target.value);
    });

    $("#global-search")?.addEventListener("keydown", event => {
      if (event.key !== "Enter") return;
      const node = nodeByCode(event.target.value);
      if (!node) return;
      event.preventDefault();
      location.href = nodePageHref(node);
    });

    $("#open-apparatus")?.addEventListener("click", () => {
      state.activeTab = "relations";
      selectTarget(currentSectionHref());
      if (matchMedia("(max-width: 1240px)").matches) {
        requestAnimationFrame(() => {
          const panel = $("#app-panel");
          if (!panel) return;
          window.scrollTo({ top: panel.getBoundingClientRect().top + window.scrollY - 8, behavior: "auto" });
        });
      }
    });

    $("#toggle-columns")?.addEventListener("click", () => {
      state.columns = !state.columns;
      localStorage.setItem("spinoza:columns", state.columns ? "1" : "0");
      applyReaderModes();
    });

    $("#toggle-marginalia")?.addEventListener("click", () => {
      state.marginalia = !state.marginalia;
      localStorage.setItem("spinoza:marginalia", state.marginalia ? "1" : "0");
      applyReaderModes();
    });

    $("#marginalia-mode")?.addEventListener("change", event => {
      state.marginaliaMode = event.target.value;
      localStorage.setItem("spinoza:marginaliaMode", state.marginaliaMode);
      buildMarginalia($("#app-document"));
      applyReaderModes();
    });

    $("#app-reader")?.addEventListener("scroll", () => {
      if (state.activeTab === "target") selectTarget(currentSectionHref());
      else renderBreadcrumbs(currentSectionHref());
    }, { passive: true });

    window.addEventListener("popstate", event => {
      const params = new URLSearchParams(location.search);
      const target = event.state?.target || params.get("doc") || "/text/part0029_split_001.html#ch6d";
      loadDocument(target, false);
    });
  }

  renderEthicsContents();
  init();
})();


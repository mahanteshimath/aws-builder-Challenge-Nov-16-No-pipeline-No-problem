"use strict";
(() => {
  const POLL_MS = 3000, STALE_MS = 10000;
  const q = new URLSearchParams(location.hash.slice(1));
  const ctx = { job: q.get("job"), sup: q.get("sup"), slot: q.get("slot"), key: q.get("key"), wall: q.get("wall"), w: q.get("w") };
  if (q.get("embed") === "1") document.body.classList.add("embed");
  if (q.get("wall")) document.body.classList.add("wall-mode");
  const $ = (id) => document.getElementById(id);
  const app = $("app");

  /* ---------- dom + icons ---------- */
  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value" || k === "checked") el[k] = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    return el;
  }
  const NS = "http://www.w3.org/2000/svg";
  const ICONS = {
    lock: [["path", { d: "M7.5 10.5V8a4.5 4.5 0 0 1 9 0v2.5" }], ["rect", { x: 5, y: 10.5, width: 14, height: 9.5, rx: 1.5 }], ["path", { d: "M12 14.2v2.4" }]],
    unlock: [["path", { d: "M7.5 10.5V8a4.5 4.5 0 0 1 8.7-1.6" }], ["rect", { x: 5, y: 10.5, width: 14, height: 9.5, rx: 1.5 }], ["path", { d: "M12 14.2v2.4" }]],
    copy: [["rect", { x: 9, y: 9, width: 11, height: 11, rx: 2 }], ["path", { d: "M5 15V6a2 2 0 0 1 2-2h9" }]],
    qr: [["rect", { x: 4, y: 4, width: 6, height: 6 }], ["rect", { x: 14, y: 4, width: 6, height: 6 }], ["rect", { x: 4, y: 14, width: 6, height: 6 }], ["path", { d: "M14 14h2v2h-2zM19 14h1M14 19h2M18 18v2h2" }]],
    check: [["path", { d: "M5 12.5l4.5 4.5L19 7.5" }]],
    chain: [["path", { d: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1" }], ["path", { d: "M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" }]],
    warn: [["path", { d: "M12 4l9 16H3z" }], ["path", { d: "M12 10v4M12 17.2v.1" }]],
    download: [["path", { d: "M12 4v11M7.5 11l4.5 4.5 4.5-4.5M5 20h14" }]],
    external: [["path", { d: "M14 5h5v5M19 5l-8 8M18 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h4" }]],
    x: [["path", { d: "M6 6l12 12M18 6L6 18" }]],
    screen: [["rect", { x: 3, y: 4, width: 18, height: 12, rx: 2 }], ["path", { d: "M8 20h8M12 16v4" }]],
    play: [["path", { d: "M8 5.5l11 6.5-11 6.5z" }]],
  };
  function icon(name, size = 20) {
    const s = document.createElementNS(NS, "svg");
    for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", width: size, height: size, fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" })) s.setAttribute(k, v);
    for (const [tag, attrs] of ICONS[name]) { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); s.append(e); }
    return s;
  }
  function qrSvg(text) {
    const code = qrcode(0, "M"); code.addData(text); code.make();
    const n = code.getModuleCount(), pad = 3;
    let d = "";
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      if (!code.isDark(y, x)) continue;
      let x2 = x; while (x2 < n && code.isDark(y, x2)) x2++;
      d += `M${x + pad} ${y + pad}h${x2 - x}v1h-${x2 - x}z`; x = x2;
    }
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", `0 0 ${n + pad * 2} ${n + pad * 2}`); s.setAttribute("shape-rendering", "crispEdges");
    s.setAttribute("role", "img"); s.setAttribute("aria-label", "QR code for the link");
    const p = document.createElementNS(NS, "path"); p.setAttribute("d", d); p.setAttribute("fill", "currentColor"); s.append(p);
    return s;
  }

  /* ---------- helpers ---------- */
  const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "";
  const list = (a) => a.length < 2 ? a.join("") : `${a.slice(0, -1).join(", ")} and ${a.at(-1)}`;
  const link = (o) => `${location.origin}/#${new URLSearchParams(o)}`;
  const EVENTS = { JOB_OPENED: "Job opened", LOCK_APPLIED: "Lock applied", LOCK_RELEASED: "Lock released", LOCK_HANDED_OVER: "Handover", SUPERVISOR_OVERRIDE: "Override", RESTART_REFUSED: "Restart refused", CLEARED_FOR_RESTART: "Cleared", RESTART_AUTHORIZED: "Restart authorized" };
  const TONE = { RESTART_REFUSED: "bad", SUPERVISOR_OVERRIDE: "warn", CLEARED_FOR_RESTART: "good", RESTART_AUTHORIZED: "good" };

  function toast(text, kind) {
    const t = h("div", { class: "toast", "data-k": kind || "ok", role: kind === "err" ? "alert" : null }, icon(kind === "err" ? "warn" : "check", 18), h("span", {}, text));
    $("toasts").append(t);
    setTimeout(() => t.remove(), kind === "err" ? 7000 : 4000);
  }
  async function copy(text, label) {
    try { await navigator.clipboard.writeText(text); toast(`${label} copied`); return; } catch { /* fall through to the legacy path */ }
    const ta = h("textarea", { value: text, "aria-hidden": "true" }); document.body.append(ta); ta.select();
    try { document.execCommand("copy"); toast(`${label} copied`); } catch { toast("Copy failed. Select the link and copy it by hand.", "err"); }
    ta.remove();
  }
  async function api(path, body) {
    try {
      const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : { cache: "no-store" });
      return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
    } catch { return { ok: false, status: 0, data: { error: "Network error. Check your connection and try again." } }; }
  }
  function show(...nodes) { // replace the view but keep keyboard focus and caret where the user left them
    const a = document.activeElement, id = a && a.id, sel = a && a.selectionStart != null ? [a.selectionStart, a.selectionEnd] : null;
    app.replaceChildren(...nodes.flat(Infinity).filter(Boolean));
    app.setAttribute("aria-busy", "false");
    const el = id && $(id);
    if (el) { el.focus({ preventScroll: true }); if (sel) try { el.setSelectionRange(...sel); } catch { /* not a text field */ } }
  }

  /* ---------- state ---------- */
  const S = { data: null, raw: "", lastOk: 0, stale: false, seq: 0, applied: 0, notFound: false, opened: null, qr: {}, busy: new Set(),
    mine: {}, ui: { release: false, handover: false, to: "", ovr: null, ovrReason: "", ovrOk: false, relOk: false, restart: null, handed: null }, announced: "" };
  const F = { machine: "", supervisor: "", roster: [], draft: "", timing: "shift", lockWait: "", stuck: "", code: "", needsCode: false, errors: {}, error: "", busy: false };

  /* ---------- home: open a lockout ---------- */
  function addNames(raw) {
    for (const n of raw.split(/[\n,]/).map((s) => s.trim()).filter(Boolean)) {
      if (n.length > 40) { F.errors.roster = "Each name must be 40 characters or fewer."; continue; }
      if (F.roster.some((r) => r.toLowerCase() === n.toLowerCase())) { F.errors.roster = `${n} is already on the list.`; continue; }
      if (F.roster.length >= 20) { F.errors.roster = "A lockout can have at most 20 workers."; break; }
      F.roster.push(n); delete F.errors.roster;
    }
  }
  const seconds = (v) => /^\d+$/.test(v) && +v >= 10 && +v <= 604800;
  async function submitOpen(e) {
    e.preventDefault();
    addNames(F.draft); F.draft = "";
    const er = {};
    if (!F.machine.trim()) er.machine = "Enter the machine name.";
    if (!F.supervisor.trim()) er.supervisor = "Enter the supervisor's name.";
    if (!F.roster.length) er.roster = "Add at least one worker.";
    if (F.timing === "custom") {
      if (!seconds(F.lockWait)) er.lockwait = "Whole seconds, 10 to 604800.";
      if (!seconds(F.stuck)) er.stuck = "Whole seconds, 10 to 604800.";
    }
    F.errors = er; F.error = "";
    if (Object.keys(er).length) { render(); const first = ["machine", "supervisor", "roster-draft", "lockwait", "stuck"].find((id) => $(id) && $(id).getAttribute("aria-invalid") === "true"); if (first) $(first).focus(); return; }
    const body = { machine: F.machine, supervisor: F.supervisor, roster: F.roster, siteCode: F.code };
    if (F.timing === "demo") Object.assign(body, { lockWaitSeconds: 120, stuckSeconds: 45 });
    if (F.timing === "custom") Object.assign(body, { lockWaitSeconds: +F.lockWait, stuckSeconds: +F.stuck });
    F.busy = true; render();
    const r = await api("/jobs", body);
    F.busy = false;
    if (r.ok) { S.opened = { ...r.data, machine: F.machine }; render(); scrollTo(0, 0); return; }
    if (r.status === 403) F.needsCode = true;
    F.error = r.data.error || "Could not open the lockout. Try again."; render();
  }
  function fillDemo() { Object.assign(F, { machine: "Press Line 4", supervisor: "Sam", roster: ["Asha", "Ben", "Chen"], draft: "", timing: "demo", errors: {}, error: "" }); render(); }

  function field(id, label, input, err, hint) {
    return h("div", { class: "field" }, h("label", { for: id }, label), input, hint && h("p", { class: "hint", id: `${id}-hint` }, hint), err && h("p", { class: "err", id: `${id}-err` }, err));
  }
  function renderHome() {
    const er = F.errors, txt = (id, key, ph) => h("input", { id, type: "text", value: F[key], placeholder: ph, autocomplete: "off", maxlength: 60, "aria-invalid": er[id] ? "true" : null, "aria-describedby": er[id] ? `${id}-err` : null, oninput: (e) => { F[key] = e.target.value; } });
    const TIMING = { shift: "Alert if a lock isn't applied within 15 minutes, or is still on after 4 hours.", demo: "Alert after 2 minutes and 45 seconds. Use this for recordings.", custom: "Set both limits in seconds." };
    const timing = (v, title) => h("label", {}, h("input", { id: `timing-${v}`, type: "radio", name: "timing", value: v, checked: F.timing === v, onchange: () => { F.timing = v; render(); } }), h("span", {}, title));
    show(h("div", { class: "home" },
      h("section", { class: "pitch" },
        h("h1", {}, "Nobody restarts the machine while someone is still inside it."),
        h("p", { class: "lede" }, "Each worker puts on their own digital lock from their phone. The machine is cleared only when every lock is off, and every step goes into a tamper-evident log."),
        h("ol", { class: "steps" },
          h("li", {}, h("span", { class: "n" }, "01"), h("div", {}, h("h2", {}, "List the crew"), h("p", {}, "The supervisor names everyone who will work on the machine. Each person gets a personal link."))),
                    h("li", {}, h("span", { class: "n" }, "02"), h("div", {}, h("h2", {}, "Everyone locks, everyone releases"), h("p", {}, "A lock goes on before anyone enters and comes off only when that person is out. At shift change a lock is handed over without a gap."))),
                    h("li", {}, h("span", { class: "n" }, "03"), h("div", {}, h("h2", {}, "The last lock decides"), h("p", {}, "A restart is refused while any lock is on, and the refusal is logged. When the last lock comes off, the workflow re-checks every lock before it clears the machine.")))),
        h("p", { class: "stat" }, h("strong", {}, "Lockout/tagout was the 4th most-cited OSHA standard in fiscal year 2025, with 2,562 citations. "), h("a", { href: "https://www.osha.gov/top10citedstandards", rel: "noopener" }, "OSHA top 10"))),
      h("form", { class: "sheet", novalidate: true, onsubmit: submitOpen, "aria-labelledby": "form-title" },
        h("div", { class: "sheet-head" }, h("h2", { id: "form-title" }, "Open a lockout"), h("button", { class: "linkbtn", type: "button", onclick: fillDemo }, "Fill with a demo crew")),
        field("machine", "Machine", txt("machine", "machine", "Press Line 4"), er.machine),
        field("supervisor", "Supervisor", txt("supervisor", "supervisor", "Who will authorize the restart"), er.supervisor),
        h("div", { class: "field" }, h("label", { for: "roster-draft" }, "Who will work on it"),
          F.roster.length ? h("div", { class: "chips" }, F.roster.map((n, i) => h("span", { class: "chip" }, n, h("button", { type: "button", "aria-label": `Remove ${n}`, onclick: () => { F.roster.splice(i, 1); render(); } }, icon("x", 14))))) : null,
          h("input", { id: "roster-draft", type: "text", value: F.draft, placeholder: F.roster.length ? "Add another name" : "Type a name, press Enter", autocomplete: "off", "aria-invalid": er.roster ? "true" : null, "aria-describedby": er.roster ? "roster-err" : "roster-draft-hint",
            oninput: (e) => { F.draft = e.target.value; },
            onkeydown: (e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addNames(F.draft); F.draft = ""; render(); } else if (e.key === "Backspace" && !F.draft && F.roster.length) { F.roster.pop(); render(); } },
            onpaste: (e) => { const t = e.clipboardData && e.clipboardData.getData("text"); if (t && /[\n,]/.test(t)) { e.preventDefault(); addNames(t); render(); } },
            onblur: () => { if (F.draft.trim()) { addNames(F.draft); F.draft = ""; render(); } } }),
          h("p", { class: "hint", id: "roster-draft-hint" }, `${F.roster.length} of up to 20. Press Enter after each name.`), er.roster && h("p", { class: "err", id: "roster-err" }, er.roster)),
        h("fieldset", { class: "timing" }, h("legend", { class: "label" }, "Alert timing"),
          h("div", { class: "seg seg--radio", role: "radiogroup" }, timing("shift", "Shift"), timing("demo", "Demo"), timing("custom", "Custom")),
          h("p", { class: "hint" }, TIMING[F.timing]),
          F.timing === "custom" && h("div", { class: "custom" },
            field("lockwait", "Not applied after", h("input", { id: "lockwait", type: "number", min: 10, max: 604800, value: F.lockWait, "aria-invalid": er.lockwait ? "true" : null, oninput: (e) => { F.lockWait = e.target.value; } }), er.lockwait),
            field("stuck", "Still on after", h("input", { id: "stuck", type: "number", min: 10, max: 604800, value: F.stuck, "aria-invalid": er.stuck ? "true" : null, oninput: (e) => { F.stuck = e.target.value; } }), er.stuck))),
        F.needsCode && field("code", "Site code", h("input", { id: "code", type: "text", value: F.code, autocomplete: "off", oninput: (e) => { F.code = e.target.value; } }), null, "This deployment requires a site code to open a lockout."),
        F.error && h("p", { class: "form-error", role: "alert" }, F.error),
        h("button", { class: "btn btn--danger btn--huge", type: "submit", "data-busy": F.busy ? "true" : null, disabled: F.busy }, icon("lock", 24), F.busy ? "Opening" : "Lock out machine"))));
  }

  /* ---------- opened: links, QR, wall ---------- */
  function linkRow(name, slot, url, qrId) {
    const open = !!S.qr[qrId];
    return h("li", {},
      h("div", { class: "who" }, h("b", {}, name), h("span", { class: "slot" }, slot)),
      h("div", { class: "acts" },
        h("button", { class: "btn btn--quiet btn--small", type: "button", onclick: () => copy(url, `${name}'s link`) }, icon("copy", 16), "Copy link"),
        h("button", { class: "btn btn--quiet btn--small", type: "button", "aria-expanded": String(open), onclick: () => { S.qr[qrId] = !open; render(); } }, icon("qr", 16), open ? "Hide QR" : "QR"),
        h("a", { class: "btn btn--quiet btn--small", href: url, target: "_blank", rel: "noopener" }, icon("external", 16), "Open")),
      open && h("div", { class: "qrbox" }, h("div", { class: "qr" }, qrSvg(url)), h("p", {}, `Scan with ${name === "Supervisor" ? "the supervisor's" : name + "'s"} phone. Anyone holding this link can act as that person.`)));
  }
  function renderOpened() {
    const o = S.opened, supUrl = link({ job: o.jobId, sup: o.supervisorKey }), roUrl = link({ job: o.jobId });
    const wallUrl = link({ wall: o.jobId, sup: o.supervisorKey, w: o.workers.map((w) => `${w.slot}:${w.key}`).join(",") });
    show(h("section", { class: "opened" },
      h("p", { class: "eyebrow" }, "Lockout opened"),
      h("h1", {}, `${o.machine} is locked out.`),
      h("p", { class: "lede" }, "Send each person their own link. They appear only on this screen, and anyone holding a link can act as that person."),
      h("div", { class: "row-actions" },
        h("a", { class: "btn", href: supUrl }, icon("lock", 18), "Open supervisor board"),
        h("a", { class: "btn btn--outline", href: wallUrl }, icon("screen", 18), "Open demo wall"),
        h("button", { class: "btn btn--quiet", type: "button", onclick: () => copy(roUrl, "Read-only link") }, icon("copy", 18), "Copy read-only link")),
      h("ul", { class: "links" }, linkRow("Supervisor", "SUP", supUrl, "sup"), o.workers.map((w) => linkRow(w.name, w.slot, link({ job: o.jobId, slot: w.slot, key: w.key }), w.slot))),
      h("p", { class: "hint" }, "The demo wall shows the supervisor and every worker side by side on one screen. Use it for demonstrations and training only: it puts every key in one address.")));
  }

  /* ---------- wall ---------- */
  async function renderWall() {
    const workers = (ctx.w || "").split(",").filter(Boolean).map((p) => p.split(":"));
    const names = {};
    const r = await api(`/jobs/${encodeURIComponent(ctx.wall)}`);
    if (r.ok) r.data.locks.forEach((l) => { names[l.slot] = l.holder; });
    const frame = (cls, cap, hash) => h("figure", { class: `frame ${cls}` }, h("figcaption", {}, cap), h("iframe", { src: `${location.origin}/#${hash}&embed=1`, title: cap }));
    show(h("section", {},
      h("div", { class: "wall-head" }, h("p", { class: "eyebrow" }, "Demo wall"), h("h1", {}, r.ok ? `${r.data.machine}: supervisor and every worker` : "Demo wall"),
        h("p", { class: "muted" }, "For demonstrations and training. Each pane is a real session with its own key.")),
      h("div", { class: "wall" }, frame("sup-frame", "Supervisor", `job=${ctx.wall}&sup=${ctx.sup}`), workers.map(([slot, key]) => frame("phone", `${names[slot] || slot} · phone`, `job=${ctx.wall}&slot=${slot}&key=${key}`)))));
  }

  /* ---------- board ---------- */
  const isStale = () => !S.lastOk || Date.now() - S.lastOk > STALE_MS;
  function derive(d) {
    const on = d.locks.filter((l) => l.state === "LOCKED").map((l) => l.holder), wait = d.locks.filter((l) => l.state === "AWAITING").map((l) => l.holder);
    if (S.stale) return { kind: "stale", stamp: "Status unknown", line: `No update for ${Math.round((Date.now() - S.lastOk) / 1000)} seconds. Treat the machine as locked out and follow the physical procedure.` };
    if (d.status === "RESTARTED") return { kind: "restarted", stamp: "Restart authorized", line: `Authorized at ${fmtTime(d.restartedAt)}. The audit record is sealed.` };
    if (d.status === "CLEARED") return { kind: "cleared", stamp: "Cleared for restart", line: `All ${d.locks.length} locks are released and the workflow has re-verified every one.` };
    if (["FAILED", "TIMED_OUT", "ABORTED"].includes(d.workflow)) return { kind: "stopped", stamp: "Workflow stopped", line: "The machine stays locked out. Open a new lockout to continue." };
    const parts = [on.length && `${list(on)} ${on.length > 1 ? "still have" : "still has"} a lock on.`, wait.length && `${list(wait)} ${wait.length > 1 ? "have" : "has"} not locked in yet.`].filter(Boolean);
    return { kind: "locked", stamp: "Locked out", line: parts.length ? `Do not start. ${parts.join(" ")}` : "Do not start. Every lock is off and the workflow is verifying before it clears the machine." };
  }
  function plate(d, v) {
    const off = d.locks.filter((l) => l.state === "RELEASED").length;
    return h("section", { class: "plate", "data-kind": v.kind, "aria-label": "Machine status" },
      h("div", {}, h("p", { class: "tagline" }, `${d.machine} · job ${d.jobId.slice(0, 8)}`), h("h1", { class: "stamp" }, v.stamp), h("p", { class: "line" }, v.line)),
      h("div", { class: "quorum" },
        h("p", { class: "count" }, String(off), h("small", {}, `of ${d.locks.length} locks off`)),
        h("div", { class: "segs", "aria-hidden": "true" }, d.locks.map((l) => h("i", { "data-s": l.state }))),
        h("p", { class: "legend" }, h("span", { class: "r" }, "Released"), h("span", { class: "l" }, "Locked"), h("span", { class: "a" }, "Not yet locked"))));
  }

  async function poll() {
    if (!ctx.job) return;
    const mine = ++S.seq, r = await api(`/jobs/${encodeURIComponent(ctx.job)}`);
    if (mine < S.applied) return;
    S.applied = mine;
    if (r.ok) {
      const wasStale = S.stale;
      S.lastOk = Date.now(); S.stale = false;
      const raw = JSON.stringify(r.data);
      if (raw !== S.raw || wasStale) { S.raw = raw; S.data = r.data; render(); }
    } else if (r.status === 404) { S.notFound = true; render(); }
    updateChip();
  }
  function updateChip() {
    const chip = $("live"); if (!ctx.job || ctx.wall) { chip.hidden = true; return; }
    chip.hidden = false;
    const s = S.lastOk ? Math.round((Date.now() - S.lastOk) / 1000) : null;
    chip.dataset.stale = String(S.stale);
    $("live-text").textContent = s == null ? "Connecting" : S.stale ? `Offline · last update ${s}s ago` : `Live · updated ${s}s ago`;
  }
  async function doAct(kind, body, done) {
    S.busy.add(kind); render();
    const r = await api(`/jobs/${ctx.job}/act`, body);
    S.busy.delete(kind);
    if (r.ok) done(r.data); else toast(r.data.error || "That did not go through. Try again.", "err");
    await poll(); render();
  }
  async function doRestart() {
    S.busy.add("restart"); render();
    const r = await api(`/jobs/${ctx.job}/restart`, { key: ctx.sup });
    S.busy.delete("restart");
    if (r.ok) S.ui.restart = { kind: "ok", title: r.data.already ? "Already authorized" : "Restart authorized", text: r.data.already ? "This restart was authorized earlier." : `The audit is sealed in S3 at ${r.data.sealKey}.` };
    else S.ui.restart = { kind: "err", title: "Restart refused", text: r.data.blocking && r.data.blocking.length ? `Still locked or not yet applied: ${list(r.data.blocking)}. The refusal is in the audit trail.` : r.status === 409 ? "The workflow has not cleared the job yet. Wait a few seconds and try again." : r.data.error || "Restart failed." };
    await poll(); render();
  }
  function ensureCheck(d) {
    const lock = d.locks.find((l) => l.slot === ctx.slot);
    if (!ctx.slot || !ctx.key || !lock || S.mine.pending || (S.mine.holder === lock.holder && S.mine.valid !== undefined)) return;
    S.mine.pending = true;
    api(`/jobs/${ctx.job}/act`, { action: "check", slot: ctx.slot, key: ctx.key }).then((r) => {
      S.mine.pending = false;
      if (r.status === 0) return;
      S.mine.holder = lock.holder; S.mine.valid = r.ok && r.data.valid === true; render();
    });
  }
  const busyBtn = (kind, cls, o, ...kids) => h("button", { class: `btn ${cls}`, type: "button", onclick: o.onclick, "data-busy": S.busy.has(kind) ? "true" : null, disabled: S.busy.has(kind) || !!o.off }, ...kids);

  function handedPanel() {
    const x = S.ui.handed; if (!x) return null;
    return h("div", { class: "callout callout--ok" }, h("b", {}, `Handed over to ${x.to}`), h("p", {}, "The lock never came off. Give them this link; yours no longer works."),
      h("div", { class: "row-actions" }, h("button", { class: "btn btn--small", type: "button", onclick: () => copy(x.url, "Link") }, icon("copy", 16), "Copy link"), h("button", { class: "btn btn--quiet btn--small", type: "button", onclick: () => { x.qr = !x.qr; render(); } }, icon("qr", 16), x.qr ? "Hide QR" : "Show QR")),
      x.qr && h("div", { class: "qr" }, qrSvg(x.url)));
  }
  function mineCard(d) {
    const lock = d.locks.find((l) => l.slot === ctx.slot);
    if (!ctx.slot || !ctx.key || !lock) return null;
    if (S.mine.valid === undefined) return h("div", { class: "mine", role: "status" }, h("p", { class: "who" }, "Checking your link"));
    if (!S.mine.valid) return h("div", { class: "mine" }, h("p", { class: "who" }, "This link is no longer active"), h("p", { class: "help" }, "The lock it controlled was handed over, or the link is incorrect. Ask your supervisor for a current link. You can still watch the board."), handedPanel());
    const open = d.status === "LOCKED_OUT", st = lock.state, U = S.ui;
    let body;
    if (st === "RELEASED") body = [h("p", { class: "help" }, icon("check", 16), " Your lock is released. Thank you. You can close this page.")];
    else if (!open) body = [h("p", { class: "help" }, "This lockout is closed.")];
    else if (st === "AWAITING") body = [
      busyBtn("lock", "btn--danger btn--huge", { onclick: () => doAct("lock", { action: "lock", slot: ctx.slot, key: ctx.key }, () => toast("Your lock is on")) }, icon("lock", 26), "Apply my lock"),
      h("p", { class: "help" }, "Put your physical padlock on first, then tap. Your digital lock stays on until you release it yourself.")];
    else body = [
      h("p", { class: "help" }, `Your lock has been on since ${fmtTime(lock.lockedAt)}.`),
      h("button", { class: "btn btn--outline btn--huge", type: "button", "aria-expanded": String(U.release), onclick: () => { U.release = !U.release; U.relOk = false; render(); } }, icon("unlock", 26), "Release my lock"),
      U.release && h("div", { class: "confirm" },
        h("label", { class: "check", for: "rel-ok" }, h("input", { id: "rel-ok", type: "checkbox", checked: U.relOk, onchange: (e) => { U.relOk = e.target.checked; render(); } }), h("span", {}, "I am out of the machine and my own padlock is off.")),
        busyBtn("release", "btn--ok", { off: !U.relOk, onclick: () => doAct("release", { action: "release", slot: ctx.slot, key: ctx.key }, () => { U.release = false; U.relOk = false; toast("Your lock is released"); }) }, "Confirm release")),
      h("div", { class: "more" },
        h("button", { class: "linkbtn", type: "button", "aria-expanded": String(U.handover), onclick: () => { U.handover = !U.handover; render(); } }, "Handing over at shift change?"),
        U.handover && h("div", { class: "confirm" },
          field("handover-to", "Incoming worker", h("input", { id: "handover-to", type: "text", value: U.to, maxlength: 40, autocomplete: "off", oninput: (e) => { U.to = e.target.value; } }), null, "The lock stays on while it changes hands."),
          busyBtn("handover", "btn--outline", { onclick: () => {
            const to = U.to.trim(); if (!to) { toast("Enter the incoming worker's name.", "err"); return; }
            doAct("handover", { action: "handover", slot: ctx.slot, key: ctx.key, to }, (r) => { U.handed = { to: r.holder, url: link({ job: ctx.job, slot: r.slot, key: r.key }), qr: false }; U.handover = false; U.to = ""; S.mine = { holder: r.holder, valid: false }; toast(`Lock handed over to ${r.holder}`); });
          } }, "Hand over my lock")))];
    return h("div", { class: "mine" }, h("p", { class: "who" }, `You are ${lock.holder}`), body, handedPanel());
  }
  function supPanel(d) {
    if (!ctx.sup) return null;
    const r = S.ui.restart, done = d.status === "RESTARTED";
    return h("section", { class: "panel sup" }, h("h2", {}, "Supervisor"),
      busyBtn("restart", "btn--huge", { off: done || S.stale, onclick: doRestart }, icon("play", 24), done ? "Restart authorized" : "Request restart"),
      h("p", { class: "hint" }, "Refused while any lock is on. Every refusal is written to the audit trail."),
      r && h("div", { class: `callout callout--${r.kind}`, role: r.kind === "err" ? "alert" : "status" }, h("b", {}, r.title), r.text),
      h("div", { class: "links-mini" }, h("button", { class: "btn btn--quiet btn--small", type: "button", onclick: () => copy(link({ job: ctx.job }), "Read-only link") }, icon("copy", 16), "Copy read-only link")));
  }
  function lockRow(l, d) {
    const U = S.ui, can = ctx.sup && d.status === "LOCKED_OUT" && l.state !== "RELEASED";
    const meta = l.state === "LOCKED" ? `on since ${fmtTime(l.lockedAt)}` : l.state === "RELEASED" ? `off ${fmtTime(l.releasedAt)}${String(l.releasedBy || "").startsWith("SUPERVISOR") ? " · override" : ""}` : "not locked in yet";
    const reasonOk = U.ovrReason.trim().length >= 10 && U.ovrOk;
    return h("li", { class: "lock", "data-s": l.state },
      h("span", { class: "ic" }, icon(l.state === "RELEASED" ? "unlock" : "lock", 20)),
      h("div", {}, h("div", { class: "nm" }, l.holder), h("div", { class: "meta" }, meta)),
      h("span", { class: "flag", "data-s": l.state }, l.state === "AWAITING" ? "Not locked" : l.state === "LOCKED" ? "Locked" : "Released"),
      can && h("div", { class: "ovr" }, h("button", { class: "linkbtn", type: "button", "aria-expanded": String(U.ovr === l.slot), onclick: () => { U.ovr = U.ovr === l.slot ? null : l.slot; U.ovrReason = ""; U.ovrOk = false; render(); } }, "Supervisor override")),
      can && U.ovr === l.slot && h("div", { class: "override" },
        field("ovr-reason", "Written reason", h("textarea", { id: "ovr-reason", rows: 2, maxlength: 200, value: U.ovrReason, oninput: (e) => { U.ovrReason = e.target.value; const b = $("ovr-go"); if (b) b.disabled = !(U.ovrReason.trim().length >= 10 && U.ovrOk); } }), null, "At least 10 characters. This goes into the audit trail."),
        h("label", { class: "check", for: "ovr-ok" }, h("input", { id: "ovr-ok", type: "checkbox", checked: U.ovrOk, onchange: (e) => { U.ovrOk = e.target.checked; render(); } }), h("span", {}, `I verified that ${l.holder} is not inside the machine.`)),
        h("div", { class: "row" }, h("button", { id: "ovr-go", class: "btn btn--danger btn--small", type: "button", disabled: !reasonOk || S.busy.has("override"), "data-busy": S.busy.has("override") ? "true" : null,
          onclick: () => doAct("override", { action: "override", slot: l.slot, key: ctx.sup, reason: U.ovrReason.trim(), confirmNotInside: true }, () => { U.ovr = null; toast(`${l.holder}'s lock was force-released`); }) }, "Force release"),
          h("button", { class: "btn btn--quiet btn--small", type: "button", onclick: () => { U.ovr = null; render(); } }, "Cancel"))));
  }
  function ledger(d) {
    const ev = d.events.slice().reverse();
    const download = () => { const a = h("a", { href: URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })), download: `loto-${d.jobId}.json` }); document.body.append(a); a.click(); a.remove(); };
    return h("section", { class: "panel" },
      h("h2", {}, "Audit trail", h("span", { class: "chain", "data-ok": String(d.chain.ok) }, icon("chain", 16), d.chain.ok ? `Hash chain verified · ${d.chain.length} events` : `Chain broken: ${d.chain.detail}`)),
      d.sealKey && h("p", { class: "sealed" }, `Sealed in S3 with Object Lock: ${d.sealKey}`),
      h("ol", { class: "ledger", "aria-label": "Audit events, newest first" }, ev.map((e, i) => { const li = h("li", { "data-t": TONE[e.type] || "" },
        h("span", { class: "sq" }, String(e.seq)), h("span", { class: "tm" }, fmtTime(e.ts)), h("span", { class: "ev" }, EVENTS[e.type] || e.type), h("span", { class: "dt" }, e.detail), h("span", { class: "hs", title: `sha256 ${e.hash}\nprev ${e.prevHash}` }, e.hash.slice(0, 8))); li.style.setProperty("--i", Math.min(i, 12)); return li; })),
      h("p", {}, h("button", { class: "btn btn--quiet btn--small", type: "button", onclick: download }, icon("download", 16), "Download audit JSON")));
  }
  function chrome(v, d) {
    document.title = `${v.stamp} · ${d.machine} · LOTO Quorum`;
    const c = { locked: "#c23b22", stopped: "#c23b22", cleared: "#1c7a4b", restarted: "#1c7a4b", stale: "#8a5a00" }[v.kind];
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="${c}"/><path d="M10 14v-3.5a6 6 0 0 1 12 0V14" fill="none" stroke="#fbf9f3" stroke-width="3"/><rect x="7.5" y="14" width="17" height="11.5" rx="1.5" fill="#fbf9f3"/></svg>`;
    $("favicon").href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
    const msg = `${v.stamp}. ${v.line}`;
    if (msg !== S.announced) { S.announced = msg; $("announce").textContent = msg; }
  }
  function renderBoard() {
    if (S.notFound) return show(h("div", { class: "empty" }, h("p", { class: "eyebrow" }, "404"), h("h1", {}, "That lockout doesn't exist."), h("p", { class: "muted" }, "The link may be mistyped, or the job expired. If you are at a locked machine, follow the physical procedure."), h("p", {}, h("a", { class: "btn", href: "/" }, "Open a lockout"))));
    const d = S.data;
    if (!d) return show(
      h("div", { class: "plate", "data-kind": "stale", role: "status" }, h("div", {}, h("p", { class: "tagline" }, "Loading the lockout"), h("h1", { class: "stamp" }, "Connecting"), h("p", { class: "line" }, "Fetching the current lock status. Until it arrives, treat the machine as locked out."))),
      h("div", { class: "board", "aria-hidden": "true" }, h("div", { class: "skel" }), h("div", { class: "skel" })));
    S.stale = isStale(); ensureCheck(d);
    const v = derive(d); chrome(v, d);
    show(plate(d, v), h("div", { class: "board" },
      h("div", {}, mineCard(d), supPanel(d), h("section", { class: "panel" }, h("h2", {}, "Locks", h("span", {}, `${d.locks.filter((l) => l.state === "RELEASED").length} of ${d.locks.length} off`)), h("ul", { class: "locks" }, d.locks.map((l) => lockRow(l, d))))),
      ledger(d)));
  }

  /* ---------- boot ---------- */
  function render() { if (ctx.wall) return; if (ctx.job) return renderBoard(); S.opened ? renderOpened() : renderHome(); }
  function themeControl() {
    const el = $("theme"), cur = () => { try { return localStorage.getItem("loto-theme") || "auto"; } catch { return "auto"; } };
    const apply = (v) => v === "light" || v === "dark" ? document.documentElement.setAttribute("data-theme", v) : document.documentElement.removeAttribute("data-theme");
    const draw = () => el.replaceChildren(...["auto", "light", "dark"].map((v) => h("button", { type: "button", "aria-pressed": String(cur() === v), onclick: () => { try { v === "auto" ? localStorage.removeItem("loto-theme") : localStorage.setItem("loto-theme", v); } catch { /* storage blocked */ } apply(v); draw(); } }, v[0].toUpperCase() + v.slice(1))));
    addEventListener("storage", (e) => { if (e.key === "loto-theme") { apply(e.newValue); draw(); } });
    draw();
  }
  themeControl();
  const notice = $("notice");
  $("open-notice").onclick = () => notice.showModal();
  $("close-notice").onclick = () => notice.close();
  notice.addEventListener("click", (e) => { if (e.target === notice) notice.close(); });
  addEventListener("hashchange", () => location.reload());

  if (ctx.wall) renderWall();
  else if (ctx.job) {
    render(); poll(); updateChip();
    setInterval(() => { if (!document.hidden || Date.now() - S.lastOk > 12000) poll(); }, POLL_MS);
    setInterval(() => { const st = isStale(); const changed = st !== S.stale && S.data; if (changed) S.stale = st; updateChip(); if (changed) render(); }, 1000);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
    addEventListener("online", poll);
  } else render();
})();

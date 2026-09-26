// Panel ramienia SO-101: wspolny dla arm_panel.html (serwer tools/arm_web.py, :8010)
// i frontend.html (panel jazdy web_control.py, :8000 - gada z :8010 przez CORS).
//
//   const arm = mountArmPanel(document.getElementById("arm-root"), {
//     base: "http://" + location.hostname + ":8010",  // "" = ten sam serwer
//     stickyStop: false,    // duzy STOP przyklejony do dolu ekranu
//     keyboardStop: false,  // spacja = STOP ramienia
//   });
//   arm.stop();             // np. z glownego przycisku STOP jazdy
//
// Style sa pod klasa .armp, zeby nie gryzly sie z frontend.html.
// DOM budowany raz; przy odpytywaniu stanu zmieniany jest tylko tekst i pozycje
// znacznikow (docs/HARDWARE.md, pulapka 32).
(function () {
  const CSS = `
  .armp { --armp-ok: #35c759; --armp-bad: #ff453a; --armp-warn: #ffb340; --armp-accent: #4f9dff;
          --armp-muted: #8a8f98; --armp-text: #e6e8eb; --armp-btn: #22262f; --armp-border: #2c313c; }
  .armp .armp-sec { margin-bottom: 14px; }
  .armp .armp-title { font-size: 12px; font-weight: 700; letter-spacing: 0.04em; color: var(--armp-muted); margin-bottom: 8px; }
  .armp .armp-status { display: flex; align-items: center; gap: 8px; font-size: 14px; }
  .armp .armp-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--armp-bad); flex-shrink: 0; }
  .armp .armp-dot.on { background: var(--armp-ok); }
  .armp .armp-dot.busy { background: var(--armp-warn); }
  .armp .armp-muted { color: var(--armp-muted); font-size: 12px; }
  .armp .armp-error { color: var(--armp-bad); font-size: 12px; margin-top: 4px; min-height: 1em; word-break: break-word; }
  .armp button {
    font: inherit; color: var(--armp-text); background: var(--armp-btn);
    border: 1px solid var(--armp-border); border-radius: 8px; cursor: pointer;
    user-select: none; -webkit-user-select: none; touch-action: manipulation;
  }
  .armp button:active { background: var(--armp-accent); border-color: var(--armp-accent); color: #fff; }
  .armp button:disabled { opacity: 0.35; cursor: default; }
  .armp .armp-steps { display: flex; gap: 8px; }
  .armp .armp-steps button { flex: 1; padding: 10px; font-weight: 600; }
  .armp .armp-steps button.sel { background: var(--armp-accent); border-color: var(--armp-accent); color: #fff; }
  .armp .armp-joint { display: grid; grid-template-columns: 52px 1fr 52px; gap: 8px; align-items: center; margin-bottom: 10px; }
  .armp .armp-joint button { height: 52px; font-size: 24px; font-weight: 700; }
  .armp .armp-jinfo { min-width: 0; }
  .armp .armp-jname { font-size: 13px; display: flex; justify-content: space-between; gap: 6px; }
  .armp .armp-jval { font-variant-numeric: tabular-nums; font-weight: 600; }
  .armp .armp-track { height: 8px; background: var(--armp-btn); border-radius: 4px; position: relative; margin: 6px 0 3px; }
  .armp .armp-mark { position: absolute; top: -3px; width: 3px; height: 14px; border-radius: 2px; transform: translateX(-1px); }
  .armp .armp-mark.pos { background: var(--armp-ok); }
  .armp .armp-mark.set { background: var(--armp-accent); opacity: 0.7; }
  .armp .armp-jlim { font-size: 11px; color: var(--armp-muted); display: flex; justify-content: space-between; font-variant-numeric: tabular-nums; }
  .armp .armp-row { display: flex; gap: 8px; flex-wrap: wrap; }
  .armp .armp-row button { flex: 1 1 45%; padding: 12px; font-weight: 600; min-width: 100px; }
  .armp .armp-stop { width: 100%; padding: 16px; font-size: 18px; font-weight: 800;
                     background: var(--armp-bad); border-color: var(--armp-bad); color: #fff; }
  .armp .armp-stop:active { background: #c7322a; border-color: #c7322a; }
  .armp .armp-stopbar { position: fixed; left: 0; right: 0; bottom: 0; padding: 12px 16px;
                        background: linear-gradient(transparent, #0f1115 30%); display: flex; justify-content: center; z-index: 10; }
  .armp .armp-stopbar .armp-stop { max-width: 520px; font-size: 20px; padding: 18px; }
  `;

  const OFFLINE = "Serwer ramienia nie działa (na Pi: python tools/arm_web.py)";

  function mountArmPanel(root, opts) {
    opts = opts || {};
    const base = opts.base || "";

    if (!document.getElementById("armp-style")) {
      const st = document.createElement("style");
      st.id = "armp-style";
      st.textContent = CSS;
      document.head.appendChild(st);
    }

    root.classList.add("armp");
    root.innerHTML = `
      <div class="armp-sec">
        <div class="armp-status"><span class="armp-dot"></span><span class="armp-st">łączę z serwerem ramienia...</span></div>
        <div class="armp-muted armp-result"></div>
        <div class="armp-error"></div>
      </div>
      <div class="armp-sec">
        <div class="armp-title">KROK (stopnie, chwytak: jednostki 0-100)</div>
        <div class="armp-steps"></div>
      </div>
      <div class="armp-sec">
        <div class="armp-title">STAWY <span class="armp-muted">(zielony = odczyt z serw, niebieski = ostatnia komenda)</span></div>
        <div class="armp-joints"></div>
      </div>
      <div class="armp-sec armp-poses">
        <div class="armp-title">POZYCJE</div>
        <div class="armp-row">
          <button data-cmd="home" data-always="1">HOME</button>
          <button data-cmd="open">Otwórz chwytak</button>
          <button data-cmd="close">Zamknij chwytak</button>
        </div>
      </div>
      <div class="armp-sec armp-mot">
        <div class="armp-title">RUCHY Z motions/</div>
        <div class="armp-row armp-motions"></div>
      </div>
      <div class="${opts.stickyStop ? "armp-stopbar" : "armp-sec"}">
        <button class="armp-stop" data-always="1">STOP RAMIENIA${opts.keyboardStop ? " (spacja)" : ""}</button>
      </div>`;

    const q = (sel) => root.querySelector(sel);
    const el = {
      dot: q(".armp-dot"), st: q(".armp-st"), result: q(".armp-result"), error: q(".armp-error"),
      steps: q(".armp-steps"), joints: q(".armp-joints"), motions: q(".armp-motions"),
    };
    const marks = {};  // joint -> {v, p, s, lo, hi}
    let step = 5;
    let built = false;
    let motionsKey = "";
    let sendError = "";

    function showError(msg) {
      sendError = msg;
      el.error.textContent = msg;
    }

    async function send(cmd) {
      try {
        const r = await fetch(base + "/api/cmd", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cmd),
        });
        const j = await r.json();
        if (!j.ok) showError("Odrzucone: " + j.msg);
        else if (sendError) showError("");
      } catch (e) {
        showError(OFFLINE);
      }
    }

    function buildSteps(steps) {
      el.steps.textContent = "";
      for (const s of steps) {
        const b = document.createElement("button");
        b.textContent = s;
        b.dataset.step = s;
        b.dataset.always = "1";
        if (s === step) b.classList.add("sel");
        b.onclick = () => {
          step = s;
          for (const x of el.steps.children) x.classList.toggle("sel", Number(x.dataset.step) === step);
        };
        el.steps.appendChild(b);
      }
    }

    function buildJoints(joints) {
      el.joints.textContent = "";
      for (const j of joints) {
        const row = document.createElement("div");
        row.className = "armp-joint";
        row.innerHTML =
          `<button data-j="${j}" data-d="-1">−</button>` +
          `<div class="armp-jinfo">` +
            `<div class="armp-jname"><span>${j}</span><span class="armp-jval">-</span></div>` +
            `<div class="armp-track"><span class="armp-mark set"></span><span class="armp-mark pos"></span></div>` +
            `<div class="armp-jlim"><span></span><span></span></div>` +
          `</div>` +
          `<button data-j="${j}" data-d="1">+</button>`;
        const lim = row.querySelectorAll(".armp-jlim span");
        marks[j] = {
          v: row.querySelector(".armp-jval"), p: row.querySelector(".armp-mark.pos"),
          s: row.querySelector(".armp-mark.set"), lo: lim[0], hi: lim[1],
        };
        row.querySelectorAll("button").forEach((b) => {
          b.onclick = () => send({ cmd: "jog", joint: b.dataset.j, step: Number(b.dataset.d) * step });
        });
        el.joints.appendChild(row);
      }
    }

    function buildMotions(names) {
      el.motions.textContent = "";
      for (const n of names) {
        const b = document.createElement("button");
        b.textContent = n;
        b.onclick = () => send({ cmd: "motion", name: n });
        el.motions.appendChild(b);
      }
      if (!names.length) el.motions.innerHTML = '<span class="armp-muted">brak plików w motions/</span>';
    }

    function placeMark(m, v, lo, hi) {
      if (v === undefined || v === null) { m.style.display = "none"; return; }
      m.style.display = "";
      const f = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
      m.style.left = (f * 100).toFixed(1) + "%";
    }

    function busyText(b) {
      if (b.cmd === "jog") return `ruch: ${b.joint} ${b.step > 0 ? "+" : ""}${b.step}`;
      if (b.cmd === "motion") return `ruch: ${b.name}`;
      return "ruch: " + b.cmd;
    }

    function setEnabled(homed) {
      root.querySelectorAll("button").forEach((b) => {
        if (!b.dataset.always) b.disabled = !homed;
      });
    }

    function render(s) {
      if (!built) {
        buildSteps(s.steps);
        buildJoints(s.joints);
        built = true;
      }
      const key = s.motions.join(",");
      if (key !== motionsKey) { buildMotions(s.motions); motionsKey = key; }

      el.dot.className = "armp-dot " + (s.busy ? "busy" : "on");
      let st = s.busy ? busyText(s.busy) : "gotowe";
      if (s.queue) st += ` (w kolejce: ${s.queue})`;
      if (!s.homed) st = (s.busy ? "jadę do HOME..." : "czekam na HOME") + " - inne komendy zablokowane";
      if (s.manual_only) st += " | tryb bez HOME: tylko stawy i chwytak";
      // --no-home: HOME i ruchy z motions/ wylaczone na serwerze, chowamy je (chwytak zostaje)
      q(".armp-mot").style.display = s.manual_only ? "none" : "";
      q('[data-cmd="home"]').style.display = s.manual_only ? "none" : "";
      el.st.textContent = st;
      el.result.textContent = s.result || "";
      if (s.error) el.error.textContent = "Błąd: " + s.error;
      else if (!sendError) el.error.textContent = "";

      for (const j of s.joints) {
        const m = marks[j];
        const [lo, hi] = s.limits[j];
        const p = s.positions[j];
        m.v.textContent = p === undefined ? "-" : p.toFixed(1);
        m.lo.textContent = lo.toFixed(0);
        m.hi.textContent = hi.toFixed(0);
        placeMark(m.p, p, lo, hi);
        placeMark(m.s, s.setpoint[j], lo, hi);
      }
      setEnabled(s.homed);
    }

    async function poll() {
      let delay = 500;
      try {
        const r = await fetch(base + "/api/state", { cache: "no-store" });
        render(await r.json());
        if (sendError === OFFLINE) showError("");
      } catch (e) {
        el.dot.className = "armp-dot";
        el.st.textContent = OFFLINE;
        setEnabled(false);
        delay = 2000;  // serwer ramienia wylaczony: nie zasypuj konsoli bledami
      }
      setTimeout(poll, delay);
    }

    root.querySelectorAll("[data-cmd]").forEach((b) => {
      b.onclick = () => send({ cmd: b.dataset.cmd });
    });
    const stop = () => send({ cmd: "stop" });
    q(".armp-stop").onclick = stop;
    if (opts.keyboardStop) {
      document.addEventListener("keydown", (e) => {
        if (e.code === "Space") { e.preventDefault(); stop(); }
      });
      // spacja na przycisku z fokusem inaczej "kliknelaby" go przy puszczeniu klawisza
      document.addEventListener("keyup", (e) => { if (e.code === "Space") e.preventDefault(); });
    }
    poll();
    return { stop };
  }

  window.mountArmPanel = mountArmPanel;
})();

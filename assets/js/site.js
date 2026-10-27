// The moving parts of the site: the light/dark switch, the network behind the page titles and the typed
// last word of the tagline. The animations stay still for visitors who ask for reduced motion; without
// JavaScript the page shows the first word and no network.
(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Light/dark switch. The page starts light unless the visitor chose dark before (the inline script
  // in <head> applies that before the first paint); the button stays hidden without JavaScript.
  const root = document.documentElement;
  const toggle = document.querySelector(".theme");
  if (toggle) {
    const meta = document.querySelector('meta[name="theme-color"]');
    const sync = () => {
      const dark = root.dataset.theme === "dark";
      toggle.setAttribute("aria-pressed", dark);
      if (meta) meta.content = dark ? "#05070d" : "#f6f8fc";
    };
    toggle.hidden = false;
    sync();
    toggle.addEventListener("click", () => {
      const dark = root.dataset.theme !== "dark";
      if (dark) root.dataset.theme = "dark"; else delete root.dataset.theme;
      try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) {}
      sync();
      dispatchEvent(new Event("themechange"));
    });
  }

  // Tagline: types out each of data-words in turn.
  for (const rot of document.querySelectorAll(".rot[data-words]")) {
    const words = rot.dataset.words.split("|");
    if (still || words.length < 2) continue;
    let w = 0, n = [...words[0]].length, del = true;
    const tick = () => {
      const chars = [...words[w]];
      n += del ? -1 : 1;
      rot.textContent = chars.slice(0, n).join("");
      let wait = del ? 45 : 85;
      if (del && n === 0) { del = false; w = (w + 1) % words.length; wait = 250; }
      else if (!del && n === [...words[w]].length) { del = true; wait = 2200; }
      setTimeout(tick, wait);
    };
    setTimeout(tick, 2200);
  }

  // Network: nodes in the three research colours drift, nearby nodes link up, and the pointer pulls
  // links towards itself. Drawing stops while the canvas is off screen.
  const R = 130;
  for (const cv of document.querySelectorAll("canvas.net")) {
    const ctx = cv.getContext("2d");
    const host = cv.parentElement;
    let w, h, cols, edge, nodes = [], mouse = null, on = true, queued = false;

    const colours = () => {
      const css = getComputedStyle(document.documentElement);
      cols = ["--c1", "--c2", "--c3"].map(v => css.getPropertyValue(v).trim());
      edge = parseFloat(css.getPropertyValue("--edge")) || 0.35;
      nodes.forEach((p, i) => { p.c = cols[i % 3]; });
    };
    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = cv.clientWidth; h = cv.clientHeight;
      cv.width = w * dpr; cv.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.max(24, Math.min(110, Math.round(w * h / 13000)));
      nodes = Array.from({ length: count }, (_, i) => ({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.35, vy: (Math.random() - 0.5) * 0.35,
        r: 1.2 + Math.random() * 2.2, c: cols[i % 3]
      }));
    };
    const draw = () => {
      queued = false;
      ctx.clearRect(0, 0, w, h);
      if (!still) for (const p of nodes) {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
      }
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j], d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < R) {
            ctx.strokeStyle = a.c;
            ctx.globalAlpha = (1 - d / R) * edge;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          }
        }
        if (mouse) {
          const d = Math.hypot(a.x - mouse.x, a.y - mouse.y);
          if (d < R * 1.6) {
            ctx.strokeStyle = a.c;
            ctx.globalAlpha = (1 - d / (R * 1.6)) * 0.8;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
          }
        }
      }
      for (const p of nodes) {
        ctx.globalAlpha = 0.9;
        ctx.fillStyle = ctx.shadowColor = p.c;
        ctx.shadowBlur = 8;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
      }
      ctx.shadowBlur = 0; ctx.globalAlpha = 1;
      if (!still && on) frame();
    };
    const frame = () => { if (!queued) { queued = true; requestAnimationFrame(draw); } };

    colours(); resize(); draw();
    addEventListener("resize", () => { resize(); frame(); });
    addEventListener("themechange", () => { colours(); frame(); });
    host.addEventListener("pointermove", e => {
      const r = cv.getBoundingClientRect();
      mouse = { x: e.clientX - r.left, y: e.clientY - r.top };
      if (still) frame();
    });
    host.addEventListener("pointerleave", () => { mouse = null; if (still) frame(); });
    new IntersectionObserver(([e]) => { on = e.isIntersecting; if (on) frame(); }).observe(host);
  }
})();

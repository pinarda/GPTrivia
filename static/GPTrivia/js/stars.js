// ─────────────────────────────────────────────
//  little physics helper
// ─────────────────────────────────────────────
const GRAVITY = 0.45;          // px per frame²
const FADE_MS = 300;           // fade-out time

const overlay     = document.getElementById("star-overlay");
const magicButton = document.getElementById("magic-button");
let FOOTER = null;        // declare it at module scope

window.addEventListener('DOMContentLoaded', () => {
  FOOTER = document.getElementById('thefoot');
});
starRadius=5;

function fadeOutAndRemove(elem){
  elem.style.transition = `opacity ${FADE_MS}ms`;
  elem.style.opacity = 0;
  setTimeout(() => elem.remove(), FADE_MS);
}

// Launch one star at (x0, y0) in viewport coordinates
// stars.js  (only the launchStar function has changed)

function launchStar(cx, cy) {
  const s = document.createElement("div");
  s.className = "star";

  // anchor the star’s origin at button centre
  s.style.left = `${cx}px`;
  s.style.top  = `${cy}px`;
  overlay.appendChild(s);

  // relative displacement from the anchor point
  let dx = 0, dy = 0;

  // random initial velocity (px per frame @60 Hz)
  let vx = (Math.random() - 0.5) * 8;     // sideways
  let vy = (Math.random() - 1.2) * 12;    // upward

  const GRAVITY = 0.45;   // px / frame²
  const FADE_MS = 300;

  let last = performance.now();
  let restingTime = 0;        // frames spent almost still
  function frame(t) {
    const dt = (t - last) / 16.7;   // ms → “frames”
    last = t;

    vy += GRAVITY * dt;   // accelerate downward
    dx += vx * dt;
    dy += vy * dt;

    /* ── absolute viewport coords (needed below) ───────── */
    const absX = cx + dx;
    const absY = cy + dy;

    // ─── collision check with footer ───────────────
    const footerTop = FOOTER.getBoundingClientRect().top;
    if (FOOTER){                               // guard for null
      const hitY = FOOTER.getBoundingClientRect().top - starRadius;
      if (absY >= hitY){
        dy = hitY - cy;                        // clamp offset
        vy = -vy * 0.55;                       // bounce (damped)

        if (Math.abs(vy) < 1){                 // settle detector
          vy = 0;  vx *= 0.98;
          restingTime += dt;
          if (restingTime > 40){ fadeOutAndRemove(s); return; }
        } else { restingTime = 0; }
      }
    }

      // ── NEW: colour based on current viewport coords ──
    const normX = dx / window.innerWidth;       // 0 → 1
    const normY = dy / window.innerHeight;      // 0 → 1
    const hue  = normX * 720;                     // 2× colour wheel ⇒ faster change
    const sat  = 60 + (1 - normY) * 40;           // 100 % high up → 60 % near bottom
    const light = 50 + Math.pow(normY, 1.8) * 45; // starts 30 %, ends 75 %

    s.style.backgroundColor = `hsl(${hue}, ${sat}%, ${light}%)`;

    // move only by the *change* since launch
    s.style.transform = `translate(${dx}px, ${dy}px) rotate(${t * 0.6}deg)`;

    if (cy + dy < window.innerHeight + 40) {
      requestAnimationFrame(frame);
    } else { fadeOutAndRemove(s); }
  }
  requestAnimationFrame(frame);
}


// ─────────────────────────────────────────────
//  click handler – fire a burst of stars
// ─────────────────────────────────────────────
magicButton.addEventListener("click", () => {
  const { left, top, width, height } = magicButton.getBoundingClientRect();
  const cx = left + width  / 2;
  const cy = top  + height / 2;

  for (let i = 0; i < 12; i++) launchStar(cx, cy);
});

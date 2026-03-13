// ─────────────────────────────────────────────
//  little physics helper
// ─────────────────────────────────────────────
const GRAVITY = 0.45;          // px per frame²
const FADE_MS = 300;           // fade-out time
const FLOOR_BOUNCE = 0.72;
const SURFACE_BOUNCE = 0.78;
const SURFACE_VERTICAL_DRAG = 0.96;

const overlay = document.getElementById("star-overlay");
const MAX_SPEED = 25; // px/frame at which color hits "max"
const STAR_RADIUS = 5;

function fadeOutAndRemove(elem){
  elem.style.transition = `opacity ${FADE_MS}ms`;
  elem.style.opacity = 0;
  setTimeout(() => elem.remove(), FADE_MS);
}

function parseRgb(color) {
  const match = String(color || '').match(/rgba?\(([^)]+)\)/i);
  if (!match) {
    return null;
  }

  const [r = 0, g = 0, b = 0, a = 1] = match[1].split(',').map(value => Number.parseFloat(value.trim()));
  return { r, g, b, a };
}

function rgbToHue({ r, g, b }) {
  const red = r / 255;
  const green = g / 255;
  const blue = b / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const delta = max - min;

  if (delta === 0) {
    return null;
  }

  let hue;
  if (max === red) {
    hue = ((green - blue) / delta) % 6;
  } else if (max === green) {
    hue = (blue - red) / delta + 2;
  } else {
    hue = (red - green) / delta + 4;
  }

  const degrees = hue * 60;
  return degrees < 0 ? degrees + 360 : degrees;
}

function isRicochetColor(color) {
  const rgb = parseRgb(color);
  if (!rgb || rgb.a === 0) {
    return false;
  }

  const max = Math.max(rgb.r, rgb.g, rgb.b);
  const min = Math.min(rgb.r, rgb.g, rgb.b);
  if (max < 55 || max - min < 35) {
    return false;
  }

  const hue = rgbToHue(rgb);
  if (hue === null) {
    return false;
  }

  return (hue >= 95 && hue <= 165) || hue <= 22 || hue >= 338;
}

function collectRicochetSurfaces() {
  const seen = new Set();
  const surfaces = [];
  const elements = document.querySelectorAll('body *');

  for (const element of elements) {
    if (
      !element ||
      element === overlay ||
      element.classList?.contains('star') ||
      ['SCRIPT', 'STYLE', 'LINK', 'META'].includes(element.tagName)
    ) {
      continue;
    }

    if (overlay && overlay.contains(element)) {
      continue;
    }

    const style = window.getComputedStyle(element);
    if (
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      Number.parseFloat(style.opacity) === 0
    ) {
      continue;
    }

    const hasRicochetColor = [
      style.backgroundColor,
      style.borderTopColor,
      style.borderRightColor,
      style.borderBottomColor,
      style.borderLeftColor,
      style.color,
    ].some(isRicochetColor);

    if (!hasRicochetColor) {
      continue;
    }

    const rect = element.getBoundingClientRect();
    if (
      rect.width < 6 ||
      rect.height < 6 ||
      rect.bottom < 0 ||
      rect.top > window.innerHeight ||
      rect.right < 0 ||
      rect.left > window.innerWidth
    ) {
      continue;
    }

    const key = [
      Math.round(rect.left),
      Math.round(rect.top),
      Math.round(rect.width),
      Math.round(rect.height),
    ].join(':');

    if (seen.has(key)) {
      continue;
    }
    seen.add(key);

    surfaces.push({
      left: rect.left,
      right: rect.right,
      top: rect.top,
      bottom: rect.bottom,
    });
  }

  return surfaces;
}

function resolveSurfaceCollision(previousX, previousY, nextX, nextY, vx, vy, surface) {
  const expanded = {
    left: surface.left - STAR_RADIUS,
    right: surface.right + STAR_RADIUS,
    top: surface.top - STAR_RADIUS,
    bottom: surface.bottom + STAR_RADIUS,
  };

  if (
    nextX < expanded.left ||
    nextX > expanded.right ||
    nextY < expanded.top ||
    nextY > expanded.bottom
  ) {
    return null;
  }

  if (previousY <= expanded.top && nextY >= expanded.top) {
    return {
      x: nextX,
      y: expanded.top,
      vx: vx * SURFACE_VERTICAL_DRAG,
      vy: -Math.abs(vy) * FLOOR_BOUNCE,
    };
  }

  if (previousY >= expanded.bottom && nextY <= expanded.bottom) {
    return {
      x: nextX,
      y: expanded.bottom,
      vx: vx * SURFACE_VERTICAL_DRAG,
      vy: Math.abs(vy) * FLOOR_BOUNCE,
    };
  }

  if (previousX <= expanded.left && nextX >= expanded.left) {
    return {
      x: expanded.left,
      y: nextY,
      vx: -Math.abs(vx) * SURFACE_BOUNCE,
      vy: vy * SURFACE_VERTICAL_DRAG,
    };
  }

  if (previousX >= expanded.right && nextX <= expanded.right) {
    return {
      x: expanded.right,
      y: nextY,
      vx: Math.abs(vx) * SURFACE_BOUNCE,
      vy: vy * SURFACE_VERTICAL_DRAG,
    };
  }

  const distances = [
    { edge: 'left', value: Math.abs(nextX - expanded.left) },
    { edge: 'right', value: Math.abs(nextX - expanded.right) },
    { edge: 'top', value: Math.abs(nextY - expanded.top) },
    { edge: 'bottom', value: Math.abs(nextY - expanded.bottom) },
  ].sort((left, right) => left.value - right.value);

  switch (distances[0].edge) {
    case 'left':
      return { x: expanded.left, y: nextY, vx: -Math.abs(vx) * SURFACE_BOUNCE, vy: vy * SURFACE_VERTICAL_DRAG };
    case 'right':
      return { x: expanded.right, y: nextY, vx: Math.abs(vx) * SURFACE_BOUNCE, vy: vy * SURFACE_VERTICAL_DRAG };
    case 'top':
      return { x: nextX, y: expanded.top, vx: vx * SURFACE_VERTICAL_DRAG, vy: -Math.abs(vy) * FLOOR_BOUNCE };
    default:
      return { x: nextX, y: expanded.bottom, vx: vx * SURFACE_VERTICAL_DRAG, vy: Math.abs(vy) * FLOOR_BOUNCE };
  }
}

function burstStarsAt(cx, cy, count = 24) {
  if (!overlay) {
    return;
  }

  const surfaces = collectRicochetSurfaces();
  for (let i = 0; i < count; i += 1) {
    launchStar(cx, cy, surfaces);
  }
}

// Launch one star at (x0, y0) in viewport coordinates
// stars.js  (only the launchStar function has changed)

function launchStar(cx, cy, surfaces) {
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

    const previousX = cx + dx;
    const previousY = cy + dy;

    vy += GRAVITY * dt;   // accelerate downward
    dx += vx * dt;
    dy += vy * dt;

    /* ── absolute viewport coords (needed below) ───────── */
    let absX = cx + dx;
    let absY = cy + dy;

    for (const surface of surfaces) {
      const collision = resolveSurfaceCollision(previousX, previousY, absX, absY, vx, vy, surface);
      if (!collision) {
        continue;
      }

      absX = collision.x;
      absY = collision.y;
      dx = absX - cx;
      dy = absY - cy;
      vx = collision.vx;
      vy = collision.vy;

      if (Math.abs(vy) < 1) {
        vy = 0;
        vx *= 0.985;
        restingTime += dt;
        if (restingTime > 40) {
          fadeOutAndRemove(s);
          return;
        }
      } else {
        restingTime = 0;
      }

      break;
    }

      // ── NEW: colour based on current viewport coords ──
    // const normX = dx / window.innerWidth;       // 0 → 1
    // const normY = dy / window.innerHeight;      // 0 → 1
    // const hue  = normX * 720;                     // 2× colour wheel ⇒ faster change
    // const sat  = 60 + (1 - normY) * 40;           // 100 % high up → 60 % near bottom
    // const light = 50 + Math.pow(normY, 1.8) * 45; // starts 30 %, ends 75 %

    const speed = Math.hypot(vx, vy);            // px per frame
    const n = Math.min(speed / MAX_SPEED, 1);    // 0..1

    // slow → blue, fast → red; more saturation and slightly darker when fast
    const hue   = 240 - 240 * n;                 // 240=blue → 0=red
    const sat   = 60  + 40  * n;                 // 60% → 100%
    const light = 50  + 30  * n;                 // 70% → 40%

    s.style.backgroundColor = `hsl(${hue}, ${sat}%, ${light}%)`;

    s.style.backgroundColor = `hsl(${hue}, ${sat}%, ${light}%)`;

    // move only by the *change* since launch
    s.style.transform = `translate(${dx}px, ${dy}px) rotate(${t * 0.6}deg)`;

    if (cy + dy < window.innerHeight + 40) {
      requestAnimationFrame(frame);
    } else { fadeOutAndRemove(s); }
  }
  requestAnimationFrame(frame);
}


window.addEventListener("scoresheet:crown-stars", (event) => {
  const x = event?.detail?.x;
  const y = event?.detail?.y;

  if (typeof x !== 'number' || typeof y !== 'number') {
    return;
  }

  burstStarsAt(x, y);
});

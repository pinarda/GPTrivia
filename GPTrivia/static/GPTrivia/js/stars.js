// ─────────────────────────────────────────────
//  little physics helper
// ─────────────────────────────────────────────
const GRAVITY = 0.45;          // px per frame²
const FADE_MS = 300;           // fade-out time
const FLOOR_BOUNCE = 0.72;
const SURFACE_BOUNCE = 0.78;
const SURFACE_VERTICAL_DRAG = 0.96;
const AIR_DRAG = 0.997;
const SPIN_DRAG = 0.994;
const SPIN_TRANSFER = 1.15;
const COLLISION_SPIN_CARRY = 0.94;

const overlay = document.getElementById("star-overlay");
const MAX_SPEED = 25; // px/frame at which color hits "max"
const STAR_RADIUS = 5;
const STAR_COLLISION_RADIUS = 3.75;
const HORIZONTAL_COLLISION_PADDING = 1;

function fadeOutAndRemove(elem){
  elem.style.transition = `opacity ${FADE_MS}ms`;
  elem.style.opacity = 0;
  setTimeout(() => elem.remove(), FADE_MS);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function dot(ax, ay, bx, by) {
  return (ax * bx) + (ay * by);
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

  return (hue >= 90 && hue <= 190) || hue <= 22 || hue >= 338;
}

function hasRicochetBackground(style) {
  return isRicochetColor(style.backgroundColor);
}

function hasRicochetBorder(style) {
  return ['Top', 'Right', 'Bottom', 'Left'].some((side) => {
    const borderWidth = Number.parseFloat(style[`border${side}Width`]);
    if (!borderWidth) {
      return false;
    }
    return isRicochetColor(style[`border${side}Color`]);
  });
}

function hasRicochetSurface(style) {
  return hasRicochetBackground(style) || hasRicochetBorder(style);
}

function hasRicochetForeground(style) {
  return isRicochetColor(style.color);
}

function collectCollisionNodes(element) {
  const outlineCandidates = Array.from(
    element.querySelectorAll('.MuiOutlinedInput-notchedOutline')
  );
  if (outlineCandidates.length) {
    return outlineCandidates.map((node) => ({
      node,
      mode: 'surface',
    }));
  }

  if (element.classList?.contains('MuiCheckbox-root')) {
    const icon = element.querySelector('svg');
    if (icon) {
      return [{
        node: icon,
        mode: 'foreground',
        colorSource: element,
      }];
    }
  }

  return [{
    node: element,
    mode: 'surface',
  }];
}

function collectRicochetSurfaces() {
  const seen = new Set();
  const surfaces = [];
  const elements = document.querySelectorAll('.star-ricochet');

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

    const collisionNodes = collectCollisionNodes(element);

    for (const collisionCandidate of collisionNodes) {
      const collisionNode = collisionCandidate.node;
      const style = window.getComputedStyle(collisionNode);
      const colorSourceStyle = collisionCandidate.colorSource
        ? window.getComputedStyle(collisionCandidate.colorSource)
        : style;
      const isRicochetTarget = collisionCandidate.mode === 'foreground'
        ? hasRicochetForeground(colorSourceStyle)
        : hasRicochetSurface(style);
      if (
        style.display === 'none' ||
        style.visibility === 'hidden' ||
        Number.parseFloat(style.opacity) === 0 ||
        !isRicochetTarget
      ) {
        continue;
      }

      const rect = collisionNode.getBoundingClientRect();
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
  }

  return surfaces;
}

function resolveSurfaceCollision(previousX, previousY, nextX, nextY, vx, vy, angularVelocity, surface) {
  const expanded = {
    left: surface.left - HORIZONTAL_COLLISION_PADDING,
    right: surface.right + HORIZONTAL_COLLISION_PADDING,
    top: surface.top,
    bottom: surface.bottom,
  };

  const closestX = clamp(nextX, expanded.left, expanded.right);
  const closestY = clamp(nextY, expanded.top, expanded.bottom);
  let normalX = nextX - closestX;
  let normalY = nextY - closestY;
  const distanceSquared = (normalX * normalX) + (normalY * normalY);

  if (distanceSquared > STAR_COLLISION_RADIUS * STAR_COLLISION_RADIUS) {
    return null;
  }

  const EPSILON = 0.0001;
  if (distanceSquared > EPSILON) {
    const distance = Math.sqrt(distanceSquared);
    normalX /= distance;
    normalY /= distance;
  } else {
    const distances = [
      { normalX: -1, normalY: 0, value: Math.abs(nextX - expanded.left), previous: Math.abs(previousX - expanded.left) },
      { normalX: 1, normalY: 0, value: Math.abs(expanded.right - nextX), previous: Math.abs(expanded.right - previousX) },
      { normalX: 0, normalY: -1, value: Math.abs(nextY - expanded.top), previous: Math.abs(previousY - expanded.top) },
      { normalX: 0, normalY: 1, value: Math.abs(expanded.bottom - nextY), previous: Math.abs(expanded.bottom - previousY) },
    ].sort((left, right) => {
      if (left.value !== right.value) {
        return left.value - right.value;
      }
      return left.previous - right.previous;
    });

    normalX = distances[0].normalX;
    normalY = distances[0].normalY;
  }

  const correctedX = closestX + (normalX * STAR_COLLISION_RADIUS);
  const correctedY = closestY + (normalY * STAR_COLLISION_RADIUS);
  const tangentX = -normalY;
  const tangentY = normalX;
  const normalSpeed = dot(vx, vy, normalX, normalY);
  const tangentSpeed = dot(vx, vy, tangentX, tangentY);
  const restitution = Math.abs(normalY) > Math.abs(normalX) ? FLOOR_BOUNCE : SURFACE_BOUNCE;
  const bouncedNormalSpeed = normalSpeed < 0 ? (-normalSpeed * restitution) : Math.max(normalSpeed, 0);
  const nextTangentSpeed = tangentSpeed * SURFACE_VERTICAL_DRAG;
  const nextVx = (normalX * bouncedNormalSpeed) + (tangentX * nextTangentSpeed);
  const nextVy = (normalY * bouncedNormalSpeed) + (tangentY * nextTangentSpeed);
  const spinKick = clamp(tangentSpeed * SPIN_TRANSFER, -36, 36);

  return {
    x: correctedX,
    y: correctedY,
    vx: nextVx,
    vy: nextVy,
    angularVelocity: (angularVelocity * COLLISION_SPIN_CARRY) + spinKick,
    resting:
      Math.abs(bouncedNormalSpeed) < 0.8 &&
      Math.abs(nextTangentSpeed) < 1.5 &&
      Math.abs(normalY) > 0.45,
  };
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

function launchStar(cx, cy, surfaces) {
  const s = document.createElement("div");
  s.className = "star";

  s.style.left = `${cx}px`;
  s.style.top  = `${cy}px`;
  overlay.appendChild(s);

  let dx = 0, dy = 0;

  let vx = 2.75 + (Math.random() * 5.5);
  let vy = (Math.random() - 1.2) * 12;
  let angle = Math.random() * 360;
  const initialSpinMagnitude = 30 + (Math.random() * 40);
  let angularVelocity = (Math.random() < 0.5 ? -1 : 1) * initialSpinMagnitude;

  let last = performance.now();
  let restingTime = 0;
  function frame(t) {
    const dt = (t - last) / 16.7;
    last = t;

    const previousX = cx + dx;
    const previousY = cy + dy;

    vy += GRAVITY * dt;
    vx *= Math.pow(AIR_DRAG, dt);
    angularVelocity *= Math.pow(SPIN_DRAG, dt);
    dx += vx * dt;
    dy += vy * dt;
    angle += angularVelocity * dt;

    let absX = cx + dx;
    let absY = cy + dy;

    for (const surface of surfaces) {
      const collision = resolveSurfaceCollision(previousX, previousY, absX, absY, vx, vy, angularVelocity, surface);
      if (!collision) {
        continue;
      }

      absX = collision.x;
      absY = collision.y;
      dx = absX - cx;
      dy = absY - cy;
      vx = collision.vx;
      vy = collision.vy;
      angularVelocity = collision.angularVelocity;

      if (collision.resting) {
        vy = 0;
        vx *= 0.982;
        angularVelocity *= 0.96;
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

    const speed = Math.hypot(vx, vy);
    const n = Math.min(speed / MAX_SPEED, 1);

    const hue   = 240 - 240 * n;
    const sat   = 60  + 40  * n;
    const light = 50  + 30  * n;

    s.style.backgroundColor = `hsl(${hue}, ${sat}%, ${light}%)`;
    s.style.transform = `translate(${dx}px, ${dy}px) rotate(${angle}deg)`;

    if (cy + dy < window.innerHeight + 40) {
      requestAnimationFrame(frame);
    } else {
      fadeOutAndRemove(s);
    }
  }
  requestAnimationFrame(frame);
}

window.addEventListener("scoresheet:burst-stars", (event) => {
  const x = event?.detail?.x;
  const y = event?.detail?.y;

  if (typeof x !== 'number' || typeof y !== 'number') {
    return;
  }

  burstStarsAt(x, y);
});

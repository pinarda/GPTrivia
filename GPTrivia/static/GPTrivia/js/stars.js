const GRAVITY = 0.45;
const FADE_MS = 300;
const FLOOR_BOUNCE = 0.72;
const SURFACE_BOUNCE = 0.78;
const SURFACE_VERTICAL_DRAG = 0.96;

const overlay = document.getElementById("star-overlay");
const MAX_SPEED = 25;
const STAR_RADIUS = 5;

function fadeOutAndRemove(elem) {
  elem.style.transition = `opacity ${FADE_MS}ms`;
  elem.style.opacity = 0;
  setTimeout(() => elem.remove(), FADE_MS);
}

function parseRgb(color) {
  const match = String(color || "").match(/rgba?\(([^)]+)\)/i);
  if (!match) {
    return null;
  }

  const [r = 0, g = 0, b = 0, a = 1] = match[1]
    .split(",")
    .map((value) => Number.parseFloat(value.trim()));
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
  const elements = document.querySelectorAll("body *");

  for (const element of elements) {
    if (
      !element ||
      element === overlay ||
      element.classList?.contains("star") ||
      ["SCRIPT", "STYLE", "LINK", "META"].includes(element.tagName)
    ) {
      continue;
    }

    if (overlay && overlay.contains(element)) {
      continue;
    }

    const style = window.getComputedStyle(element);
    if (
      style.display === "none" ||
      style.visibility === "hidden" ||
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
    ].join(":");

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
    { edge: "left", value: Math.abs(nextX - expanded.left) },
    { edge: "right", value: Math.abs(nextX - expanded.right) },
    { edge: "top", value: Math.abs(nextY - expanded.top) },
    { edge: "bottom", value: Math.abs(nextY - expanded.bottom) },
  ].sort((left, right) => left.value - right.value);

  switch (distances[0].edge) {
    case "left":
      return {
        x: expanded.left,
        y: nextY,
        vx: -Math.abs(vx) * SURFACE_BOUNCE,
        vy: vy * SURFACE_VERTICAL_DRAG,
      };
    case "right":
      return {
        x: expanded.right,
        y: nextY,
        vx: Math.abs(vx) * SURFACE_BOUNCE,
        vy: vy * SURFACE_VERTICAL_DRAG,
      };
    case "top":
      return {
        x: nextX,
        y: expanded.top,
        vx: vx * SURFACE_VERTICAL_DRAG,
        vy: -Math.abs(vy) * FLOOR_BOUNCE,
      };
    default:
      return {
        x: nextX,
        y: expanded.bottom,
        vx: vx * SURFACE_VERTICAL_DRAG,
        vy: Math.abs(vy) * FLOOR_BOUNCE,
      };
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

function launchStar(cx, cy, surfaces) {
  const star = document.createElement("div");
  star.className = "star";
  star.style.left = `${cx}px`;
  star.style.top = `${cy}px`;
  overlay.appendChild(star);

  let dx = 0;
  let dy = 0;
  let vx = (Math.random() - 0.5) * 8;
  let vy = (Math.random() - 1.2) * 12;

  let last = performance.now();
  let restingTime = 0;

  function frame(t) {
    const dt = (t - last) / 16.7;
    last = t;

    const previousX = cx + dx;
    const previousY = cy + dy;

    vy += GRAVITY * dt;
    dx += vx * dt;
    dy += vy * dt;

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
          fadeOutAndRemove(star);
          return;
        }
      } else {
        restingTime = 0;
      }

      break;
    }

    const speed = Math.hypot(vx, vy);
    const normalizedSpeed = Math.min(speed / MAX_SPEED, 1);
    const hue = 240 - 240 * normalizedSpeed;
    const saturation = 60 + 40 * normalizedSpeed;
    const lightness = 50 + 30 * normalizedSpeed;

    star.style.backgroundColor = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
    star.style.transform = `translate(${dx}px, ${dy}px) rotate(${t * 0.6}deg)`;

    if (cy + dy < window.innerHeight + 40) {
      requestAnimationFrame(frame);
    } else {
      fadeOutAndRemove(star);
    }
  }

  requestAnimationFrame(frame);
}

window.addEventListener("scoresheet:burst-stars", (event) => {
  const x = event?.detail?.x;
  const y = event?.detail?.y;

  if (typeof x !== "number" || typeof y !== "number") {
    return;
  }

  burstStarsAt(x, y);
});

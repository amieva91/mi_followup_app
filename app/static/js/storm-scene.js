/**
 * Auðr storm scene — vanilla port of StormScene.tsx
 * Expects a root element with data-storm-scene (or #storm-scene).
 */
(function () {
  'use strict';

  function boltSegment(x, y, length, segments, spread) {
    const points = [[x, y]];
    let cx = x;
    let cy = y;
    const step = length / segments;
    for (let i = 0; i < segments; i += 1) {
      cx += (Math.random() - 0.5) * spread;
      cy += step * (0.85 + Math.random() * 0.3);
      points.push([cx, cy]);
    }
    return points;
  }

  function pointsToPath(points) {
    return points
      .map(function (p, i) {
        return (i === 0 ? 'M' : 'L') + ' ' + p[0].toFixed(1) + ' ' + p[1].toFixed(1);
      })
      .join(' ');
  }

  function buildLightningBolt(width, height) {
    const originX = width * (0.38 + Math.random() * 0.24);
    const main = boltSegment(
      originX,
      -12,
      height * (0.55 + Math.random() * 0.2),
      9 + Math.floor(Math.random() * 4),
      width * 0.09
    );
    const paths = [
      { cls: 'storm-bolt-main', d: pointsToPath(main) },
      { cls: 'storm-bolt-core', d: pointsToPath(main) },
    ];

    const branchCount = 1 + Math.floor(Math.random() * 2);
    for (let b = 0; b < branchCount; b += 1) {
      const idx = 2 + Math.floor(Math.random() * (main.length - 4));
      const start = main[idx];
      const dir = Math.random() > 0.5 ? 1 : -1;
      const branch = boltSegment(
        start[0],
        start[1],
        height * (0.12 + Math.random() * 0.12),
        4 + Math.floor(Math.random() * 2),
        width * 0.05 * dir
      );
      paths.push({ cls: 'storm-bolt-branch', d: pointsToPath(branch) });
    }
    return { originX: originX, paths: paths, width: width, height: height };
  }

  function initStormScene(scene) {
    const canvas = scene.querySelector('[data-storm-rain]');
    const seaGlow = scene.querySelector('[data-storm-sea-glow]');
    const sea = scene.querySelector('[data-storm-sea]');
    const shipWrap = scene.querySelector('[data-storm-ship-wrap]');
    const lightningLayer = scene.querySelector('[data-storm-lightning]');
    if (!canvas || !lightningLayer) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let drops = [];
    let rainFrame = 0;
    let cancelled = false;
    let strikeTimeout = 0;
    let flashEl = null;
    let boltSvg = null;

    function resizeRain() {
      const rect = scene.getBoundingClientRect();
      canvas.width = Math.floor(rect.width);
      canvas.height = Math.floor(rect.height);
      const count = Math.floor((canvas.width * canvas.height) / 9000);
      const n = Math.min(260, Math.max(120, count));
      drops = [];
      for (let i = 0; i < n; i += 1) {
        drops.push({
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height,
          len: Math.random() * 18 + 8,
          speed: Math.random() * 5 + 6,
          opacity: Math.random() * 0.25 + 0.12,
        });
      }
    }

    function drawRain() {
      if (cancelled) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < drops.length; i += 1) {
        const d = drops[i];
        ctx.strokeStyle = 'rgba(190, 210, 230, ' + d.opacity + ')';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(d.x, d.y);
        ctx.lineTo(d.x - 1.2, d.y + d.len);
        ctx.stroke();
        d.y += d.speed;
        d.x -= 0.7;
        if (d.y > canvas.height) {
          d.y = -d.len;
          d.x = Math.random() * canvas.width;
        }
      }
      rainFrame = requestAnimationFrame(drawRain);
    }

    function clearBolt() {
      if (flashEl) {
        flashEl.remove();
        flashEl = null;
      }
      if (boltSvg) {
        boltSvg.remove();
        boltSvg = null;
      }
      if (sea) sea.removeAttribute('data-lit');
      if (shipWrap) shipWrap.removeAttribute('data-lightning');
    }

    function setBoltActive(active) {
      if (flashEl) flashEl.classList.toggle('is-active', active);
      if (boltSvg) boltSvg.classList.toggle('is-active', active);
    }

    function strike() {
      if (cancelled) return;
      const rect = scene.getBoundingClientRect();
      const built = buildLightningBolt(rect.width, rect.height);
      const lx = (built.originX / rect.width) * 100 + '%';
      if (seaGlow) seaGlow.style.setProperty('--lx', lx);

      clearBolt();

      flashEl = document.createElement('div');
      flashEl.className = 'storm-lightning-flash';
      flashEl.style.setProperty('--lx', lx);

      boltSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      boltSvg.setAttribute('class', 'storm-lightning-bolt');
      boltSvg.setAttribute('viewBox', '0 0 ' + built.width + ' ' + built.height);
      boltSvg.setAttribute('preserveAspectRatio', 'none');
      for (let i = 0; i < built.paths.length; i += 1) {
        const p = built.paths[i];
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('class', p.cls);
        path.setAttribute('d', p.d);
        boltSvg.appendChild(path);
      }

      lightningLayer.appendChild(flashEl);
      lightningLayer.appendChild(boltSvg);

      if (sea) sea.setAttribute('data-lit', 'true');
      if (shipWrap) shipWrap.setAttribute('data-lightning', 'true');

      requestAnimationFrame(function () {
        setBoltActive(true);
      });

      const duration = 100 + Math.random() * 180;
      const flicker = Math.random() > 0.55;

      window.setTimeout(function () {
        if (flicker) {
          setBoltActive(false);
          window.setTimeout(function () {
            setBoltActive(true);
          }, 40);
        }
      }, duration * 0.45);

      window.setTimeout(function () {
        setBoltActive(false);
        if (sea) sea.removeAttribute('data-lit');
        if (shipWrap) shipWrap.removeAttribute('data-lightning');
        window.setTimeout(clearBolt, 200);
      }, duration + (flicker ? 60 : 0));

      strikeTimeout = window.setTimeout(strike, 3200 + Math.random() * 7500);
    }

    resizeRain();
    drawRain();
    window.addEventListener('resize', resizeRain);
    strikeTimeout = window.setTimeout(strike, 1600);

    return function destroy() {
      cancelled = true;
      cancelAnimationFrame(rainFrame);
      window.removeEventListener('resize', resizeRain);
      window.clearTimeout(strikeTimeout);
      clearBolt();
    };
  }

  function boot() {
    const scenes = document.querySelectorAll('[data-storm-scene]');
    for (let i = 0; i < scenes.length; i += 1) {
      initStormScene(scenes[i]);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

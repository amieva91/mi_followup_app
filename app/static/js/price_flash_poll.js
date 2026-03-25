/**
 * Polling ligero para efecto flash en celdas .price-cell[data-asset-id].
 * Requiere window.__priceUpdatesUrl (URL de /api/price-updates).
 */
(function () {
  var url = typeof window.__priceUpdatesUrl === 'string' ? window.__priceUpdatesUrl : '';
  if (!url) return;

  var lastSince = null;
  var intervalMs = 30000;
  var view = typeof window.__priceUpdatesView === 'string' ? window.__priceUpdatesView : '';
  var pollInFlight = false;
  /** @type {WeakMap<Element, { tid: number, onEnd: function(Event): void }>} */
  var cssFlashCleanup = new WeakMap();
  /** @type {WeakMap<Element, Animation>} */
  var wapiFlashByEl = new WeakMap();

  function setCellText(el, text) {
    var kids = el.children;
    if (
      kids.length === 1 &&
      (kids[0].tagName === 'SPAN' || kids[0].tagName === 'DIV')
    ) {
      kids[0].textContent = text;
      return;
    }
    el.textContent = text;
  }

  function fmt1(n) {
    if (n == null || Number.isNaN(Number(n))) return '—';
    return Number(n).toFixed(1);
  }

  function setCryptoMetalesPlCell(el, u) {
    if (u.pl_eur == null) return;
    var sign = Number(u.pl_eur) >= 0 ? '+' : '';
    var main = sign + fmt2(u.pl_eur) + ' €';
    if (u.pl_pct == null || Number.isNaN(Number(u.pl_pct))) {
      el.textContent = main;
      return;
    }
    var ps = Number(u.pl_pct) >= 0 ? '+' : '';
    el.innerHTML =
      main +
      ' <span class="text-xs">(' +
      ps +
      fmt1(u.pl_pct) +
      '%)</span>';
  }

  function clearFlash(el) {
    el.classList.remove('price-updated');
    el.style.removeProperty('background-color');
  }

  function cancelPendingFlash(el) {
    var prevCss = cssFlashCleanup.get(el);
    if (prevCss) {
      clearTimeout(prevCss.tid);
      el.removeEventListener('animationend', prevCss.onEnd);
      cssFlashCleanup.delete(el);
    }
    var prevAnim = wapiFlashByEl.get(el);
    if (prevAnim && typeof prevAnim.cancel === 'function') {
      try {
        prevAnim.cancel();
      } catch (e) {}
      wapiFlashByEl.delete(el);
    }
  }

  function flashOneCell(el) {
    cancelPendingFlash(el);
    clearFlash(el);

    if (typeof el.animate === 'function') {
      var anim = el.animate(
        [
          { backgroundColor: 'rgba(34, 197, 94, 0.35)' },
          { backgroundColor: 'rgba(34, 197, 94, 0)' },
        ],
        { duration: 600, easing: 'ease-out', fill: 'none' }
      );
      wapiFlashByEl.set(el, anim);
      anim.finished
        .then(function () {
          if (wapiFlashByEl.get(el) === anim) wapiFlashByEl.delete(el);
          el.style.removeProperty('background-color');
        })
        .catch(function () {
          if (wapiFlashByEl.get(el) === anim) wapiFlashByEl.delete(el);
          el.style.removeProperty('background-color');
        });
      return;
    }

    void el.offsetWidth;
    el.classList.add('price-updated');
    function onEnd(e) {
      var name = String(e.animationName || '');
      if (name.indexOf('followup-price-flash') === -1) return;
      el.removeEventListener('animationend', onEnd);
      clearTimeout(tid);
      cssFlashCleanup.delete(el);
      clearFlash(el);
    }
    var tid = window.setTimeout(function () {
      el.removeEventListener('animationend', onEnd);
      cssFlashCleanup.delete(el);
      clearFlash(el);
    }, 900);
    cssFlashCleanup.set(el, { tid: tid, onEnd: onEnd });
    el.addEventListener('animationend', onEnd);
  }

  function flashCells(assetIds) {
    if (!assetIds || !assetIds.length) return;
    var ids = new Set(assetIds.map(String));
    document.querySelectorAll('.price-cell[data-asset-id]').forEach(function (el) {
      if (!ids.has(String(el.getAttribute('data-asset-id')))) return;
      flashOneCell(el);
    });
  }

  function poll() {
    if (pollInFlight) return;
    pollInFlight = true;
    var u = url;
    var qs = [];
    if (lastSince) {
      qs.push('since=' + encodeURIComponent(lastSince));
    }
    if (view) qs.push('view=' + encodeURIComponent(view));
    if (qs.length) u += (u.indexOf('?') >= 0 ? '&' : '?') + qs.join('&');
    fetch(u, { credentials: 'same-origin' })
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (!data) return;
        if (data.server_now) lastSince = data.server_now;
        // Primero repintar valores; si el flash corre antes y luego se toca el TD,
        // algunos navegadores dejan el fondo verde “pegado”.
        if (data.updates && typeof data.updates === 'object') {
          applyUpdates(data.updates);
        }
        if (Array.isArray(data.updated_asset_ids) && data.updated_asset_ids.length) {
          requestAnimationFrame(function () {
            flashCells(data.updated_asset_ids);
          });
        }
      })
      .catch(function () {})
      .finally(function () {
        pollInFlight = false;
      });
  }

  function fmt2(n) {
    if (n == null || Number.isNaN(Number(n))) return '—';
    return Number(n).toFixed(2);
  }

  function applyUpdates(updates) {
    // Busca celdas con data-asset-id y data-field y actualiza su texto.
    Object.keys(updates).forEach(function (aid) {
      var u = updates[aid] || {};
      document.querySelectorAll('.price-cell[data-asset-id=\"' + aid + '\"][data-field]').forEach(function (el) {
        var field = el.getAttribute('data-field');
        if (view === 'watchlist' && field === 'price') {
          setCellText(el, u.price_local != null ? fmt2(u.price_local) + ' ' + (u.currency || '') : '—');
        } else if ((view === 'portfolio' || view === 'holdings') && field === 'price') {
          setCellText(el, u.price_local != null ? fmt2(u.price_local) + ' ' + (u.currency || '') : '—');
        } else if ((view === 'portfolio' || view === 'holdings') && field === 'value') {
          var vtxt =
            u.value_eur != null ? fmt2(u.value_eur) + ' EUR' : '—';
          var vdiv = el.querySelector('div.text-sm.font-medium');
          if (vdiv) vdiv.textContent = vtxt;
          else setCellText(el, vtxt);
        } else if ((view === 'portfolio' || view === 'holdings') && field === 'pl') {
          if (u.pl_eur == null) return;
          var sign = Number(u.pl_eur) >= 0 ? '+' : '';
          setCellText(el, sign + fmt2(u.pl_eur) + ' EUR');
        } else if (view === 'crypto') {
          if (field === 'price') setCellText(el, u.price_eur != null ? fmt2(u.price_eur) + ' €' : '—');
          if (field === 'value') setCellText(el, u.value_eur != null ? fmt2(u.value_eur) + ' €' : '—');
          if (field === 'pl') setCryptoMetalesPlCell(el, u);
        } else if (view === 'metales') {
          if (field === 'price') setCellText(el, u.price_eur_oz != null ? fmt2(u.price_eur_oz) : '—');
          if (field === 'value') setCellText(el, u.value_eur != null ? fmt2(u.value_eur) + ' €' : '—');
          if (field === 'pl') setCryptoMetalesPlCell(el, u);
        }
      });
    });
  }

  poll();
  setInterval(poll, intervalMs);
})();

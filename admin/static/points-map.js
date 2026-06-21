/* global L */
(function () {
  const YAROSLAVL = [57.622, 39.872];

  function fmtCoord(n) {
    return Number(n).toFixed(6);
  }

  function syncInputs(marker, latInput, lngInput) {
    const ll = marker.getLatLng();
    if (latInput) latInput.value = fmtCoord(ll.lat);
    if (lngInput) lngInput.value = fmtCoord(ll.lng);
  }

  function showToast(toastEl, text, kind) {
    if (!toastEl) return;
    toastEl.textContent = text;
    toastEl.hidden = false;
    toastEl.classList.remove("ok", "err");
    if (kind) toastEl.classList.add(kind);
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () {
      toastEl.hidden = true;
    }, 2600);
  }

  async function saveCoordinates(saveUrl, lat, lng, toastEl) {
    const resp = await fetch(saveUrl, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: lat, longitude: lng }),
    });
    const data = await resp.json().catch(function () {
      return { ok: false, error: "Некорректный ответ сервера" };
    });
    if (!resp.ok || !data.ok) {
      showToast(toastEl, data.error || "Не удалось сохранить", "err");
      return false;
    }
    showToast(toastEl, "Координаты сохранены", "ok");
    return true;
  }

  function makeIcon(saved) {
    return L.divIcon({
      className: saved ? "yaride-marker yaride-marker--saved" : "yaride-marker yaride-marker--draft",
      html: '<span></span>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    });
  }

  function initSinglePointMap(opts) {
    const container = document.getElementById(opts.containerId);
    if (!container || typeof L === "undefined") return;

    const latInput = document.getElementById(opts.latInputId);
    const lngInput = document.getElementById(opts.lngInputId);
    const lat = latInput && latInput.value ? parseFloat(latInput.value) : opts.lat;
    const lng = lngInput && lngInput.value ? parseFloat(lngInput.value) : opts.lng;

    const map = L.map(container, { scrollWheelZoom: true }).setView([lat, lng], opts.saved ? 15 : 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);
    if (map.attributionControl) {
      map.attributionControl.setPrefix(false);
    }

    const marker = L.marker([lat, lng], {
      draggable: true,
      icon: makeIcon(opts.saved),
    }).addTo(map);

    marker.on("drag", function () {
      syncInputs(marker, latInput, lngInput);
    });

    marker.on("dragend", async function () {
      syncInputs(marker, latInput, lngInput);
      if (!opts.saveUrl) return;
      const ll = marker.getLatLng();
      const ok = await saveCoordinates(opts.saveUrl, ll.lat, ll.lng, null);
      if (ok) {
        marker.setIcon(makeIcon(true));
      }
    });

    if (latInput && lngInput) {
      function applyFromInputs() {
        const la = parseFloat(latInput.value);
        const ln = parseFloat(lngInput.value);
        if (Number.isFinite(la) && Number.isFinite(ln)) {
          marker.setLatLng([la, ln]);
          map.panTo([la, ln]);
        }
      }
      latInput.addEventListener("change", applyFromInputs);
      lngInput.addEventListener("change", applyFromInputs);
    }
  }

  function initBulkMap(opts) {
    const container = document.getElementById(opts.containerId);
    const listEl = document.getElementById(opts.listId);
    const toastEl = document.getElementById(opts.toastId);
    if (!container || typeof L === "undefined") return;

    const stops = opts.stops || [];
    const markers = new Map();

    const map = L.map(container, { scrollWheelZoom: true }).setView(YAROSLAVL, 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);
    if (map.attributionControl) {
      map.attributionControl.setPrefix(false);
    }

    const bounds = [];

    stops.forEach(function (stop) {
      if (listEl) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "map-sidebar-item" + (stop.saved ? "" : " unsaved");
        btn.dataset.id = String(stop.id);
        btn.innerHTML =
          '<div class="title">' +
          escapeHtml(stop.title) +
          '</div><div class="meta">#' +
          stop.id +
          (stop.district ? " · " + escapeHtml(stop.district) : "") +
          "</div>";
        btn.addEventListener("click", function () {
          focusStop(stop.id);
        });
        listEl.appendChild(btn);
      }

      const marker = L.marker([stop.latitude, stop.longitude], {
        draggable: true,
        icon: makeIcon(stop.saved),
        title: stop.title,
      }).addTo(map);

      marker.bindPopup(
        "<strong>" +
          escapeHtml(stop.title) +
          "</strong><br>#" +
          stop.id +
          "<br><small>" +
          fmtCoord(stop.latitude) +
          ", " +
          fmtCoord(stop.longitude) +
          "</small>"
      );

      marker.on("dragend", async function () {
        const ll = marker.getLatLng();
        const saveUrl = "/points/" + stop.id + "/coordinates";
        const ok = await saveCoordinates(saveUrl, ll.lat, ll.lng, toastEl);
        if (ok) {
          stop.saved = true;
          stop.latitude = ll.lat;
          stop.longitude = ll.lng;
          marker.setIcon(makeIcon(true));
          marker.setPopupContent(
            "<strong>" +
              escapeHtml(stop.title) +
              "</strong><br>#" +
              stop.id +
              "<br><small>" +
              fmtCoord(ll.lat) +
              ", " +
              fmtCoord(ll.lng) +
              "</small>"
          );
          const item = listEl && listEl.querySelector('[data-id="' + stop.id + '"]');
          if (item) item.classList.remove("unsaved");
        }
      });

      markers.set(stop.id, marker);
      bounds.push([stop.latitude, stop.longitude]);
    });

    if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: 14 });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 14);
    }

    function focusStop(id) {
      const marker = markers.get(id);
      if (!marker) return;
      map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15));
      marker.openPopup();
      if (listEl) {
        listEl.querySelectorAll(".map-sidebar-item").forEach(function (el) {
          el.classList.toggle("on", el.dataset.id === String(id));
        });
        const active = listEl.querySelector('[data-id="' + id + '"]');
        if (active) active.scrollIntoView({ block: "nearest" });
      }
    }

    if (opts.focusId) {
      focusStop(opts.focusId);
    }
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  window.YaridePointsMap = {
    initSinglePointMap: initSinglePointMap,
    initBulkMap: initBulkMap,
  };
})();

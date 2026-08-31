(function () {
  "use strict";

  var DB_NAME = "hausmeister";
  var STORE = "queue";

  function toast(message, isError) {
    var el = document.getElementById("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("error", Boolean(isError));
    el.classList.remove("hidden");
    clearTimeout(el._timer);
    el._timer = setTimeout(function () {
      el.classList.add("hidden");
    }, 4000);
  }

  function openQueue() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
        }
      };
      req.onsuccess = function () {
        resolve(req.result);
      };
      req.onerror = function () {
        reject(req.error);
      };
    });
  }

  function queueAdd(entry) {
    return openQueue().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).add(entry);
        tx.oncomplete = function () {
          resolve();
        };
        tx.onerror = function () {
          reject(tx.error);
        };
      });
    });
  }

  function pendingCount() {
    return openQueue().then(function (db) {
      return new Promise(function (resolve) {
        var tx = db.transaction(STORE, "readonly");
        var req = tx.objectStore(STORE).count();
        req.onsuccess = function () {
          resolve(req.result);
        };
        req.onerror = function () {
          resolve(0);
        };
      });
    });
  }

  function registerSync() {
    if (!navigator.serviceWorker || !navigator.serviceWorker.controller) return;
    navigator.serviceWorker.controller.postMessage({ type: "replay-queue" });
    if ("sync" in navigator.serviceWorker) {
      navigator.serviceWorker.ready
        .then(function (reg) {
          return reg.sync.register("hausmeister-sync");
        })
        .catch(function () {});
    }
  }

  function markPending(instanceId, label) {
    var btn = document.querySelector(
      '[data-action][data-instance="' + instanceId + '"]'
    );
    if (btn) {
      btn.disabled = true;
      btn.textContent = label;
    }
  }

  function completeInstance(instanceId) {
    var url = "/api/maintenance/instances/" + instanceId + "/complete";
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note: null }),
    }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return true;
    });
  }

  function skipInstance(instanceId) {
    var url = "/api/maintenance/instances/" + instanceId + "/skip";
    return fetch(url, { method: "POST" }).then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return true;
    });
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = window.atob(base64);
    var arr = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  function subscribePush() {
    var btn = document.getElementById("push-subscribe");
    var key = btn ? btn.getAttribute("data-vapid-key") : "";
    if (!btn || !key) return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      toast("Push wird von diesem Browser nicht unterstützt.", true);
      return;
    }
    Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") {
        toast("Benachrichtigungen wurden nicht erlaubt.", true);
        return;
      }
      navigator.serviceWorker.ready
        .then(function (reg) {
          return reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(key),
          });
        })
        .then(function (sub) {
          return fetch("/api/settings/push/subscribe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              endpoint: sub.endpoint,
              keys: sub.toJSON().keys,
              user_agent: navigator.userAgent,
            }),
          });
        })
        .then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          toast("Push aktiviert.");
        })
        .catch(function () {
          toast("Push-Aktivierung fehlgeschlagen. Zertifikat bestätigt?", true);
        });
    });
  }

  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-action]");
    if (!btn) return;
    var action = btn.getAttribute("data-action");
    if (action === "push-subscribe") {
      event.preventDefault();
      subscribePush();
      return;
    }
    if (action === "push-test") {
      event.preventDefault();
      fetch("/api/settings/push/test", { method: "POST" })
        .then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          toast("Test-Push versendet.");
        })
        .catch(function () {
          toast("Test-Push fehlgeschlagen.", true);
        });
      return;
    }
    var instanceId = btn.getAttribute("data-instance");
    if (!instanceId) return;
    if (action === "complete") {
      event.preventDefault();
      completeInstance(instanceId)
        .then(function () {
          window.location.reload();
        })
        .catch(function () {
          queueAdd({
            url: "/api/maintenance/instances/" + instanceId + "/complete",
            body: { note: null },
            ts: Date.now(),
          })
            .then(function () {
              registerSync();
              markPending(instanceId, "Offline gespeichert");
              toast("Offline gespeichert – wird automatisch synchronisiert.");
            })
            .catch(function () {
              toast("Speichern fehlgeschlagen.", true);
            });
        });
    } else if (action === "skip") {
      event.preventDefault();
      skipInstance(instanceId)
        .then(function () {
          window.location.reload();
        })
        .catch(function () {
          toast("Überspringen fehlgeschlagen (offline?).", true);
        });
    }
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      if (window.location.protocol !== "https:") return;
      navigator.serviceWorker.register("/static/sw.js").then(function () {
        pendingCount().then(function (count) {
          if (count > 0) {
            registerSync();
            toast(count + " offline-Aktion(en) werden synchronisiert.");
          }
        });
      });
    });
    navigator.serviceWorker.addEventListener("message", function (event) {
      if (event.data && event.data.type === "queue-synced") {
        window.location.reload();
      }
    });
  }

  var form = document.querySelector(".form");
  if (form) {
    var typeSelect = document.getElementById("schedule-type");
    if (typeSelect) {
      var syncFields = function () {
        var value = typeSelect.value;
        document.querySelectorAll(".schedule-field").forEach(function (el) {
          el.style.display = el.getAttribute("data-show") === value ? "" : "none";
        });
      };
      typeSelect.addEventListener("change", syncFields);
      syncFields();
    }
  }
})();

// Offline-Warteschlange (IndexedDB): Fehlgeschlagene "Erledigt"-Aktionen
// werden gespeichert und vom Service Worker später nachgespielt – identisch
// zur bisherigen Logik, nur ohne Reload-Zwang.

const DB_NAME = "hausmeister";
const STORE = "queue";

function openQueue() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export function queueAdd(entry) {
  return openQueue().then(
    (db) =>
      new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).add(entry);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      })
  );
}

export function pendingCount() {
  return openQueue()
    .then(
      (db) =>
        new Promise((resolve) => {
          const tx = db.transaction(STORE, "readonly");
          const req = tx.objectStore(STORE).count();
          req.onsuccess = () => resolve(req.result);
          req.onerror = () => resolve(0);
        })
    )
    .catch(() => 0);
}

export function registerSync() {
  if (!navigator.serviceWorker || !navigator.serviceWorker.controller) return;
  navigator.serviceWorker.controller.postMessage({ type: "replay-queue" });
  if ("sync" in navigator.serviceWorker) {
    navigator.serviceWorker.ready
      .then((reg) => reg.sync.register("hausmeister-sync"))
      .catch(() => {});
  }
}

export function registerServiceWorker(onQueueSynced) {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    if (window.location.protocol !== "https:") return;
    navigator.serviceWorker.register("/sw.js").then(() => {
      pendingCount().then((count) => {
        if (count > 0) {
          registerSync();
          onQueueSynced && onQueueSynced(count);
        }
      });
    });
  });
  navigator.serviceWorker.addEventListener("message", (event) => {
    if (event.data && event.data.type === "queue-synced") {
      onQueueSynced && onQueueSynced(0, true);
    }
  });
}

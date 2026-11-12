import { createContext, useCallback, useContext, useState } from "react";
import { api } from "./api.js";
import { queueAdd, registerSync } from "./offline.js";
import { useToast } from "./toast.jsx";

// Zentrale Aktionen "Erledigt"/"Überspringen": online direkt per API, offline
// in der IndexedDB-Warteschlange gespeichert (Service Worker spielt später nach).
const CompleteContext = createContext({ complete: async () => {}, skip: async () => {}, dataVersion: 0, bump: () => {} });

export function CompleteProvider({ children }) {
  const showToast = useToast();
  const [dataVersion, setDataVersion] = useState(0);
  const bump = useCallback(() => setDataVersion((v) => v + 1), []);

  const complete = useCallback(
    async (instanceId) => {
      try {
        await api.post(`/api/maintenance/instances/${instanceId}/complete`, {});
        showToast("Erledigt ✓");
        bump();
      } catch (err) {
        try {
          await queueAdd({
            url: `/api/maintenance/instances/${instanceId}/complete`,
            body: { note: null },
            ts: Date.now(),
          });
          registerSync();
          showToast("Offline gespeichert – wird automatisch synchronisiert.");
          bump();
        } catch (queueErr) {
          showToast("Speichern fehlgeschlagen: " + err.message, true);
        }
      }
    },
    [showToast, bump]
  );

  const skip = useCallback(
    async (instanceId) => {
      try {
        await api.post(`/api/maintenance/instances/${instanceId}/skip`);
        showToast("Übersprungen.");
        bump();
      } catch (err) {
        showToast("Überspringen fehlgeschlagen (offline?): " + err.message, true);
      }
    },
    [showToast, bump]
  );

  return (
    <CompleteContext.Provider value={{ complete, skip, dataVersion, bump }}>
      {children}
    </CompleteContext.Provider>
  );
}

export function useCompleteActions() {
  return useContext(CompleteContext);
}

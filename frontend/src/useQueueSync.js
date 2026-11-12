import { useEffect, useState } from "react";
import { useCompleteActions } from "./complete.jsx";

// Liefert einen Key, der sich ändert, wenn Daten neu geladen werden sollten:
// nach Erledigt/Überspringen (dataVersion) oder nach einer Queue-Synchronisation.
export function useReloadKey() {
  const { dataVersion } = useCompleteActions();
  const [syncTick, setSyncTick] = useState(0);
  useEffect(() => {
    const handler = () => setSyncTick((t) => t + 1);
    window.addEventListener("hausmeister:queuesynced", handler);
    return () => window.removeEventListener("hausmeister:queuesynced", handler);
  }, []);
  return dataVersion + syncTick;
}

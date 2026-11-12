import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { ToastProvider } from "./toast.jsx";
import { CompleteProvider } from "./complete.jsx";
import { registerServiceWorker } from "./offline.js";
import "./styles.css";

registerServiceWorker((count, synced) => {
  // Nach einer Queue-Synchronisation lädt die Dashboard-/Plan-Seite ihre
  // Daten neu (CompleteProvider.bump triggert über dataVersion).
  window.dispatchEvent(new CustomEvent("hausmeister:queuesynced", { detail: { count, synced } }));
});

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <CompleteProvider>
          <App />
        </CompleteProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>
);

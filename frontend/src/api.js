// Dünner Fetch-Wrapper: FastAPI-Fehler ({detail: string|list}) in lesbare
// Meldungen umwandeln, damit die UI sie direkt als Toast zeigen kann.

async function request(method, url, body, isForm) {
  const options = { method, headers: {} };
  if (body !== undefined && !isForm) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  } else if (body !== undefined && isForm) {
    options.body = body; // FormData
  }
  const res = await fetch(url, options);
  if (res.status === 204) return null;
  let data = null;
  try {
    data = await res.json();
  } catch (err) {
    data = null;
  }
  if (!res.ok) {
    let detail = data && data.detail ? data.detail : `HTTP ${res.status}`;
    if (Array.isArray(detail)) {
      // Validierungsfehler: ["Fehler 1", "Fehler 2"] oder Pydantic-Objekte
      detail = detail
        .map((d) => (typeof d === "string" ? d : d.msg || JSON.stringify(d)))
        .join(" · ");
    } else if (detail && typeof detail === "object") {
      detail = detail.msg || JSON.stringify(detail);
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }
  return data;
}

export const api = {
  get: (url) => request("GET", url),
  post: (url, body) => request("POST", url, body),
  put: (url, body) => request("PUT", url, body),
  del: (url) => request("DELETE", url),
  postForm: (url, formData) => request("POST", url, formData, true),
};

export const AREA_ICONS = {
  haus: "🏠",
  hof: "🧰",
  technik: "⚙️",
  garten: "🌿",
  sicherheit: "🛡️",
};

export const PRIORITY_LABELS = {
  high: "⚡ Wichtig",
  normal: "⏱ Empfohlen",
  low: "📌 Optional",
};

export const MONTH_NAMES = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

export const MONTH_SHORT = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

export function formatDate(dateStr) {
  if (!dateStr) return "—";
  const [y, m, d] = dateStr.split("-");
  return `${d}.${m}.${y}`;
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

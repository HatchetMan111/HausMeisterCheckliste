import { Link, NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import Jahresplan from "./pages/Jahresplan.jsx";
import Tasks from "./pages/Tasks.jsx";
import TaskForm from "./pages/TaskForm.jsx";
import History from "./pages/History.jsx";
import Settings from "./pages/Settings.jsx";
import CertificateHelp from "./pages/CertificateHelp.jsx";

const NAV = [
  { to: "/", label: "Übersicht", end: true },
  { to: "/jahresplan", label: "Jahresplan" },
  { to: "/tasks", label: "Aufgaben" },
  { to: "/history", label: "Verlauf" },
  { to: "/settings", label: "Einstellungen" },
  { to: "/help/certificate", label: "Hilfe" },
];

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to="/">
          <img src="/static/icons/icon-192.png" alt="" className="brand-icon" />
          Hausmeister
        </Link>
        <nav className="topnav">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/jahresplan" element={<Jahresplan />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/tasks/new" element={<TaskForm />} />
          <Route path="/tasks/:id/edit" element={<TaskForm />} />
          <Route path="/history" element={<History />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/help/certificate" element={<CertificateHelp />} />
          <Route path="*" element={<Dashboard />} />
        </Routes>
      </main>
      <footer>
        <span>Hausmeister – lokale Wartungsplanung</span>
        <span><Link to="/help/certificate">Zertifikat einrichten</Link></span>
      </footer>
    </div>
  );
}

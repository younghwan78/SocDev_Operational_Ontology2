import { Link, Navigate, Route, Routes } from "react-router-dom";
import { ko } from "./i18n/ko";
import { ScenarioDetailPage } from "./pages/ScenarioDetailPage";
import { ScenarioListPage } from "./pages/ScenarioListPage";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/scenarios" className="app-title">
          {ko.app.title}
        </Link>
        <nav className="app-nav">
          <Link to="/scenarios">{ko.app.nav_scenarios}</Link>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to="/scenarios" replace />} />
          <Route path="/scenarios" element={<ScenarioListPage />} />
          <Route path="/scenarios/:scenarioId" element={<Navigate to="overview" replace />} />
          <Route path="/scenarios/:scenarioId/:tab" element={<ScenarioDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}

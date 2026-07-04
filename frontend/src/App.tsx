import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ko } from "./i18n/ko";
import { EvidencePage } from "./pages/EvidencePage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ReviewPage } from "./pages/ReviewPage";
import { ScenarioDetailPage } from "./pages/ScenarioDetailPage";
import { ScenarioListPage } from "./pages/ScenarioListPage";

const NAV_ITEMS = [
  { to: "/portfolio", label: ko.app.nav_portfolio },
  { to: "/scenarios", label: ko.app.nav_scenarios },
  { to: "/review", label: ko.app.nav_review },
  { to: "/evidence", label: ko.app.nav_evidence },
];

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <NavLink to="/portfolio" className="app-title">
          {ko.app.title}
        </NavLink>
        <nav className="app-nav">
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Navigate to="/portfolio" replace />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/scenarios" element={<ScenarioListPage />} />
          <Route path="/scenarios/:scenarioId" element={<Navigate to="overview" replace />} />
          <Route path="/scenarios/:scenarioId/:tab" element={<ScenarioDetailPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/review/:week" element={<ReviewPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
        </Routes>
      </main>
    </div>
  );
}

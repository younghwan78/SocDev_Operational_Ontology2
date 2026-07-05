import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ko } from "./i18n/ko";
import { EvidencePage } from "./pages/EvidencePage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ReviewPage } from "./pages/ReviewPage";
import { RiskMapPage } from "./pages/RiskMapPage";
import { ScenarioDetailPage } from "./pages/ScenarioDetailPage";
import { ScenarioListPage } from "./pages/ScenarioListPage";

// 질문이 곧 메뉴 — 위험 지도만 활성, 나머지는 Stage 9~11에서 활성화된다.
const QUESTION_NAV = [{ to: "/", label: ko.app.nav_risk }];
const PLANNED_NAV = [ko.app.nav_change_impact, ko.app.nav_issue_analysis, ko.app.nav_ask];

// 기존 데이터 화면 — 답의 근거를 보여주는 하위 층으로 유지.
const EXPLORE_NAV = [
  { to: "/portfolio", label: ko.app.nav_portfolio },
  { to: "/scenarios", label: ko.app.nav_scenarios },
  { to: "/review", label: ko.app.nav_review },
  { to: "/evidence", label: ko.app.nav_evidence },
];

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <NavLink to="/" className="app-title">
          {ko.app.title}
        </NavLink>
        <nav className="app-nav">
          {QUESTION_NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {label}
            </NavLink>
          ))}
          {PLANNED_NAV.map((label) => (
            <span key={label} className="nav-disabled" title={ko.app.planned}>
              {label}
            </span>
          ))}
          <span className="nav-group-label">{ko.app.nav_explore_group}</span>
          {EXPLORE_NAV.map(({ to, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<RiskMapPage />} />
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

import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { DemoStoryBar } from "./components/DemoStoryBar";
import { ko } from "./i18n/ko";
import { AskPage } from "./pages/AskPage";
import { ChangeImpactPage } from "./pages/ChangeImpactPage";
import { EvidencePage } from "./pages/EvidencePage";
import { IssueAnalysisPage } from "./pages/IssueAnalysisPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { ReviewPage } from "./pages/ReviewPage";
import { RiskMapPage } from "./pages/RiskMapPage";
import { ScenarioDetailPage } from "./pages/ScenarioDetailPage";
import { ScenarioListPage } from "./pages/ScenarioListPage";
import { SourceMapPage } from "./pages/SourceMapPage";
import { IngestPage } from "./pages/IngestPage";

// 질문이 곧 메뉴 — 원점 문서의 5대 질문이 전부 활성화됐다.
const QUESTION_NAV = [
  { to: "/", label: ko.app.nav_risk },
  { to: "/change-impact", label: ko.app.nav_change_impact },
  { to: "/issues", label: ko.app.nav_issue_analysis },
  { to: "/ask", label: ko.app.nav_ask },
];

// 기존 데이터 화면 — 답의 근거를 보여주는 하위 층으로 유지.
const EXPLORE_NAV = [
  { to: "/portfolio", label: ko.app.nav_portfolio },
  { to: "/scenarios", label: ko.app.nav_scenarios },
  { to: "/review", label: ko.app.nav_review },
  { to: "/evidence", label: ko.app.nav_evidence },
  { to: "/source-map", label: ko.app.nav_source_map },
  { to: "/ingest", label: ko.app.nav_ingest },
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
          <span className="nav-group-label">{ko.app.nav_explore_group}</span>
          {EXPLORE_NAV.map(({ to, label }) => (
            <NavLink key={to} to={to} className={({ isActive }) => (isActive ? "active" : "")}>
              {label}
            </NavLink>
          ))}
          <NavLink to="/?story=1" className="nav-demo">
            {ko.demo.nav}
          </NavLink>
        </nav>
      </header>
      <DemoStoryBar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<RiskMapPage />} />
          <Route path="/change-impact" element={<ChangeImpactPage />} />
          <Route path="/issues" element={<IssueAnalysisPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/portfolio" element={<PortfolioPage />} />
          <Route path="/scenarios" element={<ScenarioListPage />} />
          <Route path="/scenarios/:scenarioId" element={<Navigate to="overview" replace />} />
          <Route path="/scenarios/:scenarioId/:tab" element={<ScenarioDetailPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/review/:week" element={<ReviewPage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/source-map" element={<SourceMapPage />} />
          <Route path="/ingest" element={<IngestPage />} />
        </Routes>
      </main>
    </div>
  );
}

/**
 * 데모 스토리 바 — ?story=<n> 파라미터가 있으면 안내 배너를 띄운다.
 * 장면별 소요 시간을 기록해 마지막에 TAT 요약을 보여준다 (앱 내 로그).
 */
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ko } from "../i18n/ko";
import { STORY_SCENES, sceneUrl } from "../demo/story";

const t = ko.demo;
const RUN_KEY = "soc_tat_run";

interface SceneRecord {
  scene: string;
  title: string;
  ms: number;
}

function readRun(): SceneRecord[] {
  try {
    return JSON.parse(localStorage.getItem(RUN_KEY) ?? "[]") as SceneRecord[];
  } catch {
    return [];
  }
}

function formatMs(ms: number): string {
  const total = Math.round(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function DemoStoryBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const storyParam = new URLSearchParams(location.search).get("story");

  if (storyParam === "summary") {
    const run = readRun();
    const total = run.reduce((sum, record) => sum + record.ms, 0);
    return (
      <div className="story-bar">
        <span className="story-title">{t.summary_title}</span>
        {run.map((record) => (
          <span key={record.scene} className="chip">
            {record.title} {formatMs(record.ms)}
          </span>
        ))}
        <span className="badge badge-ok">
          {t.total} {formatMs(total)}
        </span>
        <span className="story-desc">{t.summary_note}</span>
        <button type="button" className="chip chip-btn" onClick={() => navigate("/")}>
          {t.exit}
        </button>
      </div>
    );
  }

  const sceneIndex = Number(storyParam ?? "0");
  if (!Number.isInteger(sceneIndex) || sceneIndex < 1 || sceneIndex > STORY_SCENES.length) {
    return null;
  }
  // key로 장면 전환 시 SceneBar를 remount → 스톱워치(enteredAt)가 자연히 리셋된다.
  return <SceneBar key={sceneIndex} sceneIndex={sceneIndex} />;
}

/** 단일 장면 배너 + 경과 스톱워치. sceneIndex별 key로 마운트되어 상태가 장면마다 초기화된다. */
function SceneBar({ sceneIndex }: { sceneIndex: number }) {
  const location = useLocation();
  const navigate = useNavigate();
  const scene = STORY_SCENES[sceneIndex - 1];
  const [enteredAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    // 스토리 시작(장면1) 진입 시 이전 실행 로그 초기화 — 외부 저장소 부수효과.
    if (sceneIndex === 1) localStorage.setItem(RUN_KEY, "[]");
  }, [sceneIndex]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const record = () => {
    const run = readRun();
    run.push({ scene: scene.id, title: scene.title, ms: Date.now() - enteredAt });
    localStorage.setItem(RUN_KEY, JSON.stringify(run));
  };

  return (
    <div className="story-bar">
      <span className="badge badge-info">
        {t.scene_label} {sceneIndex}/{STORY_SCENES.length}
      </span>
      <span className="story-title">{scene.title}</span>
      <span className="story-desc">{scene.description}</span>
      <span className="badge badge-warn">
        {t.elapsed} {formatMs(now - enteredAt)}
      </span>
      {sceneIndex > 1 && (
        <button
          type="button"
          className="chip chip-btn"
          onClick={() => navigate(sceneUrl(sceneIndex - 1))}
        >
          {t.prev}
        </button>
      )}
      <button
        type="button"
        className="chip chip-btn active"
        onClick={() => {
          record();
          if (sceneIndex === STORY_SCENES.length) navigate("/?story=summary");
          else navigate(sceneUrl(sceneIndex + 1));
        }}
      >
        {t.next}
      </button>
      <button type="button" className="chip chip-btn" onClick={() => navigate(location.pathname)}>
        {t.exit}
      </button>
    </div>
  );
}

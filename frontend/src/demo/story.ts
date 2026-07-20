/**
 * 데모 스토리 4장면 — "위험 발견 → 원인 → 변경 영향 → 결정 근거".
 * 각 장면은 사전 구성된 화면 경로로 이동한다 (클릭만으로 진행).
 * 경로의 fixture ID는 synthetic 데모 세계관의 안내 경로 구성이며 비즈니스 로직이 아니다.
 */
import { ko } from "../i18n/ko";

export interface StoryScene {
  id: string;
  title: string;
  description: string;
  path: string;
}

export const STORY_SCENES: StoryScene[] = [
  // G1(설계 26): 홈이 게이트 콘솔로 바뀌어 장면1(위험 지도)은 /risk-map으로 이동.
  { id: "risk", title: ko.demo.s1_title, description: ko.demo.s1_desc, path: "/risk-map" },
  {
    id: "cause",
    title: ko.demo.s2_title,
    description: ko.demo.s2_desc,
    path: "/issues?issue=issue_mfc_8k30_bitrate_latency_u",
  },
  {
    id: "impact",
    title: ko.demo.s3_title,
    description: ko.demo.s3_desc,
    path: "/change-impact?ip=ip_mfc&knob=knob_mfc_nal_queue",
  },
  {
    id: "evidence",
    title: ko.demo.s4_title,
    description: ko.demo.s4_desc,
    path: "/ask?q=" + encodeURIComponent("8K30 thermal issue가 해결됐다고 판단할 evidence는 무엇인가?"),
  },
];

export function sceneUrl(index: number): string {
  const scene = STORY_SCENES[index - 1];
  const separator = scene.path.includes("?") ? "&" : "?";
  return `${scene.path}${separator}story=${index}`;
}

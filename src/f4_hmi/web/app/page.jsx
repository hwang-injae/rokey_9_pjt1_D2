import Monitor from './Monitor';

// 화면은 브라우저에서만 그린다(WebSocket) — 빌드 때는 빈 틀만 만들어 둔다
export default function Home() {
  return <Monitor />;
}

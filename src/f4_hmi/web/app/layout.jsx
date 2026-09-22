import './globals.css';

export const metadata = {
  title: 'PreWash-Cell HMI',
  description: '다회용기 예비세척 셀 — 시스템 모니터',
};

export default function RootLayout({ children }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

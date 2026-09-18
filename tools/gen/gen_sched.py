# -*- coding: utf-8 -*-
"""PreWash-Cell 개발일정 v2 — 이전 프로젝트(IDC 순찰로봇) 양식: Time Line(색 간트) + 상세 + 완료 목록 + 규칙 + 변경이력"""
import zipfile, html, sys

DAYS=[('9/18','금'),('9/19','토'),('9/20','일'),('9/21','월'),('9/22','화'),('9/23','수'),('9/24~28','추석·로봇 없음'),('9/29','화'),('9/30','수')]
PARTS=['오전','오후','저녁']
# (팀, 구분, 작업, 담당, ID, 간트 span 목록 "dP" 또는 "dP-dP", 색 g/r/y, 산출물, 완료 기준, 비고)
T=[]
def A(*a): T.append(a)
# 담당 약자: S 한석형(팀장·F1) · M 민범진(F2·flow·통합 리더) · P 박진용(F3·안전) · H 황인재(PM·F4 웹)
# ---------------- 전원 / PM ----------------
A('전원','브리핑','데일리 브리핑 09:30 (진행·이슈·당일 로봇 슬롯) — 9/19~23, 9/29','전원(H 진행)','BRF','1A,2A,3A,4A,5A,7A','y','','노션 진행률 갱신','수업일(9/21~23)은 09:20 짧게')
A('전원','PM','일정표 갱신(진행·상태·완료 목록·변경이력)·진척 취합·PR 확인 — 매일 저녁','H','PM-01','0C,1C,2C,3C,4C,5C','y','구글 시트','전 행 상태 최신','')
A('전원','문서','문서 v2 확정 — 요구사항(BR·SR)·IRD·SDD, 팀원 에이전트 배포','전원','DOC-01','0B','y','docs/01~03 v2, AGENTS.md','배포 완료','')
A('전원','설계','아키텍처·인터페이스 확정 회의 (1차) — PC 2대·노드 5개·flow만 호출·F1↔F3 경계·wipe 분리·seat/home 삭제·prewash.yaml 통합 확정','전원','DSN-01','0B','r','docs/meetings/20260918_DSN-01','회의록','')
A('전원','계약','1차 회의 결과 반영 — IRD v2.1·interfaces·SDD·프롬프트·회의록','H','DSN-02','0C','r','docs PR','merge','')
A('전원','환경','PC별 환경 점검 — ws_dsr 빌드·Virtual 브링업·DOMAIN 60·저장소 clone·rokey_pjt01_ws 빌드','전원','ENV-01','0B-0C','g','setup 체크리스트','4대 모두 sodvir + cbc 성공','docs/setup/M0609_환경설정.md')
A('전원','환경','로봇 접속 확인 — IP 192.168.1.100·제어권·RG2 설정 웹(192.168.1.1)·툴/TCP 확인','S','ENV-02','0C','g','접속 로그','sodreal 브링업 성공','R')
A('전원','계약','cobot_msgs 배포 v2.0 (srv·msg 패키지화)','M','INF-01','0C','r','src/cobot_msgs','4대 빌드 성공','PR #1 merge')
A('전원','계약','cobot_msgs v2.1 — wipe 분리(F3WipeBowl·F3WipeCup)·F3Seat 삭제·F1Place 응답 offset_mm','H','INF-01b','0C','r','src/cobot_msgs PR','docs/interfaces 와 동일, 빌드 14개','정본 관리 = PM')
A('전원','계약','cobot_common v0 — init(node)·spin(node)(두산 API 초기화·실행기, TS-01) + move_to/move_rel/grip/release/weigh + config.py(로더)','P','INF-02','0C-1A','r','src/cobot_common/bootstrap.py, robot.py, config.py','Virtual에서 서비스 콜백 안 movej 연속 3회 응답 + move_to·grip 동작','남들이 이걸로 개발 · init/spin PR이 9/19 오전 V-20과 세 노드 뼈대의 선행')
A('전원','계약','config 골격(cell.yaml + params.yaml 의 f1·f2·f3·flow·hmi 절) + prewash_bringup 런치 2종','H','INF-04','0C-1A','g','config/cell.yaml·params.yaml, launch/*.py','mock 런치로 flow+hmi 기동','파일 주인은 IRD §9')
A('전원','계약','mock_f1_f3 (M) + fake_state_pub (H)','M,H','INF-03','0C-1A','g','mock/, fake_state_pub.py','mock 서비스 응답·실패 주입, fake 상태 발행','로봇 없이 flow·HMI 개발')
A('전원','검증','V-20 여러 노드의 두산 API 동시 사용 — f1·f2·f3 세 노드가 SDD §3.2 뼈대(cobot_common.init·spin)로 같은 드라이버에 번갈아 명령(Virtual, 실제 드라이버)','S,M,P','V-20','1A','g','검증 메모','세 노드에서 번갈아 movej, 노드당 연속 3회 성공','INF-02 init/spin PR 뒤 · 안 되면 로봇 명령을 한 노드로 모음')
A('전원','기록','TS-01 두산 API 초기화 누락·서비스 콜백 안 로봇 명령 교착 — 원인 분석·재현·해법 확정, 문서 반영(SDD §3.2 노드 뼈대 규약)','P,H','TS-01','0C','r','docs/troubleshooting/TS-01_*.md, 재현 스크립트','트러블슈팅 기록 + SDD·AGENTS·프롬프트 반영 merge, 팀 공지','박진용 발견 · PM 재현. 1차 수정안은 두 번째 호출부터 멈춤 → DSR 전용 노드 분리')
A('전원','환경','다중 PC 통신 (V-09) — PC-A↔PC-B DOMAIN 60에서 토픽·서비스 보임','H,M','ENV-03','1A','g','통신 확인 캡처','PC-B에서 /flow/state 수신','안 되면 Discovery Server')
A('전원','기구','공통 좌표 티칭 세션 — HOME·스테이션·반납 구역 기준·스펀지 홈·팔레트 기준점','전원','CELL-04','1A','r','config/cell.yaml 좌표','전 스테이션 기록, 제어권 해제 확인','R')
A('전원','설계','시스템 아키텍처 draw.io 정리(1차 회의 결과, PC 단위·통신 표) + 노션 산출물 10종 등록','H','ARCH-01','1A-1B','g','docs/images/*.drawio, 노션','강사 산출물 10종이 노션에 있음','')
A('전원','설계','2차 회의 — 반납 구역 방식(V-01·V-15 결과)·HMI 설계(F4-00)·실패 코드·정책·YAML 키 규칙 확정','전원','DSN-03','1C','r','docs/meetings/20260919_DSN-03','미확정 4건 모두 결정','')
A('전원','계약','2차 회의 결과 반영 — IRD v2.2·interfaces·cobot_msgs·SDD','H','DSN-04','1C','r','docs·msgs PR','merge, 4대 git pull + cbc','')
A('전원','발표','중간점검 발표 자료 — 주제·아키텍처·역할·진행·계획 (10장)','전원(H 취합)','MID-01','2C-3A','y','중간점검 PPT','30분 발표 가능','6차시 9/21(월) 오후')
A('전원','발표','프로젝트 중간점검 — 조별 30분 발표 + 30분 토론 (8팀)','전원','MID-02','3B','y','피드백 메모','피드백을 일정에 반영','수업 중 프로젝트 준비 금지')
A('전원','리뷰','팀 코드리뷰 — 노드 4종·안전 파라미터·하드코딩 점검','전원','CR-01','3C','y','리뷰 기록','지적 사항 이슈 등록','')
A('전원','문서','노션 — ROS2 노드 구조·인터페이스 정의서 업로드 (강사 9/22 요구)','H','NOTE-01','4A','y','노션 페이지','9/22 오전 업로드','')
A('전원','통합 L3','그릇 1개 end-to-end (실제 노드 3 + flow + HMI) 3회','M(전원)','INT-3a','4B','r','통합 로그·영상','무개입 3회 연속','R')
A('전원','통합 L3','컵 1개 end-to-end 3회','M(전원)','INT-3b','4C','r','통합 로그·영상','무개입 3회 연속','R')
A('전원','개발','L3 결함 수정·파라미터 튜닝','전원','FIX-01','4C-5A','g','수정 PR','INT-3a/3b 재통과','R')
A('전원','통합 L4','시작 1회 → 그릇 2·컵 2 연속 처리 (S3)','M(전원)','INT-4a','5A','r','기록 4행·영상','AC-1·AC-7','R')
A('전원','통합 L4','실패 주입 4종 — 빈 구역 / 잔반 과다 / 툴 미배치 / 팔레트 걸림 + 정지·재개','M,P','INT-4b','5B','r','복구 로그','AC-6 정책대로','R')
A('전원','통합 L4','성공률·사이클 타임·잔반 검출률 측정 ×3','H','INT-4c','5B','g','KPI 표','AC-2~5 수치','R')
A('전원','통합 L4','시연 영상 촬영(원본) · v1.0-demo 태그 · 기능 동결','전원(H 태그)','INT-4d','5C','r','원본 영상, 태그','main 태그, 이후 기능 추가 금지','R · 9/23 저녁 동결')
A('전원','문서','발표 PPT — 강사 5장 양식(개요/팀 구성·역할/절차·방법/경과/자체평가) + 평가기준 대응','전원(H 취합)','DOC-02','6A-6C','g','PPTX','슬랙 양식 필수 항목 모두','추석 재택')
A('전원','문서','시연 영상 편집 — 1분 이내, 자막','H','DOC-03','6A-6B','g','D-2_협동1_….mp4','1분 이내, 4개 처리 + 오류 복구 장면','')
A('전원','문서','발표 대본·시연 순서표·역할표·QnA 예상','H(전원)','DOC-04','6B-6C','g','대본 1장','20분 발표 + QnA 10분 리허설','')
A('전원','문서','as-built 문서 갱신·결과표·노션 정리(발표 자료에 맞게)·README','H(전원)','DOC-05','6A-6C','g','docs v2.x, 노션','결과표 수치 기입','')
A('전원','리허설','온라인 리허설 (PPT·영상)','전원','REH-01','6C','y','수정 목록','20분 내 완료','')
A('전원','리허설','통합 디버깅·실기 리허설 (오전)','전원(M 실행)','REH-02','7A','r','리허설 영상','무개입 1회','R · 9/29')
A('전원','발표','강사 입회 시연 (14:00~, 준비된 조부터) + PPT 토의','전원','DEMO-01','7B','y','강사 피드백','필수 기재 항목 누락 0','')
A('전원','리허설','백업 촬영·최종 점검·최종 git push·노션 정리','전원','REH-03','7C','g','백업 영상','main 최신, 노션 정리 완료','')
A('전원','제출','제출 (11시 전) — 영상 mp4·PPT pdf·소스 zip(패키지 폴더)·README, 파일명 D-2_협동1_한석형_민범진_박진용_황인재','H','SUB-01','8A','y','제출 패키지','슬랙 가이드라인 양식 일치','')
A('전원','발표','최종 발표 (조당 20분 + QnA 10분, 순서 랜덤) · 평가','전원','DOC-06','8A-8B','y','','','11:00~12:30 / 14:00~15:30')
A('전원','정리','PPT 검토·기술공유·제출 양식 점검·로봇 설정 초기화·주변 정리','전원','WRAP-01','8C','y','','','15:30~18:30')
# ---------------- F1 한석형 ----------------
A('F1','기구','반납 구역 2곳(그릇·컵)·식기세척기용 팔레트(그릇 2·컵 4)·격리 구역 배치·핑거 패드','S','CELL-01','0B-0C','g','워크셀 사진·치수 메모','팔레트 칸 6개 위치 확정','')
A('F1','검증','V-01 파지 폭 3상태 구분 — 그릇/컵/빈손 폭 값 간격 > 오차','S','V-01','0C','r','폭 측정표','3상태 간격 ≥ 6 mm','R · DSN-03 입력')
A('F1','검증','V-05 RG2 DO1/DO2 배선·DI1/DI2 파지 완료 신호','S','V-05','0C','g','배선 메모','grip/release 신호 왕복','R')
A('F1','검증','V-17 컵 옆면 파지 — 검증 완료: 집기·이송 OK, 털기·헹굼은 더 강한 파지 필요 → 파지 힘 2단계','S','V-17','0C','g','검증 메모','집기·이송 안정','R · 완료')
A('F1','검증','V-19 도달 범위·특이점 — 모든 스테이션에 안전 높이 경유로 도달 가능한가','S','V-19','1A','g','도달 확인표','전 지점 도달, 경고 0','R · 티칭과 함께')
A('F1','검증','V-22 티칭 좌표 재현 오차 — YAML 좌표를 ROS에서 재현','S','V-22','1A','g','오차 표','≤ 2 mm','R')
A('F1','검증','V-06 팔레트 칸 삽입 각도·걸림 힘 판정','S','V-06','1B','g','각도·힘 기록','걸림 시 힘 상승이 식별됨','R')
A('F1','검증','V-08 툴 홀더 픽업·반납 10회 반복','S','V-08','1B','g','성공 횟수','≥9/10','R')
A('F1','검증','V-15 재파지 파지 폭 인식 — 스펀지 홈의 그릇·컵을 다시 잡을 때 폭으로 구분되는가','S,P','V-15','1B','r','폭 측정표','3상태 간격 ≥ 6 mm','R · 스펀지 도착 후 · DSN-03 입력')
A('F1','검증','V-16 강한 파지(HOLD) 값 찾기 — 털기·물 털기 시 낙하·밀림 없는 최소 힘(용기 변형 없는 범위)','S,M','V-16','1B','r','HOLD 힘 표','10회 낙하 0, 폭 변화 ≤ 2 mm','R')
A('F3','검증','V-23 파지 힘 전환 방법 — 쥔 채 NORMAL→HOLD→NORMAL 재파지가 되는가(onrobot_rg_control 힘 지정 / DO 방식이면 프리셋 2종)','P,S','V-23','1A','r','검증 메모','전환 10회 낙하 0','R · grip_level 구현 입력')
A('F1','개발','config/cell.yaml 절(프리셋·좌표) + move_to + 일반 place','S','F1-01','1B-1C','g','f1_node.py, config/cell.yaml','Virtual·실기 이동 OK','R 1C')
A('F1','개발','pick 탐색 파지 — 구역 탐색점 순회·접촉 하강·폭 판정·재탐색·EMPTY_ZONE','S','F1-02','1C-2A','r','f1_node.py pick()','겹친 그릇 2개에서 10회 ≥9','R · 방식은 DSN-03 후 확정')
A('F1','검증','V-14 겹친 용기 탐색 파지 성공률 (겹침·어긋남 배치)','S','V-14','2A','g','성공률 표','≥9/10, 낙하 0','R')
A('F1','개발','place 안착 놓기 — 순응 하강·깊이/힘 판정·periodic_search·SEAT_FAIL (구 /f3/seat 흡수)','S(P)','F1-05','2A','r','f1_node.py place()','정위치 5 + 2 mm 오프셋 5 ≥9','R · 힘 함수는 INF-02b')
A('F1','개발','tool PICK/RETURN (폭 확인·힘 접촉 반납)','S','F1-03','2A','g','f1_node.py tool()','10회 ≥9','R')
A('F1','개발','rack_place — 지정 각도·순응 삽입·삽입력 감시·RACK_JAM 후퇴','S','F1-04','2B','r','f1_node.py rack_place()','각 칸 5회 ≥9/10','R')
A('F1','테스트','UT-F1 — TC-01·02·05·09','S','UT-F1','2B-2C','r','test_logs','TP 기준 통과','R · 로봇 움직이는 TC는 녹화 권장')
A('F1','통합 L2','INT-12b F1+F2 — 재파지→헹굼→물털기→팔레트 적재 5회 (주도)','S(M)','INT-12b','3C','r','통합 로그','5회 무개입, 낙하 0','R · 9/21 저녁')
A('F1','통합 L2','INT-13 참여 (F1 안착 놓기·툴)','S','INT-13p','4A','g','','','R')
# ---------------- F2 민범진 ----------------
A('F2·flow','기구','잔반통·세제/헹굼 수조 배치(컨트롤러 반대편·고정)·잔반 대용품 선정 (V-11 ≥100 g)','M','CELL-03','0B-0C','g','배치 사진, 대용품','대용품 ≥100 g, 털면 떨어짐','')
A('F2·flow','검증','V-02 하중 측정 정밀도 — 100/200 g 추 10회','M','V-02','0C','g','측정표','±20 g','R · 미달 시 임계 100 g')
A('F2·flow','개발','flow_node 상태 머신·구역 계획(plan)·실패 정책·start/stop/resume (mock)','M','FLOW-01','0C-1C','r','flow_node.py, config/params.yaml(flow 절)','mock으로 4개 시나리오 완주','')
A('F2·flow','검증','V-21 flow_node 실행 구조 — 작업 스레드 + 동기 호출로 기다리는 동안 /flow/state 2 Hz·stop 수락(mock). 기능 노드 쪽 교착은 TS-01로 원인·해법 확정(9/18 박진용)','M','V-21','1A','g','검증 메모','flow가 응답을 연속 3회 받고 /flow/state 2 Hz 유지, 모션 중 stop 수락','mock · SDD §5.1 · 안 되면 액션 전환')
A('F2·flow','검증','V-07 털기 진폭·속도에서 충돌 감지 오작동 여부','M','V-07','1B','g','진폭·속도 표','10회 정지 0','R')
A('F2·flow','개발','weigh · leftover_loop · shake(WASTE) — 시작 시 강한 파지(HOLD)·끝나면 NORMAL·전후 폭 비교','M','F2-01','1B-1C','r','f2_node.py, config/params.yaml(f2 절)','대용품 검출 100%','R 1C')
A('F2·flow','개발','기록(records.csv)·/flow/event·소모품 카운트','M','FLOW-02','1C-2A','g','logger.py','4행 누락 0','')
A('F2·flow','개발','dip(RINSE) · shake(RINSE) — 강한 파지(HOLD) 적용','M','F2-02','2A','g','f2_node.py','10회 정지 0','R')
A('F2·flow','테스트','UT-FLOW — TC-10 정책 · TC-12 기록 (mock)','M','UT-FLOW','2A','g','test_logs','정책대로, 4행','')
A('F2·flow','테스트','UT-F2 — TC-03·04·08','M','UT-F2','2C','r','test_logs','TP 기준 통과','R')
A('F2·flow','통합 L2','INT-12a F1+F2 — 탐색 파지→무게→털기 5회 (주도)','M(S)','INT-12a','2C-3C','r','통합 로그','5회 무개입, 판정 정확','R · 9/20 저녁~9/21 저녁')
# ---------------- F3 박진용 ----------------
A('F3','검증','V-03 힘제어 중 XY 이동·나선 가능 여부 (아무 스펀지 + 그릇으로)','P','V-03','0C','r','검증 메모','가능/불가 판정 → 불가면 범위 방어','R · V-02 다음 슬롯 · 닦기 설계를 결정')
A('F3','계약','cobot_common 힘 관련 함수 — force_on/off·contact_down·periodic_search (닦기와 F1 안착 놓기 공용)','P','INF-02b','0C-1A','r','src/cobot_common/robot.py','Virtual에서 호출 순서 오류 0, V-03에서 실기 확인','INF-02와 같은 파일(둘 다 박진용)')
A('F3','문서','안전 파라미터 표·위험요소/안전대책(노션 산출물)·예외/오류 리스트','P','SAFE-01','0C','g','노션 페이지','강사 산출물 목록 충족','')
A('F3','기구','용기 치수 측정·스펀지 홈 커팅 도면·툴 홀더 위치 결정 (재료 도착 전 준비)','P','CELL-02a','0C','g','치수표·도면','내일 바로 커팅 가능','로봇 불필요')
A('F3','기구','스펀지 고정틀(그릇 홈·컵 홈 커팅)·툴 홀더 2종·수세미 손잡이·작업대 고정','P','CELL-02','1A','g','고정틀·홀더 실물','5 N에서 1 mm 이상 안 밀림','재료 9/19 오전 도착')
A('F3','검증','V-12 스펀지 홈 치수 vs 용기 외경 (여유 1~2 mm)','P','V-12','1A','g','치수표','그릇·컵 모두 홈에 들어감','')
A('F3','검증','V-04 Move Periodic 탐색으로 홈 안착 (2 mm 오프셋)','P,S','V-04','1B','g','성공률','5회 중 4회','R · F1-05 입력')
A('F3','검증','V-10 컵 안쪽 솔 삽입 깊이·충돌','P','V-10','1B','g','깊이 값','충돌 정지 0','R')
A('F3','검증','V-18 툴 파지 안정성 — 닦는 힘(3~5 N)에서 수세미 툴·솔이 그리퍼 안에서 밀리거나 돌지 않는가','P','V-18','1B','g','검증 메모','닦기 1회 후 툴 자세 변화 없음','R')
A('F3','개발','wipe_bowl — 힘제어 나선·힘 로그·상한/타임아웃 후퇴','P','F3-02','1C-2B','r','f3_node.py, force_*.csv','목표 ±2 N, 초과 0','R')
A('F3','개발','soap · wipe_cup (삽입·회전·상하)','P','F3-03','2B','g','f3_node.py','10회 정상','R')
A('F3','테스트','UT-F3 — TC-06·07','P','UT-F3','2B-2C','r','test_logs','TP 기준 통과','R')
A('F3','통합 L2','INT-13 F1+F3 — 안착 놓기→툴→세제→닦기→반납 5회 (주도)','P(S)','INT-13','3C-4A','r','통합 로그','5회 무개입, 힘 로그','R · 9/21 저녁~9/22 오전')
# ---------------- F4 황인재 (웹 + PM) ----------------
A('F4','설계','HMI 설계 초안 — 화면 구성·REST/WS·필요한 FlowState·FlowEvent 필드','H','F4-00','0C-1A','r','설계 1장','DSN-03에서 확정','')
A('F4','개발','fake_state_pub + FastAPI 골격 페이지(안녕 페이지 → 상태 표시)','H','F4-01','0C-1A','g','fake_state_pub.py, app.py','브라우저에 /flow/state 값 표시','로봇 불필요')
A('F4','개발','REST/WS 브리지·버튼 3종·소프트 정지(E-STOP 표시 항상 노출)','H','F4-02','1B','r','app.py','버튼 → 서비스 ≤1 s','')
A('F4','개발','화면 — 단계·구역·팔레트 칸·수량·소모품·연결 상태·오류 로그·이력 표','H','F4-03','1C-2B','g','static/index.html','fake 시나리오 표시','DSN-03 결과 반영')
A('F4','검증','V-13 브라우저 start → mock flow 반응','H','V-13','2A','g','캡처','PAUSED/재개 반영','')
A('F4','개발','SQLite 기록(events·state)·GET /api/history','H','F4-04','2B','g','prewash.db, app.py','이벤트 행 저장·조회','')
A('F4','테스트','UT-F4 — TC-11','H','UT-F4','2C','r','test_logs','지연 ≤1 s','')
A('F4','통합 L2','INT-4 flow(mock)+HMI — 시작·정지·재개','H(M)','INT-4','3C','r','통합 로그','버튼 동작·상태 표시','')
A('F4','문서','노션 — 관리자 HMI·사용자 UI 화면 gif 업로드 (강사 9/22 요구)','H','NOTE-02','4A','y','gif','9/22 오전 업로드','')
A('F4','개발','KPI 측정 스크립트(records/SQLite → 성공률·사이클 타임·탐색 시도)·촬영 계획','H','F4-05','4A','g','kpi.py','INT-4c에 사용','')

DONE_IDS={'DOC-01','DSN-01','DSN-02','ENV-01','ENV-02','INF-01','V-17'}   # 생성 시 완료로 표기 (시트에 다른 값이 있으면 시트 값 우선)

# ---------------- 색 · 규칙 · 변경이력 ----------------
COLORS={'g':'FFB7D7A8','r':'FFE06666','y':'FFFFF2CC','x':'FFD9D9D9','h':'FFCFE2F3','t':'FF9FC5E8'}
RULES=[('마감','9/20(일) 저녁','L1 단위기능 테스트(UT-*) 전부 통과. 미통과 기능은 범위 방어표대로 축소'),
('마감','9/21(월)','오전 강의(DRL srv·launch), 오후 중간점검 발표 30분+토론 30분. 로봇·개발은 저녁만'),
('마감','9/22(화) 오전','L2 단위기능 통합 완료 · 노션에 노드 구조·HMI 화면 업로드 · GitHub 최신'),
('마감','9/23(수) 저녁','L4 전체 통합 + 시연 영상 원본 + 기능 동결(main 태그 v1.0-demo). 이후 기능 추가 금지'),
('마감','9/29(화) 14:00','강사 입회 시연(준비된 조부터) + PPT 토의'),
('마감','9/30(수) 11:00','제출: 영상 mp4·PPT pdf·소스 zip(패키지 폴더)·README. 파일명 D-2_협동1_한석형_민범진_박진용_황인재.ext'),
('색','초록 / 빨강 / 노랑 / 회색','초록 = 계획 / 빨강 = 시연 필수 경로(우선순위 높음) / 노랑 = 브리핑·리뷰·발표·제출·강사 행사 / 회색 = 완료'),
('로봇','비고 R','R 표시 작업은 실기 로봇 필요. 하루 3슬롯(오전·오후·저녁), 배정은 전날 브리핑에서. 주말 9/19·20 사용 가능. 9/24~28 불가'),
('보고','GitHub','브랜치 {이름}/{YYYYMMDD}-{taskID}-{설명}. PR 제목 <타입>(<스코프>): <taskID> <제목> 예) feat(f1): F1-02 pick 탐색 파지. taskID는 맨 오른쪽 ID 열. 일정표는 PM(황인재)만 수정'),
('개발 흐름','단위기능 → 통합','단위기능 완성 → 단위기능 테스트(TC 있는 작업) → main pull → 통합 테스트 → main PR(승인 조건: main 최신 병합·산출물 없음). 로봇 움직이는 테스트는 녹화 권장 YYYYMMDD_TCxx_기능_담당_시도N.mp4'),
('정본','이 파일(구글 드라이브)','일정표 정본은 구글 공유 드라이브의 이 xlsx. 테스트 기준(TC·INT·V)은 저장소 docs/03_설계_SDD.md §9. 완료 행은 완료 목록 시트로 이동'),
('기준 문서','docs/01~03 v2','요구사항(BR·SR) / 인터페이스(IRD) / 설계(SDD §9 테스트 계획, §13 일정표). 용기 그릇 2·컵 2, 팔레트 그릇 2칸·컵 4칸')]
HIST=[('1.0','생성','전체','9/17 초안 — ■ 문자 간트, 요일 오차 있음','','전원'),
('2.0','재생성','전체','이전 프로젝트(IDC 순찰로봇) 양식으로 재생성: 팀별 섹션, 오전/오후/저녁 색 간트, 상세·완료·규칙·변경이력 시트. 요일 수정(9/18 금), 주말 로봇 가능, 9/21 중간점검·9/22~23 강사 요구·9/29 시연·9/30 제출 반영','사용자 수정사항 36건 + 강사 노션 일정','전원'),
('2.0','신규','ENV-01~03, V-01~14, ARCH-01, MID-01/02, NOTE-01/02, SAFE-01, DEMO-01, WRAP-01','환경구성·사전 검증·중간점검·노션 산출물·강사 시연 행 추가','강사 일정·평가기준','전원'),
('2.0','재정의','F1-02, INT-4a, TC-01','겹친 용기 탐색 파지 기능 추가(반납 슬롯 → 반납 구역), 연속 처리 6개 → 4개(그릇 2·컵 2)','기능 추가·용기 수량 확정','S,M'),
('2.0','변경','워크스페이스','ws_cobot1 → rokey_pjt01_ws, 통합 실행 PC 2대(PC-A 로봇, PC-B HMI), HMI FastAPI+SQLite','사용자 결정','전원'),
('3.0','재계획','전체','PM = 황인재 반영(cobot_msgs·런치·NOTE-01·SUB-01·대본 → H, PM-01 신설). F3 재배치(재료 9/19 도착: CELL-02·V-12 → 9/19 오전, 9/18 저녁은 V-03·INF-02b 힘 함수·SAFE-01·CELL-02a). /f3/seat 삭제 → F1-05 place 안착 놓기. 검증 V-15~V-22 추가. DSN-01~04 회의·반영 행. 진행·상태는 구글 시트 값을 그대로 가져옴','9/18 DSN-01 회의·역할 정정','전원'),
('2.1','시트','마일스톤·로봇 슬롯','04_일정_테스트.md 폐지: 강사 일정·마일스톤·로봇 슬롯·제출 규칙을 이 시트로, 테스트 계획은 SDD §9로 병합. 정본을 구글 드라이브로 이동','문서 중복 제거','전원')]


# ---- 구글 시트(정본)의 진행·상태를 ID 기준으로 가져온다 (없으면 기본값) ----
def live_status():
    import urllib.request, io, re as _re, xml.etree.ElementTree as ET
    try:
        data=urllib.request.urlopen('https://docs.google.com/spreadsheets/d/1ikTAYTa8bgZofF_3RgP5jDoOipSZBPB1/export?format=xlsx',timeout=30).read()
        z=zipfile.ZipFile(io.BytesIO(data)); ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        ss=[''.join(t.text or '' for t in si.iter('{%s}t'%ns['m'])) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        rows=[]
        for row in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iter('{%s}row'%ns['m']):
            d={}
            for c in row.findall('m:c',ns):
                v=c.find('m:v',ns); t=c.get('t'); col=_re.sub(r'\d','',c.get('r'))
                d[col]=ss[int(v.text)] if (t=='s' and v is not None) else (v.text if v is not None else '')
            rows.append(d)
        h=next(i for i,r in enumerate(rows) if r.get('A','').strip()=='팀')
        idcol=[k for k,v in rows[h].items() if 'ID' in (v or '')][-1]
        return {r.get(idcol):(r.get('E',''),r.get('F','')) for r in rows[h+2:] if r.get(idcol)}
    except Exception as e:
        print('시트 상태를 못 가져옴 → 기본값 사용:',e); return {}
LIVE=live_status()
def status_of(tid):
    e,f=LIVE.get(tid,('',''))
    if f: 
        try: return float(e or 0), f
        except: return 0.0, f
    return (1.0,'완료') if tid in DONE_IDS else (0.0,'시작 전')

# ================== markdown 조각 ==================
def spans_text(sp):
    out=[]
    for s in sp.split(','):
        a,b=(s.split('-')+[None])[:2]
        def f(x): return f"{DAYS[int(x[0])][0]} {x[1]}"
        out.append(f(a) if not b or a==b else f"{f(a)}~{f(b)}")
    return ' · '.join(out)
md=['| 팀 | 구분 | ID | 작업 | 담당 | 일정 (A 오전·B 오후·C 저녁) | 색 | 완료 기준 | 비고 |','|---|---|---|---|---|---|---|---|---|']
for team,cat,task,own,tid,sp,col,deliv,crit,note in T:
    md.append(f"| {team} | {cat} | **{tid}** | {task} | {own} | {spans_text(sp)} | {'🔴' if col=='r' else '🟡' if col=='y' else '🟢'} | {crit} | {note} |")
pass  # (04 문서 폐지로 markdown 표는 쓰지 않는다)

# ================== xlsx ==================
def col(n):  # 0-based -> letters
    s=''
    n+=1
    while n: n,r=divmod(n-1,26); s=chr(65+r)+s
    return s
def esc(v): return html.escape(str(v),quote=False)
def c(ref,v,s): 
    if v=='' or v is None: return f'<c r="{ref}" s="{s}"/>'
    return f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">{esc(v)}</t></is></c>'
def sheet(rows,cols_w,merges=(),freeze=None):
    x=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
    if freeze: x.append(f'<sheetViews><sheetView workbookViewId="0"><pane xSplit="{freeze[0]}" ySplit="{freeze[1]}" topLeftCell="{col(freeze[0])}{freeze[1]+1}" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>')
    x.append('<cols>'+''.join(f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>' for i,w in enumerate(cols_w))+'</cols>')
    x.append('<sheetData>')
    for ri,row in enumerate(rows):
        x.append(f'<row r="{ri+1}">'+''.join(c(f'{col(ci)}{ri+1}',v,s) for ci,(v,s) in enumerate(row))+'</row>')
    x.append('</sheetData>')
    if merges: x.append('<mergeCells count="%d">'%len(merges)+''.join(f'<mergeCell ref="{m}"/>' for m in merges)+'</mergeCells>')
    x.append('</worksheet>')
    return '\n'.join(x)
# styles: 0 default, 1 header(bold, gray, border, center), 2 text border wrap, 3 center border, 4 g,5 r,6 y,7 x(done), 8 h(team header), 9 title bold, 10 t(day header)
fills=['<fill><patternFill patternType="none"/></fill>','<fill><patternFill patternType="gray125"/></fill>']
fid={}
for k,v in [('hdr','FFD9D9D9'),('g',COLORS['g']),('r',COLORS['r']),('y',COLORS['y']),('x',COLORS['x']),('h',COLORS['h']),('t',COLORS['t'])]:
    fid[k]=len(fills); fills.append(f'<fill><patternFill patternType="solid"><fgColor rgb="{v}"/><bgColor indexed="64"/></patternFill></fill>')
xfs=['<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>',
 f'<xf numFmtId="0" fontId="1" fillId="{fid["hdr"]}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>',
 '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>',
 '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>']
for k in ['g','r','y','x']:
    xfs.append(f'<xf numFmtId="0" fontId="0" fillId="{fid[k]}" borderId="1" applyFill="1" applyBorder="1"/>')
xfs.append(f'<xf numFmtId="0" fontId="1" fillId="{fid["h"]}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>')
xfs.append('<xf numFmtId="0" fontId="2" fillId="0" borderId="0" applyFont="1"/>')
xfs.append(f'<xf numFmtId="0" fontId="1" fillId="{fid["t"]}" borderId="1" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>')
S={'hdr':1,'txt':2,'ctr':3,'g':4,'r':5,'y':6,'x':7,'team':8,'title':9,'day':10}
styles=f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="3"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><name val="Arial"/></font><font><b/><sz val="14"/><name val="Arial"/></font></fonts>
<fills count="{len(fills)}">{''.join(fills)}</fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FF999999"/></left><right style="thin"><color rgb="FF999999"/></right><top style="thin"><color rgb="FF999999"/></top><bottom style="thin"><color rgb="FF999999"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="{len(xfs)}">{''.join(xfs)}</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

# --- Time Line ---
NF=6  # fixed cols before gantt
ndays=len(DAYS); IDCOL=NF+ndays*3
h1=[('팀',S['hdr']),('구분',S['hdr']),('작업 (9/18 금 ~ 9/23 수 저녁 동결 · 9/29 시연 · 9/30 11:00 제출·발표)',S['hdr']),('담당',S['hdr']),('진행',S['hdr']),('상태',S['hdr'])]
h2=[('',S['hdr'])]*NF
merges=[]
for d,(dd,wd) in enumerate(DAYS):
    h1+= [(f'{dd}({wd})',S['day']),('',S['day']),('',S['day'])]
    h2+= [(p,S['day']) for p in PARTS]
    a=col(NF+d*3); b=col(NF+d*3+2); merges.append(f'{a}2:{b}2')
h1.append(('ID\n(브랜치용)',S['hdr'])); h2.append(('',S['hdr'])); merges.append(f'{col(IDCOL)}2:{col(IDCOL)}3')
for i in range(NF): merges.append(f'{col(i)}2:{col(i)}3')
merges.append(f'C1:{col(IDCOL)}1')
legend=[('',S['txt']),('',S['txt']),('담당 약자: S 한석형(팀장·F1) · M 민범진(F2·flow·통합) · P 박진용(F3·안전) · H 황인재(PM·F4 웹)   |   색: 초록 계획 · 빨강 시연 필수 경로 · 노랑 회의·브리핑·제출 · 회색 완료',S['team'])]+[('',S['txt'])]*(NF-3+ndays*3+1)
rows=[legend,h1,h2]
last_team=None
for team,cat,task,own,tid,sp,colr,deliv,crit,note in T:
    cells=[(team if team!=last_team else '',S['team'] if team!=last_team else S['txt']),(cat,S['ctr']),(task,S['txt']),(own,S['ctr']),(status_of(tid)[0],S['ctr']),(status_of(tid)[1],S['ctr'])]
    last_team=team
    g=[('',S['txt'])]*(ndays*3)
    for s in sp.split(','):
        a,b=(s.split('-')+[None])[:2]; b=b or a
        i0=int(a[0])*3+'ABC'.index(a[1]); i1=int(b[0])*3+'ABC'.index(b[1])
        for i in range(i0,i1+1): g[i]=('',S['x'] if status_of(tid)[1]=='완료' else S[colr])
    rows.append(cells+g+[(tid,S['ctr'])])
tl=sheet(rows,[9,8,60,9,6,8]+[4.5]*(ndays*3)+[11],merges,freeze=(NF,3))
# --- 상세 ---
rows=[[(h,S['hdr']) for h in ['ID','팀','작업','담당','산출물','완료 기준','비고(로봇·통합·이동)']]]
for team,cat,task,own,tid,sp,colr,deliv,crit,note in T:
    rows.append([(tid,S['ctr']),(team,S['ctr']),(task,S['txt']),(own,S['ctr']),(deliv,S['txt']),(crit,S['txt']),(note,S['txt'])])
detail=sheet(rows,[11,9,60,9,30,34,30],freeze=(1,1))
# --- 완료 목록 ---
done=sheet([[(h,S['hdr']) for h in ['ID','작업','담당','산출물','시작','종료','영상 파일']]],[11,60,9,30,12,12,40])
# --- 규칙 ---
rows=[[('운영 규칙 (PreWash-Cell 일정표 v2)',S['title'])],[(h,S['hdr']) for h in ['구분','항목','내용']]]
for a,b,cc in RULES: rows.append([(a,S['ctr']),(b,S['txt']),(cc,S['txt'])])
rules=sheet(rows,[12,26,110])
# --- 변경이력 ---
rows=[[(h,S['hdr']) for h in ['#','구분','대상','변경 내용','사유','영향 담당']]]
for r in HIST: rows.append([(v,S['txt']) for v in r])
hist=sheet(rows,[6,10,34,90,34,10])

import json
ex=json.load(open(__import__('os').path.join(__import__('os').path.dirname(__file__),'extra_sheets.json'),encoding='utf-8'))
rows=[[('강사 일정과 우리 마감',S['title'])]]
for i,r in enumerate(ex['instr']): rows.append([(v,S['hdr'] if i==0 else S['txt']) for v in r])
rows.append([('',S['txt'])]); rows.append([(ex['submit'][0] if ex['submit'] else '',S['txt'])])
rows.append([('',S['txt'])]); rows.append([('마일스톤',S['title'])])
for i,r in enumerate(ex['mile']): rows.append([(v,S['hdr'] if i==0 else S['txt']) for v in r])
rows.append([('',S['txt'])]); rows.append([('로봇 슬롯 (1대 · S 한석형 M 민범진 P 박진용 H 황인재)',S['title'])])
for i,r in enumerate(ex['slot']): rows.append([(v,S['hdr'] if i==0 else S['txt']) for v in r])
for n in ex['slotnote']: rows.append([(n,S['txt'])])
mile=sheet(rows,[16,50,50,50])
names=['Time Line','상세(산출물·완료기준)','마일스톤·로봇 슬롯','완료 목록','규칙','변경이력']
wb='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{esc(n)}" sheetId="{i+1}" r:id="rId{i+1}"/>' for i,n in enumerate(names))+'</sheets></workbook>'
wbrels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>' for i in range(6))+'<Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'
ct='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(6))+'</Types>'
rels='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
out=sys.argv[1] if len(sys.argv)>1 else 'prewash_개발일정_v2.xlsx'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml',ct); z.writestr('_rels/.rels',rels); z.writestr('xl/workbook.xml',wb); z.writestr('xl/_rels/workbook.xml.rels',wbrels); z.writestr('xl/styles.xml',styles)
    for i,s in enumerate([tl,detail,mile,done,rules,hist]): z.writestr(f'xl/worksheets/sheet{i+1}.xml',s)
print('rows',len(T),'->',out)

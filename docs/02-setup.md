# 다른 PC 설치와 실행

## 준비물

1. Windows PC와 정상 설치·로그인된 마비노기 모바일 PC판.
2. 사용자가 직접 게임의 환경 설정 → 게임 → AI 제어에서 커넥터를 활성화. [공식 안내](https://mabinogimobile.nexon.com/Info/Guide/3545322)
3. MobiWorks **Beta 1.0.11 원본 배포 폴더**. 원본 코드가 가리키는 배포 사이트는 `https://wo.mobimml.com/`입니다. 조사 도구에서는 사이트 본문에 접근하지 못했으므로 현재 다운로드 가능 여부와 파일 신뢰성은 직접 확인해야 합니다. 임의 미러의 exe는 받지 마세요.
4. 원본 `python/` 전체(기존 검증 Python 3.12.10), `app/vendor/WebView2Loader.dll`, WebView2 Runtime, 아이콘과 `app/ui/folio/fonts/*.woff2`. 원본에 tkinter/필요 DLL이 갖춰진 구성을 유지합니다.
5. GitHub 저장소 ZIP 또는 git clone. 저장소의 코드만으로 위 바이너리를 대체하지 않습니다.

## 권장 경로 예시

```text
D:\MobiWorks\                 원본 배포 폴더 + 적용 소스
  python\pythonw.exe
  app\server.py
  app\vendor\WebView2Loader.dll
  app\data-location.json       이 PC에서 생성, 커밋 금지
D:\MobiWorksData\             개인 설정·큐·로그 (저장소 밖)
D:\Sources\mobinogi-checklist\ 이 저장소
```

## 적용 절차

기존 설치에 덮어쓸 때는 앱을 정상 종료하고 진행 중 명령이 없음을 먼저 확인합니다. 스크립트는 실행 중 앱을 강제 종료하거나 자동 업데이트하지 않습니다.

```powershell
cd D:\Sources\mobinogi-checklist
# 기본은 계획만 표시. 원본 누락과 경로 겹침도 검사합니다.
.\scripts\Install-OverlaySources.ps1 -AppRoot D:\MobiWorks
# 확인한 뒤 적용. 변경 대상 파일을 별도 백업하고 덮어씁니다.
.\scripts\Install-OverlaySources.ps1 -AppRoot D:\MobiWorks -Apply
# 데이터 위치는 절대 경로. 기존 설정이 있으면 별도로 백업합니다.
.\scripts\Set-DataLocation.ps1 -AppRoot D:\MobiWorks -DataRoot D:\MobiWorksData
```

새 PC에서 개인 데이터 없이 시작하려면 새 데이터 폴더를 사용합니다. 개인 큐나 프리셋까지 옮기려면 앱이 꺼진 상태에서 기존 데이터의 별도 비공개 백업을 전달해야 합니다. 이 저장소와 Notion에는 그 개인 파일을 올리지 않았습니다. `lite.json`, 브라우저 프로필, 인증키는 다른 PC로 복제하지 않습니다.

`config/settings.example.json`은 읽기용 예시입니다. 기본값을 전체 덮어쓰거나 기존 큐를 생성하지 않습니다. 특히 `overlay_auto_collect`를 켜면 사용자가 직접 담지 않은 수령 카드가 생길 수 있으므로 선택 의도를 확인합니다.

## 실행 방법

```powershell
.\scripts\Start-Overlay.ps1 -AppRoot D:\MobiWorks
```

일반 실행을 먼저 사용합니다. 게임과 입력/오버레이의 권한 수준 차이가 실제 문제인 경우에만 아래 선택형 실행기를 사용합니다.

```powershell
# 최초 1회: 사용자가 연 관리자 PowerShell에서만 수행
.\scripts\Install-ApprovedLauncher.ps1 -AppRoot D:\MobiWorks -TaskName 'MobiWorks - Overlay Launch'
# 이후 일반 PowerShell/바로가기에서 승인된 고정 작업 실행
schtasks /Run /TN "MobiWorks - Overlay Launch"
```

이 작업은 지정된 Python과 server.py만 실행합니다. Windows UAC를 끄지 않으며 게임 확인창을 누르지도 않습니다. 관리자 실행 파일 경로를 다른 프로그램이 바꾸지 못하도록 폴더 ACL을 관리해야 합니다. 스크립트는 기존 작업 이름을 조용히 덮어쓰지 않고, 설치 후 자동 실행하지 않습니다.

## 첫 실행 점검

- 서버 실행 뒤 지정한 데이터 폴더에 새 `lite.json`이 생기는지 확인.
- 본 앱과 오버레이가 동일한 큐를 표시하는지 확인. `%LOCALAPPDATA%\MobiWorks`의 예전 데이터와 섞이지 않도록 주의.
- 가공/작업/음악/관리 메뉴가 열리고, 시작 전 수량·재료·수령 방식을 검토.
- 설정의 공식 CLI 경로가 실제 설치의 `MabinogiMobile_CLI.exe`인지 확인. 다른 exe를 지정하지 않음.
- 원격 연결은 필요할 때만 별도 설정. GitHub Pages는 로컬 게임 커넥터가 아니며 기존 웹 체크리스트 index.html은 제거됨.
- 첫 누적시간 0은 새 관찰기 시작점일 뿐 게임 타이머가 0이라는 뜻이 아님.

새 PC 실제 게임 통합 실행은 아직 검증하지 않았습니다. 적용 스크립트의 모의 설치·경로·백업 검증과 현재 PC 적용 검증은 개발 문서에 구분해 기록합니다.

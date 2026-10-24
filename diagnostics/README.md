# 非本番・진단용 소스

앱의 자동 실행 경로에 연결하지 않습니다. `InputPrivilegeProbe.cs`는 관련 프로세스의 권한 상태를 조회하고 `MouseInputMonitor.cs`는 사용자가 켠 동안 마우스 위치/버튼만 관찰합니다. 키보드 수집이나 게임 확인 자동 처리는 없습니다.

빌드 예시 (Windows .NET Framework C# compiler 경로는 PC마다 확인):

```powershell
csc /target:exe InputPrivilegeProbe.cs
csc /target:winexe /reference:System.Windows.Forms.dll /reference:System.Drawing.dll MouseInputMonitor.cs
```

관찰 로그는 개인 정보가 될 수 있으므로 저장소에 추가하지 않습니다. 프로세스 감시의 누락/권한 차이가 존재할 수 있습니다. 상세 사실·추론·미검증 범위는 `docs/08-input-experiments.md`를 읽으세요. 과거의 좌표 고정 클릭/확인창 자동화 도우미 exe와 소스는 운영 도구로 오해하지 않도록 제외했습니다.

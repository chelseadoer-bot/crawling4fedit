"""
Windows 작업 스케줄러에 주간 크롤링 작업을 등록하는 스크립트.
관리자 권한으로 실행하세요.

사용법:
  python setup_scheduler.py         # 등록
  python setup_scheduler.py remove  # 제거
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "backend" / "scripts" / "weekly_crawl.py"
PYTHON = sys.executable

TASK_NAME = "FashionCrawlingWeekly"

# XML 작업 스케줄러 정의 — 매일 09:00 실행
TASK_XML = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>패션 크롤링 주간 자동 실행 (매일 09:00, 요일별 브랜드 그룹)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT4H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{PYTHON}</Command>
      <Arguments>"{SCRIPT}"</Arguments>
      <WorkingDirectory>{PROJECT_ROOT}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def register():
    xml_path = PROJECT_ROOT / "data" / "task_schedule.xml"
    xml_path.parent.mkdir(parents=True, exist_ok=True)
    xml_path.write_text(TASK_XML, encoding="utf-16")

    result = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"[OK] 작업 스케줄러 등록 완료: {TASK_NAME}")
        print(f"  실행 시각: 매일 오전 09:00")
        print(f"  스크립트: {SCRIPT}")
        print(f"\n작업 확인: schtasks /Query /TN {TASK_NAME} /FO LIST")
    else:
        print(f"[ERR] 등록 실패:\n{result.stderr}")
        print("관리자 권한으로 실행해 주세요.")


def remove():
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"[OK] 작업 삭제됨: {TASK_NAME}")
    else:
        print(f"[ERR] 삭제 실패: {result.stderr}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove()
    else:
        register()

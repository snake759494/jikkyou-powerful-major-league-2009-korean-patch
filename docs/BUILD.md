# 재빌드

게임 원본·추출물·글꼴·외부 실행 파일은 별도로 준비해야 합니다. 배포용 ISO는 Windows/Python 3.13에서 제작했습니다. 라이브러리 버전은 requirements.txt에 기록했습니다.

1. 해시가 일치하는 원본 ISO를 루트의 `Jikkyou Powerful Major League 2009 (Japan).iso`로 준비합니다.
2. FONT_CREDITS.md에 적힌 네 가지 글꼴을 루트에 놓습니다.
3. 다음 명령을 저장소 루트에서 순서대로 실행합니다.

```powershell
python -m pip install -r requirements.txt
python tools/prepare.py
python tools/build_font.py
python tools/build.py
```

prepare.py는 원본 해시를 확인하고 PROJECT.BIN·SLPM_551.55 및 PACK 파일을 `work/`에 추출합니다. 기존 작업을 덮어쓰지 않도록 work 폴더가 있으면 중단합니다. 이름 입력 배치와 텍스처 목록은 metadata에서 복사합니다. 이 과정에서 새 번역 단위를 추출하거나 번역 ID를 재생성하지 않습니다.

build.py는 원본 ISO에서 시작해 임시 파일에 반영하고 읽기 검사를 통과한 뒤 한글 ISO로 교체합니다. 번역 적용 오류가 있으면 중단합니다. 결과 해시는 release_manifest.json과 비교하세요.

공개용 소스는 배포 빌드의 최종 명세를 포함합니다. 이번 공개 작업에서는 적용기와 릴리즈 xdelta의 복원 결과를 검증했습니다. 공개 저장소를 새 환경에서 전체 재빌드한 결과까지 동일하다고 검증한 것은 아닙니다. Pillow·폰트·수치 라이브러리 버전 변경에 따라 렌더링 바이트가 달라질 수 있습니다.

# 실황 파워풀 메이저리그 2009 PS2 한글패치

PS2 일본판 **実況パワフルメジャーリーグ2009 (Jikkyou Powerful Major League 2009, SLPM-55155)** 용 비공식 한국어 패치입니다. 메뉴·도움말·대사·선수 이름·이름 입력·이미지 글자를 한글화한 기존 작업에 HUD와 선수 정보 이미지 개선을 반영했습니다. 현재 배포판은 **v1.0 (2026-10-02)** 입니다.

[패치 다운로드](https://github.com/snake759494/jikkyou-powerful-major-league-2009-korean-patch/releases/latest) · [기술 설명](docs/TECHNICAL.md) · [재빌드](docs/BUILD.md) · [변경 기록](CHANGELOG.md) · [권리 안내](RIGHTS.md)

릴리즈 첨부 파일은 **PowerfulMajorLeague2009_PS2_KO_v1.0.xdelta 하나**입니다. 저장소에는 제작 도구·번역 대역표·검증 자료를 공개합니다. 원본 및 완성 ISO, 추출된 게임 바이너리·이미지·음성·영상, 글꼴 파일, 외부 실행 파일은 포함하지 않습니다.

> `translation/`에는 대사와 선수 소개 등 번역 대역표가 있으므로 **스포일러**가 포함됩니다.
> 이번 빌드는 ISO 내부 검사와 xdelta 복원 검증을 통과했지만, **새 빌드의 실제 게임 화면 검증은 미완료**입니다. 모든 화면의 가독성이나 전체 진행을 보증하는 완성 검수판은 아닙니다.

## 대상 버전

수정되지 않은 **PS2 일본판 SLPM-55155 DVD ISO (2,048바이트 섹터)** 에 적용합니다. 파일명보다 크기와 해시가 일치하는지가 중요합니다.

| 항목 | 값 |
| --- | --- |
| 게임 ID | SLPM-55155 |
| 원본 ISO 크기 | 2,243,690,496 바이트 |
| **원본 ISO MD5** | `829d72b0c23e934438f5114135736441` |
| 원본 ISO SHA-1 | `bfc2f87d8e1f2bb142010d3489b7bd5ba6369537` |
| 원본 ISO SHA-256 | `452d333097a9fa25b260e4272e6ac5434561e9d9547fca6a05bcb66d9e3328e6` |
| xdelta 크기 | 14,226,917 바이트 |
| xdelta SHA-256 | `6fc3b99208a6230f40e79dd426cddaffa4a62aed4964267cffa444c2041a913f` |
| 결과 ISO 크기 | 2,243,690,496 바이트 |
| 결과 ISO SHA-1 | `10a8b5f6a01a786e5655b545797275aba80e6413` |
| 결과 ISO SHA-256 | `21dbfe67e83caad217044fef92aa78813912122974b6c30c957673af9acd9aac` |

## 패치 적용 방법

### 원본 확인 (Windows)

```powershell
Get-FileHash -Algorithm MD5 -LiteralPath '.\Jikkyou Powerful Major League 2009 (Japan).iso'
```

위 표와 다르면 적용하지 마세요. 다른 지역판이나 CHD·CSO 형식에는 직접 적용할 수 없습니다.

### xdelta UI 사용

1. 릴리즈에서 `PowerfulMajorLeague2009_PS2_KO_v1.0.xdelta`를 받습니다.
2. xdelta3 패치를 지원하는 도구의 **Apply Patch**를 엽니다.
3. **Patch**에 xdelta, **Source File**에 해시가 일치하는 원본 ISO를 선택합니다.
4. **Output File**에 새 파일명을 지정합니다. 원본 파일을 덮어쓰지 마세요.

기존 게임 패치와 동일하게 2차 압축과 파일 경로 헤더 없이 만들었습니다. xdelta는 [공식 프로젝트](https://github.com/jmacd/xdelta)를 참고하세요.

### 명령줄 사용

```powershell
.\xdelta3.exe -d -s '.\Jikkyou Powerful Major League 2009 (Japan).iso' '.\PowerfulMajorLeague2009_PS2_KO_v1.0.xdelta' '.\Jikkyou Powerful Major League 2009 (Japan) (Korean).iso'
```

해시 자동 검사 적용기(Python 3 + xdelta3, 기존 출력 파일 덮어쓰기 금지):

```powershell
python tools/apply_release.py --xdelta .\xdelta3.exe --source '.\Jikkyou Powerful Major League 2009 (Japan).iso' --patch .\PowerfulMajorLeague2009_PS2_KO_v1.0.xdelta --output '.\Jikkyou Powerful Major League 2009 (Japan) (Korean).iso'
```

### PCSX2에서 실행

한글판 ISO를 **새로 부팅**하세요. 이전 버전 세이브스테이트에는 이전 이미지 메모리가 포함되므로 불러오지 말고, 게임 내 메모리카드 저장을 사용하세요. 실기 및 새 빌드 실행 화면 검증은 미완료입니다.

## 작업 내용과 범위

| 구분 | 내용 |
| --- | --- |
| 게임 문장 | 메뉴·도움말·메모리카드 안내·마이 라이프·석세스 대사 등 |
| 선수 정보 | 선수 이름 DB, 선수 카드 이름·소개, 실황 호출명 목록, 기록 보유 선수 명단 |
| 스크립트 | 석세스 대사 스크립트 적용 11,794조각 |
| 글꼴·이름 입력 | 나눔스퀘어 네오 기반 한글 2,350자 및 이름 입력판 |
| 이미지 | 이미지 명세 1,207종, 전체 빌드 이미지 적용 1,388곳 |
| 이번 품질 개선 | 이미지 49종의 398개 항목 보정, 공유 참조 64곳 반영 |

이번 개선은 회차의 `회·초·말`, `투구수·방어율`, 일시정지 메뉴 `컨트롤러`, 선수 정보 구종명·능력치·탭 번호·특수능력 버튼, 투명도 전용 팀 이름을 중심으로 진행했습니다. 일본어 원문 칸과 어긋난 좌표, 과도한 배경 복원, 색상 인덱스 오판을 수정했습니다.

## 검증과 알려진 한계

- 번역 적용 오류 0건. 전체 빌드 기록 1,780곳 읽기 검증.
- 최종 변경 이미지 64곳의 ISO 픽셀·팔레트 일치, 수정 범위 밖 픽셀 보존, 번역 칸 겹침 검사 통과.
- 릴리즈 xdelta를 원본 ISO에 적용한 결과의 SHA-256 일치 확인.
- 실제 게임 화면 검증은 창 제어 도구의 입력 위치 문제로 완료하지 못했습니다. 새 스크린샷을 검증 증거로 제시하지 않습니다.
- 경기 중 별도 음절 글꼴로 출력되는 구종명은 음역 방식이 남아 있습니다(예: `스트레-트`). 이번 선수 정보용 완성형 구종 이미지 수정과는 별개입니다.
- 일부 미검수 이미지에는 글자 잔상·줄 넘침 등이 남을 수 있습니다. 전체 경기·시즌·석세스 진행 검수는 미완료입니다.
- 일본어 음성 및 타이틀 로고는 원본 그대로입니다.

## 저장소 구성

| 경로 | 내용 |
| --- | --- |
| `tools/` | 적용·빌드·폰트·아카이브·텍스처 처리 도구 |
| `translation/` | 번역 결과, 원문 매핑·오프셋, 이미지 명세 (스포일러) |
| `metadata/` | 텍스처 위치 목록·이름 입력 배치 정보 |
| `validation/` | 빌드·이미지·복원 검사 기록 |
| `docs/` | 기술 설명·재빌드 절차·글꼴 출처 |
| `release_manifest.json` | 배포 파일과 원본·결과 해시 |

오역·잘림 신고에는 모드, 화면 위치, 스크린샷, 사용한 패치 버전과 새 부팅 여부를 함께 남겨 주세요.

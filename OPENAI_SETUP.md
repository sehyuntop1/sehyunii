# GPT-5.6 Luna 설정

이 버전은 Gemini 대신 OpenAI Responses API와 `gpt-5.6-luna`를 사용합니다.

## 환경변수

배포 환경 또는 로컬 `.env`에 다음 값을 설정하세요.

```env
TELEGRAM_BOT_TOKEN=텔레그램_봇_토큰
OPENAI_API_KEY=OpenAI_API_키
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_REFINEMENT=low
OPENAI_REASONING_MAPPING=low
OPENAI_REASONING_SUMMARY=low
OPENAI_MAX_OUTPUT_TOKENS=32768
```

- 이 봇은 이미 슬라이드 마커가 있는 정제본을 합치고 짧게 요약하므로 모든 AI 작업을 `low`로 설정했습니다.
- `.env` 파일이나 실제 API 키는 Git에 커밋하지 마세요.
- 기존 배포 환경의 `GEMINI_API_KEY`는 더 이상 사용하지 않습니다.

## 실행

```bash
pip install -r requirements.txt
python main.py
```

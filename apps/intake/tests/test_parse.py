from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from contracts.drafts import ChildRef, ParseRequest
from intake.parse import IntakeUnavailable, parse_sentence
from intake.settings import Settings
from llm.fake import FakeLanguageModel

JERUSALEM = ZoneInfo("Asia/Jerusalem")
CHILD = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2025, 6, 1, 10, tzinfo=JERUSALEM)


def settings(**overrides: str) -> Settings:
    values = {
        "INTERNAL_API_TOKEN": "test-internal-token",
        "LLM_PROVIDER": "fake",
        "LLM_API_KEY": "",
        "LLM_MODEL": "gpt-4.1-mini",
        "APP_TIMEZONE": "Asia/Jerusalem",
        "LOG_LEVEL": "INFO",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def request(text: str, locale: str = "en") -> ParseRequest:
    return ParseRequest(
        text=text,
        locale_hint=locale,  # type: ignore[arg-type]
        now=NOW,
        timezone="Asia/Jerusalem",
        children=[ChildRef(id=CHILD, token="child_1")],
    )


@pytest.mark.asyncio
async def test_fixed_english_and_hebrew_phrases() -> None:
    model = FakeLanguageModel()
    cfg = settings()
    dentist = await parse_sentence(request("dentist tomorrow at 16:00 for child_1"), cfg, model)
    assert dentist.status == "ready"
    assert dentist.draft is not None
    assert dentist.draft.title == "dentist"
    assert dentist.draft.child_ids == [CHILD]
    assert dentist.draft.starts_at.astimezone(JERUSALEM).hour == 16
    assert dentist.draft.starts_at.date().isoformat() == "2025-06-02"

    hebrew = await parse_sentence(request("רופא שיניים מחר בשעה 16:00 ל-child_1", "he"), cfg, model)
    assert hebrew.status == "ready"
    assert hebrew.draft is not None
    assert "רופא" in hebrew.draft.title

    shabbat = await parse_sentence(request("swim on shabbat at 09:30 for child_1"), cfg, model)
    assert shabbat.draft is not None
    assert shabbat.draft.starts_at.date().isoformat() == "2025-06-07"

    erev = await parse_sentence(request("dinner erev chag at 18:00 for child_1"), cfg, model)
    assert erev.draft is not None
    assert erev.draft.starts_at.date().isoformat() == "2025-06-01"

    after = await parse_sentence(request("מוזיאון אחרי החג בשעה 11:00 ל-child_1", "he"), cfg, model)
    assert after.status == "needs_clarification" or after.draft is not None
    # 1 June 2025 is erev Shavuot, outside the block, so after-chag is 3 June (7 Sivan).
    if after.draft is not None:
        assert after.draft.starts_at.date().isoformat() == "2025-06-03"


@pytest.mark.asyncio
async def test_missing_time_and_unknown_name() -> None:
    model = FakeLanguageModel()
    cfg = settings()
    missing = await parse_sentence(request("dentist tomorrow for child_1"), cfg, model)
    assert missing.status == "needs_clarification"
    assert missing.questions

    unknown = await parse_sentence(request("dentist tomorrow at 16:00 for Dana"), cfg, model)
    assert unknown.status == "needs_clarification"
    assert "child" in unknown.questions[0].lower() or "know" in unknown.questions[0].lower()


@pytest.mark.asyncio
async def test_fixture_overrides_the_phrase_table() -> None:
    model = FakeLanguageModel(
        {
            "dentist tomorrow at 16:00 for child_1": {
                "status": "extract",
                "title": "from fixture",
                "child_tokens": ["child_1"],
                "date_token": "tomorrow",
                "time_hhmm": "16:00",
                "all_day": False,
                "unknown_child": False,
            }
        }
    )
    result = await parse_sentence(
        request("dentist tomorrow at 16:00 for child_1"), settings(), model
    )
    assert result.draft is not None
    assert result.draft.title == "from fixture"


@pytest.mark.asyncio
async def test_openai_without_a_key_is_unavailable() -> None:
    with pytest.raises(IntakeUnavailable):
        await parse_sentence(
            request("dentist tomorrow at 16:00 for child_1"),
            settings(LLM_PROVIDER="openai"),
            FakeLanguageModel(),
        )

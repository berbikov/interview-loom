import pytest
from pydantic import ValidationError

from app.schemas import AIAnalysis

VALID_ANALYSIS = {
    "overall_score": 70,
    "criteria": {
        "structure": 70,
        "clarity": 80,
        "specificity": 60,
        "relevance": 75,
        "confidence": 65,
    },
    "summary": "Ответ понятный, но ему не хватает измеримого результата.",
    "strengths": ["Понятно описана личная роль", "Есть контекст проекта"],
    "weaknesses": ["Не назван итоговый эффект", "Мало конкретных метрик"],
    "filler_words": [{"word": "типа", "count": 4}],
    "recommendations": ["Добавить результат в цифрах", "Использовать структуру STAR"],
    "improved_answer": "В проекте я отвечал за проверку гипотезы и рост конверсии.",
    "follow_up_question": "Как именно вы измеряли результат гипотезы?",
}


def test_ai_analysis_validation_accepts_contract() -> None:
    analysis = AIAnalysis.model_validate(VALID_ANALYSIS)

    assert analysis.overall_score == 70
    assert analysis.filler_words[0].word == "типа"


def test_ai_analysis_validation_rejects_invalid_score() -> None:
    invalid_analysis = {**VALID_ANALYSIS, "overall_score": 101}

    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(invalid_analysis)


def test_ai_analysis_migrates_legacy_ten_point_scores() -> None:
    legacy = {
        **VALID_ANALYSIS,
        "overall_score": 7,
        "structure_score": 7,
        "clarity_score": 8,
        "specificity_score": 6,
    }
    legacy.pop("criteria")

    analysis = AIAnalysis.model_validate(legacy)

    assert analysis.overall_score == 70
    assert analysis.criteria.structure == 70

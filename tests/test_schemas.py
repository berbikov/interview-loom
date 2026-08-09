import pytest
from pydantic import ValidationError

from app.schemas import AIAnalysis

VALID_ANALYSIS = {
    "overall_score": 7,
    "structure_score": 7,
    "clarity_score": 8,
    "specificity_score": 6,
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

    assert analysis.overall_score == 7
    assert analysis.filler_words[0].word == "типа"


def test_ai_analysis_validation_rejects_invalid_score() -> None:
    invalid_analysis = {**VALID_ANALYSIS, "overall_score": 11}

    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(invalid_analysis)


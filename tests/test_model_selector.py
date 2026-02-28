"""Tests for the ModelSelector class."""

from __future__ import annotations

import pytest

from src.api.model_selector import AVAILABLE_MODELS, ModelSelector


@pytest.fixture
def selector() -> ModelSelector:
    """Create a ModelSelector instance."""
    return ModelSelector()


def test_init_default_model() -> None:
    """ModelSelector should initialize with default model."""
    selector = ModelSelector(default_model="mistral-large-latest")
    assert selector._default_model == "mistral-large-latest"


def test_select_model_uses_custom_default() -> None:
    """Should use custom default model for simple queries."""
    selector = ModelSelector(default_model="mistral-large-latest")
    result = selector.select_model("What is the capital of France?")
    assert result == "mistral-large-latest"


def test_select_model_with_images(selector: ModelSelector) -> None:
    """Should select multimodal model when images are present."""
    result = selector.select_model("Что на этой картинке?", has_images=True)
    assert result == "pixtral-12b-latest"


def test_select_model_code_python(selector: ModelSelector) -> None:
    """Should select code model for Python-related queries."""
    prompts = [
        "Write a Python function to sort a list",
        "How to debug this code?",
        "Explain this algorithm in Python",
        "Напиши функцию на Python",
    ]
    for prompt in prompts:
        result = selector.select_model(prompt)
        assert result == "codestral-latest", f"Failed for prompt: {prompt}"


def test_select_model_code_javascript(selector: ModelSelector) -> None:
    """Should select code model for JavaScript queries."""
    prompt = "Create a JavaScript function for form validation"
    result = selector.select_model(prompt)
    assert result == "codestral-latest"


def test_select_model_code_block(selector: ModelSelector) -> None:
    """Should select code model when code blocks are present."""
    prompt = "Fix this code:\n```python\ndef hello():\n  print('hi')\n```"
    result = selector.select_model(prompt)
    assert result == "codestral-latest"


def test_select_model_complex_reasoning(selector: ModelSelector) -> None:
    """Should select medium model for complex reasoning tasks."""
    prompts = [
        "Analyze step by step why this approach is better",
        "Compare and evaluate these three solutions",
        "Explain the reasoning behind this design pattern",
        "Проанализируй почему это работает",
    ]
    for prompt in prompts:
        result = selector.select_model(prompt)
        assert result == "mistral-medium-latest", f"Failed for prompt: {prompt}"


def test_select_model_long_content(selector: ModelSelector) -> None:
    """Should select medium model for long-form content requests."""
    prompts = [
        "Write a detailed explanation of quantum computing",
        "Provide a comprehensive guide to machine learning",
        "Напиши подробную статью о нейронных сетях",
    ]
    for prompt in prompts:
        result = selector.select_model(prompt)
        assert result == "mistral-medium-latest"


def test_select_model_simple_query(selector: ModelSelector) -> None:
    """Should select small/fast model for simple queries."""
    prompts = [
        "What is the capital of France?",
        "Hello, how are you?",
        "Translate this to English",
        "Привет, как дела?",
    ]
    for prompt in prompts:
        result = selector.select_model(prompt)
        assert result == "mistral-small-latest", f"Failed for prompt: {prompt}"


def test_select_model_long_prompt(selector: ModelSelector) -> None:
    """Should select medium model for very long prompts."""
    # Create a prompt with more than 200 words
    long_prompt = " ".join(["word"] * 250)
    result = selector.select_model(long_prompt)
    assert result == "mistral-medium-latest"


def test_select_model_multiple_questions(selector: ModelSelector) -> None:
    """Should select medium model for prompts with multiple questions."""
    prompt = "What is AI? How does it work? Why is it important? When was it invented?"
    result = selector.select_model(prompt)
    assert result == "mistral-medium-latest"


def test_select_model_with_long_context(selector: ModelSelector) -> None:
    """Should select medium model when context is moderately long."""
    result = selector.select_model("Simple question", conversation_length=25000)
    assert result == "mistral-medium-latest"


def test_select_model_with_very_large_context(selector: ModelSelector) -> None:
    """Should select large model only when context exceeds 100k tokens."""
    result = selector.select_model("Simple question", conversation_length=105000)
    assert result == "mistral-large-latest"


def test_is_code_request_python_keywords(selector: ModelSelector) -> None:
    """Should detect Python code keywords."""
    assert selector._is_code_request("def function(): pass")
    assert selector._is_code_request("write a python function to parse data")
    assert selector._is_code_request("class MyClass:")


def test_is_code_request_russian(selector: ModelSelector) -> None:
    """Should detect code-related Russian keywords."""
    assert selector._is_code_request("напиши код для сортировки")
    assert selector._is_code_request("исправь код этой функции")


def test_is_code_request_negative(selector: ModelSelector) -> None:
    """Should not detect code in non-code queries."""
    assert not selector._is_code_request("What is the weather today?")
    assert not selector._is_code_request("Tell me about history")


def test_is_complex_request_step_by_step(selector: ModelSelector) -> None:
    """Should detect complex reasoning requests."""
    assert selector._is_complex_request("Explain step by step how this works")
    assert selector._is_complex_request("Analyze the reasoning behind this decision")


def test_is_complex_request_russian(selector: ModelSelector) -> None:
    """Should detect complex requests in Russian."""
    assert selector._is_complex_request("Проанализируй эту ситуацию")
    assert selector._is_complex_request("Сравни эти два подхода")


def test_is_complex_request_negative(selector: ModelSelector) -> None:
    """Should not detect complexity in simple queries."""
    assert not selector._is_complex_request("Hi there")
    assert not selector._is_complex_request("What's your name?")


def test_get_model_info_existing(selector: ModelSelector) -> None:
    """Should return model characteristics for existing models."""
    info = selector.get_model_info("mistral-small-latest")
    assert info is not None
    assert info.name == "mistral-small-latest"
    assert info.max_context_length == 32000
    assert info.speed_tier == 1


def test_get_model_info_nonexistent(selector: ModelSelector) -> None:
    """Should return None for non-existent models."""
    info = selector.get_model_info("non-existent-model")
    assert info is None


def test_available_models_structure() -> None:
    """All available models should have valid characteristics."""
    assert len(AVAILABLE_MODELS) > 0
    for model_name, characteristics in AVAILABLE_MODELS.items():
        assert characteristics.name == model_name
        assert characteristics.max_context_length > 0
        assert 1 <= characteristics.speed_tier <= 3
        assert 1 <= characteristics.complexity_score <= 3
        assert isinstance(characteristics.supports_code, bool)
        assert isinstance(characteristics.supports_vision, bool)

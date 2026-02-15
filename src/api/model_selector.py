"""Dynamic model selector for Mistral AI based on request analysis."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Token estimation multiplier: Average ratio of tokens to words for typical text
# Based on common tokenizers which generally produce 1.2-1.4 tokens per word
TOKEN_ESTIMATION_MULTIPLIER = 1.3


@dataclass
class ModelCharacteristics:
    """Characteristics of a Mistral AI model."""

    name: str
    max_context_length: int  # Maximum context window in tokens
    speed_tier: int  # 1=fastest, 3=slowest but most capable
    supports_code: bool  # Whether model is optimized for code
    supports_vision: bool  # Whether model supports image input
    complexity_score: int  # 1=simple, 3=complex reasoning


# Mistral free tier models with their characteristics
AVAILABLE_MODELS = {
    "mistral-small-latest": ModelCharacteristics(
        name="mistral-small-latest",
        max_context_length=32000,
        speed_tier=1,
        supports_code=False,
        supports_vision=False,
        complexity_score=1,
    ),
    "codestral-latest": ModelCharacteristics(
        name="codestral-latest",
        max_context_length=32000,
        speed_tier=2,
        supports_code=True,
        supports_vision=False,
        complexity_score=2,
    ),
    "pixtral-12b-latest": ModelCharacteristics(
        name="pixtral-12b-latest",
        max_context_length=128000,
        speed_tier=2,
        supports_code=False,
        supports_vision=True,
        complexity_score=2,
    ),
    "mistral-large-latest": ModelCharacteristics(
        name="mistral-large-latest",
        max_context_length=128000,
        speed_tier=3,
        supports_code=True,
        supports_vision=False,
        complexity_score=3,
    ),
}


class ModelSelector:
    """Analyzes requests and selects the most appropriate Mistral model."""

    def __init__(self, default_model: str = "mistral-small-latest") -> None:
        """
        Initialize the model selector.

        Args:
            default_model: Model to use when no better match is found
        """
        self._default_model = default_model
        logger.info("ModelSelector initialized with default model: %s", default_model)

    def select_model(
        self, prompt: str, conversation_length: int = 0, has_images: bool = False
    ) -> str:
        """
        Select the most appropriate model based on request characteristics.

        Args:
            prompt: The user's message/question
            conversation_length: Number of tokens in conversation history
            has_images: Whether the request includes images

        Returns:
            The selected model name
        """
        # If images are present, use multimodal model
        if has_images:
            logger.info("Selected pixtral-12b-latest due to image input")
            return "pixtral-12b-latest"

        # Analyze prompt characteristics
        is_code_related = self._is_code_request(prompt)
        is_complex = self._is_complex_request(prompt)
        # Rough token estimation using standard multiplier
        total_context = len(prompt.split()) * TOKEN_ESTIMATION_MULTIPLIER + conversation_length

        # Select based on characteristics
        if is_code_related:
            logger.info("Selected codestral-latest due to code-related content")
            return "codestral-latest"

        if is_complex or total_context > 20000:
            logger.info(
                "Selected mistral-large-latest due to complexity or long context "
                "(complex=%s, context=%d)",
                is_complex,
                int(total_context),
            )
            return "mistral-large-latest"

        # Default to configured model for simple queries
        logger.info("Selected %s for simple query", self._default_model)
        return self._default_model

    def _is_code_request(self, prompt: str) -> bool:
        """
        Determine if the request is code-related.

        Args:
            prompt: The user's message

        Returns:
            True if request appears to be code-related
        """
        prompt_lower = prompt.lower()

        # First, check for strong code patterns (code blocks, syntax)
        strong_code_patterns = [
            r"```",  # Code blocks
            r"\bdef\s+\w+\(",  # Python function definition
            r"\bfunction\s+\w+\(",  # JS function definition
            r"\bclass\s+\w+\s*[{:]",  # Class definition
            r"[{}\[\]];.*[{}\[\]]",  # Multiple code syntax elements
        ]

        for pattern in strong_code_patterns:
            if re.search(pattern, prompt):
                return True

        # Code-related keywords in multiple languages (more specific)
        code_keywords = [
            # English - specific programming terms
            r"\bwrite.*code\b",
            r"\bwrite.*function\b",
            r"\bwrite.*class\b",
            r"\bfix.*code\b",
            r"\bfix.*bug\b",
            r"\bdebug\b",
            r"\brefactor\b",
            r"\bprogramming\b",
            r"\bcompile\b",
            r"\bsyntax error\b",
            # Programming language names
            r"\bpython\b",
            r"\bjavascript\b",
            r"\btypescript\b",
            r"\bjava\b(?!script)",
            r"(?<!\w)c\+\+(?!\w)",
            r"(?<!\w)c#(?!\w)",
            r"\brust\b.*\b(lang|code|program)",
            r"\bgo\b.*\b(lang|code|program)",
            # Russian
            r"\bнапиши.*код\b",
            r"\bнапиши.*функци\b",
            r"\bисправ.*код\b",
            r"\bисправ.*ошибк.*программ\b",
            r"\bотладк\b",
            r"\bкомпил\b",
        ]

        for keyword_pattern in code_keywords:
            if re.search(keyword_pattern, prompt_lower):
                return True

        return False

    def _is_complex_request(self, prompt: str) -> bool:
        """
        Determine if the request requires complex reasoning.

        Args:
            prompt: The user's message

        Returns:
            True if request appears to require complex reasoning
        """
        prompt_lower = prompt.lower()

        # Indicators of complex reasoning needs
        complexity_indicators = [
            # Multi-step reasoning
            "step by step",
            "explain why",
            "analyze",
            "compare",
            "evaluate",
            "reasoning",
            "логика",
            "анализ",
            "сравни",
            "оцени",
            "рассужд",
            "почему",
            # Long-form content
            "write an essay",
            "detailed explanation",
            "comprehensive",
            "in-depth",
            "напиши статью",
            "подробн",
            "детальн",
            "всесторон",
            # Complex tasks
            "plan",
            "strategy",
            "design",
            "architecture",
            "solution",
            "план",
            "стратеги",
            "дизайн",
            "архитектур",
            "решение",
        ]

        # Check for complexity indicators
        if any(indicator in prompt_lower for indicator in complexity_indicators):
            return True

        # Check prompt length as indicator of complexity
        word_count = len(prompt.split())
        if word_count > 200:
            return True

        # Check for multiple questions
        question_marks = prompt.count("?")
        if question_marks >= 3:
            return True

        return False

    def get_model_info(self, model_name: str) -> Optional[ModelCharacteristics]:
        """
        Get characteristics of a specific model.

        Args:
            model_name: Name of the model

        Returns:
            ModelCharacteristics if model exists, None otherwise
        """
        return AVAILABLE_MODELS.get(model_name)

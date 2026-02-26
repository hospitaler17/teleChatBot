"""Tests for the Mistral API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.mistral_client import GenerateResponse, MistralClient
from src.api.model_selector import requires_current_date
from src.config.settings import AccessSettings, AppSettings, MistralSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest"),
    )


def test_requires_current_date_with_date_keywords() -> None:
    """requires_current_date() should return True for queries about current date."""
    assert requires_current_date("What happened today?")
    assert requires_current_date("Какие новости сегодня?")
    assert requires_current_date("Какая будет погода завтра?")
    assert requires_current_date("What's the current exchange rate?")
    assert requires_current_date("Покажи последние новости")


def test_requires_current_date_without_date_keywords() -> None:
    """requires_current_date() should return False for queries that don't need current date."""
    assert not requires_current_date("What is Python?")
    assert not requires_current_date("Напиши функцию")
    assert not requires_current_date("Как работает интернет?")
    assert not requires_current_date("Write a poem about love")


@patch("src.api.mistral_client.Mistral")
def test_client_init(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """Client should initialize Mistral with the API key."""
    MistralClient(settings)
    mock_mistral.assert_called_once_with(api_key="fake-key")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should return GenerateResponse with model text and metadata."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Hello from Mistral!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    # Mock usage information
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 15
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    # Check result is GenerateResponse
    assert isinstance(result, GenerateResponse)
    assert result.content == "Hello from Mistral!"
    assert result.input_tokens == 10
    assert result.output_tokens == 15
    assert result.total_tokens == 25

    # Verify that complete_async was called with the expected arguments
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    # Model should be dynamically selected (mistral-small-latest for simple query)
    assert kwargs["model"] == "mistral-small-latest"
    # Ensure the user message content is correctly forwarded
    assert isinstance(kwargs["messages"], list)
    # Should have at least UserMessage (no system prompt configured, no date needed)
    assert len(kwargs["messages"]) >= 1, "Should have at least user message"
    # Last message should be the user message
    assert kwargs["messages"][-1].role == "user"
    assert kwargs["messages"][-1].content == "Hi"
    # Ensure generation settings are passed through
    assert kwargs["max_tokens"] == settings.mistral.max_tokens
    assert kwargs["temperature"] == settings.mistral.temperature


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_system_prompt(mock_mistral: MagicMock) -> None:
    """generate() should include system message when system_prompt is configured."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(
            model="mistral-small-latest", system_prompt="You are a helpful assistant."
        ),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "I'm here to help!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 8
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Hi")
    assert isinstance(result, GenerateResponse)
    assert result.content == "I'm here to help!"

    # Verify messages include both system and user
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    assert len(messages) == 2
    # First message should be system
    assert messages[0].role == "system"
    # System message should contain only the configured prompt
    assert "You are a helpful assistant." in messages[0].content
    # Second message should be user
    assert messages[1].role == "user"
    assert messages[1].content == "Hi"


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_date_context(mock_mistral: MagicMock) -> None:
    """generate() should add current date to system prompt for time-sensitive queries."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest"),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Today is a great day!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 12
    mock_usage.completion_tokens = 6
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query that requires date context (contains "today")
    result = await client.generate("What happened today?", user_id=123)
    assert isinstance(result, GenerateResponse)
    assert result.content == "Today is a great day!"

    # Verify that date was added to system prompt
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # First message should be system message with date
    assert messages[0].role == "system"
    # Check for date/instruction in English (more explicit)
    assert "CURRENT YEAR" in messages[0].content or "CRITICAL CONTEXT" in messages[0].content

    # Also verify that date context was added to conversation memory
    history = client._memory.get_history(123)
    # Should have system context with date
    system_messages = [msg for msg in history if msg["role"] == "system"]
    assert len(system_messages) > 0
    assert "Current date:" in system_messages[0]["content"]


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_without_date_context(
    mock_mistral: MagicMock,
    settings: AppSettings,
) -> None:
    """generate() should NOT add date for queries that don't need current date."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Python is great!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 8
    mock_usage.completion_tokens = 4
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_client.aclose = AsyncMock()
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query that does NOT require date (simple question)
    result = await client.generate("What is Python?")
    assert isinstance(result, GenerateResponse)
    assert result.content == "Python is great!"

    # Verify that date was NOT added to system prompt
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # System message should not contain date
    if len(messages) > 0 and messages[0].role == "system":
        assert "CURRENT YEAR" not in messages[0].content
        assert "CRITICAL CONTEXT" not in messages[0].content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_always_append_date_enabled(mock_mistral: MagicMock) -> None:
    """generate() should add date when always_append_date config and runtime are both True."""
    from src.config.settings import AccessSettings

    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(
            model="mistral-small-latest",
            system_prompt="You are helpful.",
            always_append_date=True,
        ),
        access=AccessSettings(always_append_date_enabled=True),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Python is great!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 15
    mock_usage.completion_tokens = 5
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query that does NOT contain date keywords, but flag is enabled
    result = await client.generate("What is Python?", user_id=456)
    assert isinstance(result, GenerateResponse)
    assert result.content == "Python is great!"

    # Verify that date was added to system prompt despite no date keywords
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # First message should be system message with date
    assert messages[0].role == "system"
    assert "You are helpful." in messages[0].content
    assert "CURRENT YEAR" in messages[0].content
    assert "CRITICAL CONTEXT" in messages[0].content

    # Verify date was added to conversation memory
    history = client._memory.get_history(456)
    system_messages = [msg for msg in history if msg["role"] == "system"]
    assert len(system_messages) > 0
    assert "Current date:" in system_messages[0]["content"]


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_always_append_date_disabled(mock_mistral: MagicMock) -> None:
    """generate() should NOT add date when always_append_date is False and no keywords."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(
            model="mistral-small-latest",
            always_append_date=False,  # Explicitly disabled
        ),
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Python is great!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 8
    mock_usage.completion_tokens = 4
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query without date keywords and flag disabled
    result = await client.generate("What is Python?")
    assert isinstance(result, GenerateResponse)
    assert result.content == "Python is great!"

    # Verify that date was NOT added
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # System message should not contain date
    if len(messages) > 0 and messages[0].role == "system":
        assert "CURRENT YEAR" not in messages[0].content
        assert "CRITICAL CONTEXT" not in messages[0].content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_always_append_date_runtime_disabled(
    mock_mistral: MagicMock,
) -> None:
    """generate() should NOT add date when config is True but runtime toggle is False."""
    from src.config.settings import AccessSettings

    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(
            model="mistral-small-latest",
            always_append_date=True,  # Config enabled
        ),
        access=AccessSettings(always_append_date_enabled=False),  # Runtime disabled
    )

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Python is great!"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 8
    mock_usage.completion_tokens = 4
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    # Query without date keywords
    result = await client.generate("What is Python?")
    assert isinstance(result, GenerateResponse)
    assert result.content == "Python is great!"

    # Verify that date was NOT added (runtime toggle overrides config)
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # System message should not contain date
    if len(messages) > 0 and messages[0].role == "system":
        assert "CURRENT YEAR" not in messages[0].content
        assert "CRITICAL CONTEXT" not in messages[0].content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_code_request(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should select code model for code-related queries."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "def hello(): print('hi')"
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 15
    mock_usage.completion_tokens = 10
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Write a Python function to sort a list")
    assert isinstance(result, GenerateResponse)
    assert result.content == "def hello(): print('hi')"

    # Verify that codestral model was selected
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    assert kwargs["model"] == "codestral-latest"


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_complex_request(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should select large model for complex reasoning queries."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Detailed analysis..."
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 20
    mock_usage.completion_tokens = 30
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    result = await client.generate("Analyze step by step why this approach works")
    assert isinstance(result, GenerateResponse)
    assert result.content == "Detailed analysis..."

    # Verify that large model was selected
    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    assert kwargs["model"] == "mistral-large-latest"


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_error(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should propagate exceptions."""
    mock_client = MagicMock()
    mock_client.chat.complete_async = AsyncMock(side_effect=RuntimeError("API down"))
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(RuntimeError, match="API down"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_empty_choices(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should raise ValueError if API returns no choices."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = []
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(ValueError, match="no choices"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_missing_content(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should raise ValueError if API returns no message content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = None
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 0
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(ValueError, match="no message content"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_non_string_content(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should raise TypeError if API returns non-string content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = 123  # Non-string content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 0
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client

    client = MistralClient(settings)
    with pytest.raises(TypeError, match="non-string"):
        await client.generate("Hi")


@patch("src.api.mistral_client.Mistral")
def test_should_use_web_search_with_explicit_search_requests(
    mock_mistral: MagicMock, settings: AppSettings
) -> None:
    """_should_use_web_search() should return True for explicit search requests."""
    client = MistralClient(settings)

    # Russian explicit search requests
    assert client._should_use_web_search("поищи ка информацию в сети")
    assert client._should_use_web_search("найди информацию о Python")
    assert client._should_use_web_search("поиск новостей")
    assert client._should_use_web_search("искать статьи")
    assert client._should_use_web_search("погугли это")
    assert client._should_use_web_search("узнай что такое")
    assert client._should_use_web_search("посмотри в интернете")
    assert client._should_use_web_search("проверь онлайн")

    # English explicit search requests
    assert client._should_use_web_search("search for information")
    assert client._should_use_web_search("find information about AI")
    assert client._should_use_web_search("find articles about AI")
    assert client._should_use_web_search("look up recent news")
    assert client._should_use_web_search("google this")
    assert client._should_use_web_search("check online")
    assert client._should_use_web_search("search online")
    assert client._should_use_web_search("search the internet")


@patch("src.api.mistral_client.Mistral")
def test_should_use_web_search_with_time_sensitive_queries(
    mock_mistral: MagicMock, settings: AppSettings
) -> None:
    """_should_use_web_search() should return True for time-sensitive queries."""
    client = MistralClient(settings)

    # Time-sensitive queries
    assert client._should_use_web_search("какие новости сегодня?")
    assert client._should_use_web_search("текущая погода")
    assert client._should_use_web_search("последние события")
    assert client._should_use_web_search("что сейчас происходит")
    assert client._should_use_web_search("актуальный курс доллара")
    assert client._should_use_web_search("latest news")
    assert client._should_use_web_search("current weather")
    assert client._should_use_web_search("what happened today")


@patch("src.api.mistral_client.Mistral")
def test_should_use_web_search_without_search_keywords(
    mock_mistral: MagicMock, settings: AppSettings
) -> None:
    """_should_use_web_search() should return False for queries without search keywords."""
    client = MistralClient(settings)

    # General knowledge questions that don't need web search
    assert not client._should_use_web_search("что такое Python?")
    assert not client._should_use_web_search("объясни алгоритм сортировки")
    assert not client._should_use_web_search("напиши функцию")
    assert not client._should_use_web_search("расскажи про квантовую физику")
    assert not client._should_use_web_search("What is machine learning?")
    assert not client._should_use_web_search("Write a poem")
    assert not client._should_use_web_search("Tell me about history")

    # Edge cases that contain broad keywords but should not trigger web search.
    # These help ensure we don't introduce unnecessary web searches (false positives).
    assert not client._should_use_web_search("Can you check this code for errors?")
    assert not client._should_use_web_search("I find Python very interesting")
    assert not client._should_use_web_search("The system is online now")
    assert not client._should_use_web_search("посмотри на этот код")
    assert not client._should_use_web_search("проверь этот код")
    assert not client._should_use_web_search("I can't find my keys")


# ---------------------------------------------------------------------------
# Reasoning mode (chain-of-thought) tests
# ---------------------------------------------------------------------------


def _mock_client_with_response(mock_mistral: MagicMock, content: str = "ok") -> MagicMock:
    """Create a mock Mistral client that returns *content* from complete_async."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_usage.completion_tokens = 5
    mock_response.usage = mock_usage
    mock_client.chat.complete_async = AsyncMock(return_value=mock_response)
    mock_mistral.return_value = mock_client
    return mock_client


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_with_reasoning_mode_enabled(mock_mistral: MagicMock) -> None:
    """generate() should add CoT instruction to system prompt when reasoning mode is active."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest", reasoning_mode=True),
        access=AccessSettings(reasoning_mode_enabled=True),
    )
    mock_client = _mock_client_with_response(mock_mistral)

    client = MistralClient(settings)
    result = await client.generate("Explain quantum entanglement")

    assert isinstance(result, GenerateResponse)

    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    # System message must be present and contain the CoT instruction
    assert messages[0].role == "system"
    assert "REASONING MODE" in messages[0].content
    assert "шаг за шагом" in messages[0].content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_without_reasoning_mode(mock_mistral: MagicMock, settings: AppSettings) -> None:
    """generate() should NOT add CoT instruction when reasoning mode is disabled."""
    mock_client = _mock_client_with_response(mock_mistral)

    client = MistralClient(settings)  # reasoning_mode defaults to False
    result = await client.generate("Explain quantum entanglement")

    assert isinstance(result, GenerateResponse)

    mock_client.chat.complete_async.assert_called_once()
    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    system_content = messages[0].content if messages and messages[0].role == "system" else ""
    assert "REASONING MODE" not in system_content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_reasoning_mode_config_on_runtime_off(mock_mistral: MagicMock) -> None:
    """generate() should NOT add CoT when config is True but runtime toggle is False."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(model="mistral-small-latest", reasoning_mode=True),
        access=AccessSettings(reasoning_mode_enabled=False),  # Runtime disabled
    )
    mock_client = _mock_client_with_response(mock_mistral)

    client = MistralClient(settings)
    result = await client.generate("Explain quantum entanglement")

    assert isinstance(result, GenerateResponse)

    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    system_content = messages[0].content if messages and messages[0].role == "system" else ""
    assert "REASONING MODE" not in system_content


@patch("src.api.mistral_client.Mistral")
@pytest.mark.asyncio
async def test_generate_reasoning_mode_with_existing_system_prompt(mock_mistral: MagicMock) -> None:
    """CoT instruction should be appended after any existing system prompt."""
    settings = AppSettings(
        mistral_api_key="fake-key",
        mistral=MistralSettings(
            model="mistral-small-latest",
            system_prompt="You are a helpful assistant.",
            reasoning_mode=True,
        ),
        access=AccessSettings(reasoning_mode_enabled=True),
    )
    mock_client = _mock_client_with_response(mock_mistral)

    client = MistralClient(settings)
    await client.generate("What is 2+2?")

    _, kwargs = mock_client.chat.complete_async.call_args
    messages = kwargs["messages"]
    system_content = messages[0].content
    assert "You are a helpful assistant." in system_content
    assert "REASONING MODE" in system_content

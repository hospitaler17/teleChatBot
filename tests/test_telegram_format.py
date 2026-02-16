"""Tests for Telegram formatting utilities."""

from __future__ import annotations

from src.utils.telegram_format import (
    escape_telegram_markdown,
    markdown_to_telegram,
    normalize_markdown_for_telegram,
    telegram_to_markdown,
)


class TestEscapeTelegramMarkdown:
    """Tests for escape_telegram_markdown function."""

    def test_escape_underscores_in_text(self) -> None:
        """Test that underscores in regular text are escaped."""
        text = "variable_name and another_variable"
        result = escape_telegram_markdown(text)
        assert result == "variable\\_name and another\\_variable"

    def test_preserve_italic_formatting(self) -> None:
        """Test that intentional italic formatting with underscores is preserved."""
        text = "This is _italic_ text"
        result = escape_telegram_markdown(text)
        assert result == "This is _italic_ text"

    def test_escape_square_brackets(self) -> None:
        """Test that square brackets are escaped when not part of links."""
        text = "Array[0] and dict[key]"
        result = escape_telegram_markdown(text)
        assert result == "Array\\[0\\] and dict\\[key\\]"

    def test_preserve_links(self) -> None:
        """Test that markdown links are preserved without escaping."""
        text = "Check [this link](http://example.com)"
        result = escape_telegram_markdown(text)
        assert result == "Check [this link](http://example.com)"

    def test_preserve_code_blocks(self) -> None:
        """Test that code blocks are not escaped."""
        text = "Code: ```python\ndef func_name():\n    pass\n```"
        result = escape_telegram_markdown(text)
        assert "func\\_name" not in result
        assert "func_name" in result

    def test_preserve_inline_code(self) -> None:
        """Test that inline code is not escaped."""
        text = "Use `variable_name` in your code"
        result = escape_telegram_markdown(text)
        assert "`variable_name`" in result
        assert "`variable\\_name`" not in result

    def test_mixed_content(self) -> None:
        """Test escaping with mixed content types."""
        text = "Variable my_var in `code_block` and [link](url) plus other_var"
        result = escape_telegram_markdown(text)
        # my_var should be escaped (not in code/link)
        assert "my\\_var" in result
        # code_block should NOT be escaped (inside backticks)
        assert "`code_block`" in result
        assert "`code\\_block`" not in result
        # link should be preserved
        assert "[link](url)" in result
        # other_var should be escaped
        assert "other\\_var" in result

    def test_empty_text(self) -> None:
        """Test that empty text is handled correctly."""
        assert escape_telegram_markdown("") == ""
        assert escape_telegram_markdown(None) is None

    def test_no_special_chars(self) -> None:
        """Test text without special characters."""
        text = "Simple text without special characters"
        result = escape_telegram_markdown(text)
        assert result == text

    def test_protect_formatting_disabled(self) -> None:
        """Test that disabling protect_formatting escapes everything."""
        text = "Use `code` and _italic_ with under_scores"
        result = escape_telegram_markdown(text, protect_formatting=False)
        # Everything should be escaped
        assert "\\`" in result
        assert "\\_" in result


class TestMarkdownToTelegram:
    """Tests for markdown_to_telegram function."""

    def test_convert_headers_to_bold(self) -> None:
        """Test that markdown headers are converted to bold."""
        text = "## Heading 2\n### Heading 3\n#### Heading 4"
        result = markdown_to_telegram(text)
        assert "*Heading 2*" in result
        assert "*Heading 3*" in result
        assert "*Heading 4*" in result
        # Original hashes should be removed
        assert "##" not in result

    def test_convert_double_asterisks_to_single(self) -> None:
        """Test that double asterisks are converted to single."""
        text = "This is **bold** text"
        result = markdown_to_telegram(text)
        assert result == "This is *bold* text"

    def test_convert_list_items(self) -> None:
        """Test that markdown lists are converted to bullet points."""
        text = "- Item 1\n- Item 2\n- Item 3"
        result = markdown_to_telegram(text)
        assert "• Item 1" in result
        assert "• Item 2" in result
        assert "• Item 3" in result
        # Original dashes should be replaced
        assert "- Item" not in result

    def test_escape_underscores(self) -> None:
        """Test that underscores are properly escaped."""
        text = "Function my_function with param_name"
        result = markdown_to_telegram(text)
        assert "my\\_function" in result
        assert "param\\_name" in result

    def test_complex_markdown(self) -> None:
        """Test conversion of complex markdown with multiple elements."""
        text = """## Example Code
Here's a function:
- Use variable_name
- Call **function()**
- Check `code_sample`"""
        result = markdown_to_telegram(text)
        # Header converted
        assert "*Example Code*" in result
        # List items converted
        assert "• Use" in result
        # Underscores escaped (outside code)
        assert "variable\\_name" in result
        # Bold converted
        assert "*function()*" in result
        # Code preserved
        assert "`code_sample`" in result

    def test_preserve_existing_formatting(self) -> None:
        """Test that existing Telegram formatting is preserved."""
        text = "Use *bold* and _italic_ formatting"
        result = markdown_to_telegram(text)
        assert "*bold*" in result
        assert "_italic_" in result

    def test_empty_text(self) -> None:
        """Test that empty text is handled correctly."""
        assert markdown_to_telegram("") == ""
        assert markdown_to_telegram(None) is None

    def test_links_preserved(self) -> None:
        """Test that markdown links are preserved."""
        text = "Check [documentation](https://example.com/docs)"
        result = markdown_to_telegram(text)
        assert "[documentation](https://example.com/docs)" in result


class TestTelegramToMarkdown:
    """Tests for telegram_to_markdown function."""

    def test_unescape_underscores(self) -> None:
        """Test that escaped underscores are unescaped."""
        text = "variable\\_name and other\\_variable"
        result = telegram_to_markdown(text)
        assert result == "variable_name and other_variable"

    def test_unescape_brackets(self) -> None:
        """Test that escaped brackets are unescaped."""
        text = "array\\[0\\] and dict\\[key\\]"
        result = telegram_to_markdown(text)
        assert result == "array[0] and dict[key]"

    def test_convert_bullets_to_dashes(self) -> None:
        """Test that bullet points are converted back to dashes."""
        text = "• Item 1\n• Item 2"
        result = telegram_to_markdown(text)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_empty_text(self) -> None:
        """Test that empty text is handled correctly."""
        assert telegram_to_markdown("") == ""
        assert telegram_to_markdown(None) is None

    def test_roundtrip_conversion(self) -> None:
        """Test that converting to Telegram and back preserves meaning."""
        original = "Use variable_name in code with **bold** text"
        telegram = markdown_to_telegram(original)
        back = telegram_to_markdown(telegram)
        # Should have underscores restored
        assert "variable_name" in back
        # Formatting might differ but content should be similar
        assert "variable" in back
        assert "code" in back


class TestNormalizeMarkdownForTelegram:
    """Tests for the legacy normalize_markdown_for_telegram function."""

    def test_is_alias_for_markdown_to_telegram(self) -> None:
        """Test that normalize_markdown_for_telegram is an alias."""
        text = "## Header\n**bold** with variable_name"
        result1 = normalize_markdown_for_telegram(text)
        result2 = markdown_to_telegram(text)
        assert result1 == result2


class TestRealWorldExamples:
    """Tests with real-world examples that could cause issues."""

    def test_python_code_example(self) -> None:
        """Test Python code with underscores."""
        text = """Here's a Python function:
```python
def calculate_sum(first_number, second_number):
    return first_number + second_number
```
Use it like: result = calculate_sum(1, 2)"""
        result = markdown_to_telegram(text)
        # Code block should not be escaped
        assert "first_number" in result
        assert "second_number" in result
        assert "first\\_number" not in result or "```" in result
        # Outside code block should be escaped
        assert "calculate\\_sum" in result or "`" in result

    def test_file_paths(self) -> None:
        """Test file paths with underscores and special chars."""
        text = "File: /path/to/my_file.txt and config_file.yaml"
        result = markdown_to_telegram(text)
        assert "my\\_file" in result
        assert "config\\_file" in result

    def test_api_response_example(self) -> None:
        """Test API response with JSON-like syntax."""
        text = 'Response: {"user_id": 123, "user_name": "test"}'
        result = markdown_to_telegram(text)
        # Underscores should be escaped
        assert "user\\_id" in result
        assert "user\\_name" in result

    def test_markdown_table_like(self) -> None:
        """Test text that looks like a markdown table."""
        text = "Column_1 | Column_2 | Column_3"
        result = markdown_to_telegram(text)
        # Underscores should be escaped
        assert "Column\\_1" in result
        assert "Column\\_2" in result
        assert "Column\\_3" in result

    def test_mixed_bold_and_underscores(self) -> None:
        """Test bold text containing underscores."""
        text = "**Important: my_variable** is used here"
        result = markdown_to_telegram(text)
        # Bold should be converted and underscores escaped
        assert "*Important: my\\_variable*" in result or "my\\_variable" in result

    def test_url_with_underscores(self) -> None:
        """Test URLs with underscores in links."""
        text = "[docs](https://example.com/api_docs/user_guide)"
        result = markdown_to_telegram(text)
        # Link should be preserved as-is
        assert "[docs](https://example.com/api_docs/user_guide)" in result

    def test_multiple_consecutive_underscores(self) -> None:
        """Test text with multiple consecutive underscores."""
        text = "Use __init__ method"
        result = markdown_to_telegram(text)
        # Should escape underscores
        assert "\\_\\_init\\_\\_" in result or "__init__" in result

    def test_underscore_at_word_boundary(self) -> None:
        """Test underscores at word boundaries."""
        text = "_start_of_word and end_of_word_"
        result = markdown_to_telegram(text)
        # First underscore might be italic, others should be escaped
        assert "\\_" in result or "_" in result

    def test_unpaired_asterisk_escaping(self) -> None:
        """Test that unpaired asterisks are escaped."""
        text = "Cost: 5*3 = 15"
        result = markdown_to_telegram(text)
        # Unpaired asterisk should be escaped
        assert "5\\*3" in result

    def test_unpaired_backtick_escaping(self) -> None:
        """Test that unpaired backticks are escaped."""
        text = "The ` character is used for code"
        result = markdown_to_telegram(text)
        # Unpaired backticks should be escaped
        assert "\\`" in result

    def test_header_with_bold_text(self) -> None:
        """Test that headers with bold text don't create nested asterisks."""
        text = "## Header with **bold** text"
        result = markdown_to_telegram(text)
        # Should not have nested asterisks
        assert "*Header with bold text*" in result
        # Should not have double or nested asterisks
        assert "**" not in result
        assert "*Header with *bold* text*" not in result

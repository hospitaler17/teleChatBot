"""Utilities for converting between Markdown and Telegram formatting.

This module provides conversion functions for handling special characters and formatting
between standard Markdown and Telegram's Markdown format.

Telegram Formatting References:
- Legacy Markdown: https://core.telegram.org/bots/api#markdown-style
- MarkdownV2: https://core.telegram.org/bots/api#markdownv2-style

Key Differences:
1. Legacy Markdown (parse_mode="Markdown"):
   - Supports: *bold*, _italic_, `code`, ```pre```, [link](url)
   - Special characters don't need escaping in most cases
   - Limited formatting options
   - Used by this bot for backward compatibility

2. MarkdownV2 (parse_mode="MarkdownV2"):
   - Supports: *bold*, _italic_, __underline__, ~strikethrough~, ||spoiler||
   - Requires escaping: _ * [ ] ( ) ~ ` > # + - = | { } . !
   - More powerful but requires careful character escaping

3. Standard Markdown (used by AI models):
   - Supports: **bold**, *italic*, # headers, - lists, etc.
   - No special character escaping needed

This Module's Approach:
- Convert standard Markdown (AI output) to Telegram legacy Markdown
- Escape characters that could break Telegram's parser
- Preserve intentional formatting while protecting literal characters
"""

from __future__ import annotations

import re

# Characters that need escaping in Telegram legacy Markdown mode
# These are the main problematic characters that can break formatting
TELEGRAM_ESCAPE_CHARS = r"_*[`"

# Pattern to match code blocks (triple backticks)
CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```", re.MULTILINE)

# Pattern to match inline code (single backticks)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+?`")

# Pattern to match links [text](url)
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")


def escape_telegram_markdown(text: str, protect_formatting: bool = True) -> str:
    """Escape special characters for Telegram legacy Markdown mode.

    This function protects characters that could be misinterpreted as Telegram
    formatting commands. It preserves intentional formatting while escaping
    literal characters.

    Args:
        text: Text to escape
        protect_formatting: If True, preserve code blocks and inline code from escaping

    Returns:
        Text with special characters escaped for Telegram

    Example:
        >>> escape_telegram_markdown("This_is_a_test")
        "This\\_is\\_a\\_test"
        >>> escape_telegram_markdown("Use *bold* text")
        "Use *bold* text"  # Intentional formatting preserved
        >>> escape_telegram_markdown("`code_with_underscore`")
        "`code_with_underscore`"  # Code blocks protected
    """
    if not text:
        return text

    if not protect_formatting:
        # Simple escape: escape all special characters
        return re.sub(f"([{TELEGRAM_ESCAPE_CHARS}])", r"\\\1", text)

    # Advanced escape: protect code blocks and intentional formatting
    # Strategy:
    # 1. Extract code blocks and inline code (don't escape inside them)
    # 2. Escape special characters in regular text
    # 3. Reassemble the text

    placeholders = []
    placeholder_index = 0

    def save_and_replace(match):
        nonlocal placeholder_index
        placeholder = f"\x00PLACEHOLDER{placeholder_index}\x00"
        placeholders.append((placeholder, match.group(0)))
        placeholder_index += 1
        return placeholder

    # Save code blocks first
    text = CODE_BLOCK_PATTERN.sub(save_and_replace, text)

    # Save inline code
    text = INLINE_CODE_PATTERN.sub(save_and_replace, text)

    # Save links (to preserve brackets and parentheses in URLs)
    text = LINK_PATTERN.sub(save_and_replace, text)

    # Now escape special characters in remaining text
    # Strategy: Escape underscores, asterisks, and backticks that are NOT part of formatting

    # Find all underscore pairs that look like italic formatting (_text_)
    italic_pattern = re.compile(r'(?<!\w)_([^\s_][^_]*?)_(?!\w)')
    italic_matches = []
    for match in italic_pattern.finditer(text):
        italic_matches.append((match.start(), match.end()))

    # Find all asterisk pairs that look like bold formatting (*text*)
    bold_pattern = re.compile(r'(?<!\*)\*([^\s*][^*]*?)\*(?!\*)')
    bold_matches = []
    for match in bold_pattern.finditer(text):
        bold_matches.append((match.start(), match.end()))

    # Escape special characters that are NOT part of intentional formatting
    result = []
    i = 0
    while i < len(text):
        if text[i] == '_':
            # Check if this underscore is part of italic formatting
            in_italic = any(start <= i < end for start, end in italic_matches)
            if in_italic:
                result.append('_')
            else:
                result.append('\\_')
        elif text[i] == '*':
            # Check if this asterisk is part of bold formatting
            in_bold = any(start <= i < end for start, end in bold_matches)
            if in_bold:
                result.append('*')
            else:
                result.append('\\*')
        elif text[i] == '`':
            # Backticks outside of code blocks (already protected) should be escaped
            # to prevent them from being interpreted as inline code delimiters
            result.append('\\`')
        else:
            result.append(text[i])
        i += 1

    text = ''.join(result)

    # Escape square brackets that are not part of links (already saved)
    text = text.replace('[', '\\[').replace(']', '\\]')

    # Restore placeholders
    for placeholder, original in reversed(placeholders):
        text = text.replace(placeholder, original)

    return text


def markdown_to_telegram(text: str) -> str:
    """Convert standard Markdown to Telegram-compatible Markdown format.

    This function handles the conversion of common Markdown syntax used by AI models
    to Telegram's legacy Markdown format. It also escapes special characters that
    could break Telegram's parser.

    Conversions:
    - ## Heading → *Heading* (bold)
    - ### Heading → *Heading* (bold)
    - #### Heading → *Heading* (bold)
    - **text** → *text* (double asterisks to single)
    - - list item → • list item (bullet points)

    Args:
        text: Standard Markdown text (e.g., from AI model)

    Returns:
        Telegram-compatible Markdown text with proper escaping

    Example:
        >>> markdown_to_telegram("## Heading\\n**bold** text\\n- item")
        "*Heading*\\n*bold* text\\n• item"
    """
    if not text:
        return text

    # Step 1: Convert markdown headers to bold
    # Match lines starting with 2-4 hashes followed by space and text
    # To avoid nested asterisks when headers contain bold segments (e.g. "**bold**"),
    # we strip inner markdown bold markers inside headers before wrapping the whole
    # header line in a single pair of asterisks.
    def _convert_header(match):
        header_text = match.group(1)
        # Remove markdown bold markers inside headers, keeping the inner text.
        # This prevents nested/overlapping asterisks like "*Header with *bold* text*".
        header_text = re.sub(r'\*\*(.+?)\*\*', r'\1', header_text)
        return f'*{header_text}*'

    text = re.sub(r'^#{2,4}\s+(.+?)$', _convert_header, text, flags=re.MULTILINE)

    # Step 2: Convert double asterisks to single (markdown bold to Telegram bold)
    # Use a more careful approach to avoid breaking existing single asterisks
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)

    # Step 3: Convert markdown list dashes to bullet points for better readability
    text = re.sub(r'^-\s+', '• ', text, flags=re.MULTILINE)

    # Step 4: Escape special characters that could break Telegram formatting
    text = escape_telegram_markdown(text, protect_formatting=True)

    return text


def telegram_to_markdown(text: str) -> str:
    """Convert Telegram Markdown to standard Markdown format.

    This function reverses the conversion, useful for storing or processing
    messages in standard Markdown format.

    Args:
        text: Telegram Markdown text

    Returns:
        Standard Markdown text

    Example:
        >>> telegram_to_markdown("*bold* text with \\_underscore\\_")
        "**bold** text with _underscore_"
    """
    if not text:
        return text

    # Unescape special characters
    text = text.replace('\\_', '_')
    text = text.replace('\\*', '*')
    text = text.replace('\\[', '[')
    text = text.replace('\\]', ']')
    text = text.replace('\\`', '`')

    # Convert Telegram formatting to standard Markdown
    # Note: This is a simplified conversion and may not handle all edge cases

    # Convert bullet points back to dashes
    text = re.sub(r'^•\s+', '- ', text, flags=re.MULTILINE)

    # Convert single asterisks to double (Telegram bold to Markdown bold)
    # This is tricky because we need to distinguish from italic asterisks
    # For simplicity, we'll leave asterisks as-is since both Markdown and Telegram use them

    return text


def normalize_markdown_for_telegram(text: str) -> str:
    """Legacy function name for backward compatibility.

    This function is an alias for markdown_to_telegram() to maintain
    compatibility with existing code.

    Args:
        text: Standard Markdown text

    Returns:
        Telegram-compatible Markdown text
    """
    return markdown_to_telegram(text)

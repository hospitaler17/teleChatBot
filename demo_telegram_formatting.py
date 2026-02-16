#!/usr/bin/env python3
"""Demonstration script showing the difference in Telegram markdown formatting.

This script demonstrates how the new telegram formatting utilities properly
handle special characters that would previously cause display issues.
"""

from src.utils.telegram_format import markdown_to_telegram

# Test cases showing common scenarios that were problematic before
test_cases = [
    {
        "name": "Python function with underscores",
        "input": "Use the function calculate_sum with param_value",
        "issue": "Underscores were interpreted as italic formatting"
    },
    {
        "name": "File paths",
        "input": "Open file /path/to/my_file.txt and config_file.yaml",
        "issue": "File names with underscores broke formatting"
    },
    {
        "name": "API response",
        "input": 'Response: {"user_id": 123, "user_name": "test"}',
        "issue": "JSON keys with underscores caused issues"
    },
    {
        "name": "Code with markdown headers",
        "input": "## Example Code\n\nUse variable_name in your code",
        "issue": "Headers and variables both had formatting issues"
    },
    {
        "name": "Mixed formatting",
        "input": "**Important:** use my_function and _emphasize_ this",
        "issue": "Mix of bold, variables, and italics was confusing"
    },
    {
        "name": "Code block (protected)",
        "input": "Code:\n```python\ndef my_function():\n    pass\n```\nCall my_function()",
        "issue": "Code should not be escaped, but text outside should"
    }
]

def main():
    print("=" * 80)
    print("TELEGRAM MARKDOWN FORMATTING DEMONSTRATION")
    print("=" * 80)
    print()
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test['name']}")
        print(f"{'─' * 80}")
        print(f"Problem: {test['issue']}")
        print()
        print("INPUT (Standard Markdown):")
        print(f"  {repr(test['input'])}")
        print()
        print("OUTPUT (Telegram-compatible):")
        result = markdown_to_telegram(test['input'])
        print(f"  {repr(result)}")
        print()
        
        # Show the differences
        if test['input'] != result:
            print("✅ CHANGES APPLIED:")
            # Highlight key changes
            if '_' in test['input'] and '\\_' in result:
                print("  • Underscores escaped where needed")
            if '**' in test['input'] and '**' not in result:
                print("  • Double asterisks converted to single")
            if '##' in test['input']:
                print("  • Headers converted to bold")
            if '```' in test['input']:
                print("  • Code blocks protected from escaping")
        else:
            print("ℹ️  No changes needed")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("""
The new telegram formatting utilities ensure that:
✓ Special characters in regular text are properly escaped
✓ Intentional formatting (_italic_, *bold*) is preserved
✓ Code blocks and inline code are protected from escaping
✓ Markdown links remain intact
✓ Standard Markdown is converted to Telegram-compatible format

Official Telegram Documentation:
- Legacy Markdown: https://core.telegram.org/bots/api#markdown-style
- MarkdownV2: https://core.telegram.org/bots/api#markdownv2-style

For more details, see TELEGRAM_MARKDOWN_IMPLEMENTATION.md
""")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test script to verify message extraction logic for reply messages."""

from unittest.mock import Mock, MagicMock
from src.bot.handlers.message_handler import MessageHandler
from src.config.settings import AppSettings
from src.api.mistral_client import MistralClient
from src.bot.filters.access_filter import AccessFilter


def test_extract_text_from_reply():
    """Test extraction of text from a reply message."""
    
    # Create mock dependencies
    settings = Mock(spec=AppSettings)
    mistral = Mock(spec=MistralClient)
    access = Mock(spec=AccessFilter)
    
    # Create handler
    handler = MessageHandler(settings, mistral, access)
    
    # Create mock replied message
    replied_user = Mock()
    replied_user.first_name = "Alice"
    
    replied_message = Mock()
    replied_message.text = "This is the original message"
    replied_message.from_user = replied_user
    replied_message.reply_to_message = None
    replied_message.caption = None
    replied_message.photo = None
    replied_message.video = None
    replied_message.audio = None
    replied_message.voice = None
    replied_message.document = None
    replied_message.sticker = None
    replied_message.animation = None
    replied_message.location = None
    replied_message.contact = None
    replied_message.invoice = None
    # Important: disable forward_origin Mock behavior
    replied_message.forward_origin = None
    
    # Create mock current message (reply to the above)
    current_user = Mock()
    current_user.first_name = "Bob"
    
    current_message = Mock()
    current_message.text = "I agree with this"
    current_message.from_user = current_user
    current_message.reply_to_message = replied_message
    current_message.caption = None
    current_message.photo = None
    current_message.video = None
    current_message.audio = None
    current_message.voice = None
    current_message.document = None
    current_message.sticker = None
    current_message.animation = None
    current_message.location = None
    current_message.contact = None
    current_message.invoice = None
    # Important: disable forward_origin Mock behavior
    current_message.forward_origin = None
    
    # Test extraction
    extracted = handler._extract_text_from_message(current_message)
    
    print("=" * 60)
    print("TEST: Extract text from reply message")
    print("=" * 60)
    print(f"Replied message: '{replied_message.text}'")
    print(f"Current message: '{current_message.text}'")
    print(f"\nExtracted text:\n{extracted}")
    print("=" * 60)
    
    # Assertions
    assert extracted is not None, "Extracted text should not be None"
    assert "Сообщение от Alice" in extracted, "Should contain reference to Alice"
    assert "This is the original message" in extracted, "Should contain original message"
    assert "I agree with this" in extracted, "Should contain current message text"
    
    print("✓ All tests passed!")
    print("\nThe bot now correctly:")
    print("  1. Detects reply messages (reply_to_message)")
    print("  2. Extracts text from the original quoted message")
    print("  3. Preserves the user's response text")
    print("  4. Combines them together with quote formatting")


def test_extract_text_regular():
    """Test extraction of text from a regular message."""
    
    # Create mock dependencies
    settings = Mock(spec=AppSettings)
    mistral = Mock(spec=MistralClient)
    access = Mock(spec=AccessFilter)
    
    # Create handler
    handler = MessageHandler(settings, mistral, access)
    
    # Create mock regular message
    message = Mock()
    message.text = "Just a regular message"
    message.reply_to_message = None
    message.caption = None
    message.photo = None
    message.video = None
    message.audio = None
    message.voice = None
    message.document = None
    message.sticker = None
    message.animation = None
    message.location = None
    message.contact = None
    message.invoice = None
    message.forward_origin = None  # Disable Mock behavior
    
    # Test extraction
    extracted = handler._extract_text_from_message(message)
    
    print("\n" + "=" * 60)
    print("TEST: Extract text from regular message")
    print("=" * 60)
    print(f"Extracted text: '{extracted}'")
    assert extracted == "Just a regular message"
    print("✓ Test passed!")


if __name__ == "__main__":
    test_extract_text_from_reply()
    test_extract_text_regular()
    print("\n" + "=" * 60)
    print("SUCCESS: All tests passed!")
    print("=" * 60)

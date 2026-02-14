"""Test conversation memory functionality."""

from mistralai.models import AssistantMessage, UserMessage

from src.api.conversation_memory import ConversationMemory


def test_conversation_memory_basic():
    """Test basic memory storage and retrieval."""
    memory = ConversationMemory(max_history=5)

    # Add some messages
    memory.add_message(user_id=123, role="user", content="Hello")
    memory.add_message(user_id=123, role="assistant", content="Hi there!")
    memory.add_message(user_id=123, role="user", content="How are you?")
    memory.add_message(user_id=123, role="assistant", content="I'm good, thanks!")

    # Retrieve messages in API format
    messages = memory.get_messages_for_api(user_id=123)

    assert len(messages) == 4, f"Expected 4 messages, got {len(messages)}"
    assert isinstance(messages[0], UserMessage), "First message should be UserMessage"
    assert isinstance(messages[1], AssistantMessage), "Second message should be AssistantMessage"
    assert messages[0].content == "Hello", "First message content mismatch"
    assert messages[1].content == "Hi there!", "Second message content mismatch"

    print("✅ test_conversation_memory_basic passed")


def test_conversation_memory_max_history():
    """Test that memory auto-truncates to max_history."""
    memory = ConversationMemory(max_history=3)

    # Add 6 messages (3 pairs)
    for i in range(3):
        memory.add_message(user_id=456, role="user", content=f"User message {i}")
        memory.add_message(user_id=456, role="assistant", content=f"Bot response {i}")

    messages = memory.get_messages_for_api(user_id=456)

    # With max_history=3, we should keep max 6 messages (3 pairs)
    assert len(messages) == 6, f"Expected 6 messages total, got {len(messages)}"

    # Add more messages to trigger truncation
    memory.add_message(user_id=456, role="user", content="User message 3")
    memory.add_message(user_id=456, role="assistant", content="Bot response 3")

    messages = memory.get_messages_for_api(user_id=456)

    # Should still have max 6 messages (3 pairs), but oldest ones removed
    assert len(messages) == 6, f"Expected 6 messages after truncation, got {len(messages)}"

    # Verify the content (should have messages 1, 2, 3, not 0, 1, 2)
    assert "User message 1" in messages[0].content or "User message 2" in messages[0].content

    print("✅ test_conversation_memory_max_history passed")


def test_conversation_memory_per_user():
    """Test that different users have separate histories."""
    memory = ConversationMemory(max_history=5)

    # Add messages for user 1
    memory.add_message(user_id=111, role="user", content="User 1 message")
    memory.add_message(user_id=111, role="assistant", content="Response to user 1")

    # Add messages for user 2
    memory.add_message(user_id=222, role="user", content="User 2 message")
    memory.add_message(user_id=222, role="assistant", content="Response to user 2")

    # Get histories for each user
    messages_user1 = memory.get_messages_for_api(user_id=111)
    messages_user2 = memory.get_messages_for_api(user_id=222)

    assert len(messages_user1) == 2, f"User 1 should have 2 messages, got {len(messages_user1)}"
    assert len(messages_user2) == 2, f"User 2 should have 2 messages, got {len(messages_user2)}"

    # Verify content is different
    assert messages_user1[0].content == "User 1 message"
    assert messages_user2[0].content == "User 2 message"

    print("✅ test_conversation_memory_per_user passed")


def test_conversation_memory_clear():
    """Test clearing conversation history."""
    memory = ConversationMemory(max_history=5)

    # Add some messages
    memory.add_message(user_id=789, role="user", content="Message 1")
    memory.add_message(user_id=789, role="assistant", content="Response 1")

    # Verify they're there
    messages = memory.get_messages_for_api(user_id=789)
    assert len(messages) == 2, "Should have 2 messages before clear"

    # Clear history
    memory.clear_history(user_id=789)

    # Verify they're gone
    messages = memory.get_messages_for_api(user_id=789)
    assert len(messages) == 0, "Should have 0 messages after clear"

    print("✅ test_conversation_memory_clear passed")


def test_conversation_memory_empty_user():
    """Test getting messages for user with no history."""
    memory = ConversationMemory(max_history=5)

    # Get messages for a user that doesn't exist
    messages = memory.get_messages_for_api(user_id=999)

    assert len(messages) == 0, "Should return empty list for unknown user"
    assert messages == [], "Should return empty list, not None"

    print("✅ test_conversation_memory_empty_user passed")


if __name__ == "__main__":
    test_conversation_memory_basic()
    test_conversation_memory_max_history()
    test_conversation_memory_per_user()
    test_conversation_memory_clear()
    test_conversation_memory_empty_user()

    print("\n✅ All conversation memory tests passed!")

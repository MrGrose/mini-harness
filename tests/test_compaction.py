from mini_harness.context import compact_messages, context_size


def test_compact_messages_replaces_old_tool_output() -> None:
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
    ]
    for index in range(10):
        messages.append({"role": "assistant", "content": "x" * 1000})
        messages.append({"role": "tool", "content": "y" * 5000})
    before = context_size(messages)
    result = compact_messages(messages, max_chars=8000, keep_last=4)
    assert context_size(result) < before
    assert result[0]["content"] == "system"
    assert result[-1]["content"] == "y" * 5000
    assert any("[compacted:" in str(item["content"]) for item in result)

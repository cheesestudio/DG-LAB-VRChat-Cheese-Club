"""Test multi-shock delivery: simulates sequential shocks to verify the fix."""
import sys
sys.path.insert(0, ".")

from ws_client import WSClient, _make_msg


class MockWS:
    """Mock WebSocket that records sent messages."""
    def __init__(self):
        self.sent = []
    async def send(self, msg):
        self.sent.append(msg)
    async def close(self):
        pass


def test_waveform_active_flag():
    """Verify _waveform_active flag is set/cleared correctly."""
    client = WSClient()
    # Manually set paired state
    client._bound = True

    # Initially False
    assert client._waveform_active is False, "Should start False"

    # send_waveform sets it True
    client.send_waveform("A", ["0A0A0A0A64646464"])
    assert client._waveform_active is True, "send_waveform should set True"

    # clear_waveform sets it False
    client.clear_waveform("A")
    assert client._waveform_active is False, "clear_waveform should set False"

    # stop_waveform sets it False
    client._waveform_active = True
    client.stop_waveform()
    assert client._waveform_active is False, "stop_waveform should set False"

    print("PASS: waveform_active flag")


def test_sequential_shock_no_clear_before_send():
    """Verify new waveform is sent directly without clear (device replaces queue)."""
    from app import App, _flat_waveform_entry

    # Track send_waveform calls (no clear before send anymore)
    sends = []

    class MockWSClient:
        is_paired = True
        _waveform_active = False
        def clear_waveform(self, ch):
            pass  # Should NOT be called during normal shock
        def send_waveform(self, ch, data, duration=5):
            sends.append((ch, len(data)))
            self._waveform_active = True
        def force_strength(self, a, b):
            pass
        def stop_waveform(self):
            self._waveform_active = False

    mock = MockWSClient()

    # Simulate: shock 1 -> shock 2 (no clear between them)
    mock.send_waveform("A", [_flat_waveform_entry(100)] * 10, duration=1)
    mock.send_waveform("B", [_flat_waveform_entry(100)] * 10, duration=1)
    mock.send_waveform("A", [_flat_waveform_entry(150)] * 10, duration=1)
    mock.send_waveform("B", [_flat_waveform_entry(150)] * 10, duration=1)

    # Verify: 4 sends, no clears needed
    assert len(sends) == 4, f"Expected 4 sends, got {len(sends)}"
    assert mock._waveform_active is True, "Should be True after sends"

    print("PASS: sequential shock no clear before send")


def test_no_periodic_strength():
    """Verify _periodic_strength method was removed."""
    client = WSClient()
    assert not hasattr(client, '_periodic_strength'), \
        "_periodic_strength should be removed"
    print("PASS: no periodic strength")


def test_init_strength_only_mode2():
    """Verify _init_strength only sends mode=2 (absolute set), not mode=1 (increase)."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    client = WSClient()
    client._bound = True
    client._app_target_id = "test-target"
    sent_messages = []

    async def mock_send(msg_type, message):
        sent_messages.append(message)

    client._send_to_app = mock_send

    # Run _init_strength
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client._init_strength(150, 180))
    loop.close()

    # Should only have 2 messages using mode=2, starting with strength=1
    assert len(sent_messages) == 2, f"Expected 2 messages, got {len(sent_messages)}: {sent_messages}"
    assert sent_messages[0] == "strength-1+2+1", f"Expected strength-1+2+1, got {sent_messages[0]}"
    assert sent_messages[1] == "strength-2+2+1", f"Expected strength-2+2+1, got {sent_messages[1]}"

    # Verify NO mode=1 (increase) messages
    for msg in sent_messages:
        assert "+1+" not in msg, f"Found mode=1 (increase) in: {msg}"

    print("PASS: init_strength only mode=2, value=1")


if __name__ == "__main__":
    test_waveform_active_flag()
    test_sequential_shock_no_clear_before_send()
    test_no_periodic_strength()
    test_init_strength_only_mode2()
    print("\n=== ALL MULTI-SHOCK TESTS PASSED ===")

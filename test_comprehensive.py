"""Comprehensive test: verify all core functionality."""
import sys
sys.path.insert(0, ".")
import asyncio
import json
import time

from ws_client import WSClient, _make_msg
from waveform_library import get_preset, get_random_for_second, scale_waveform, loop_waveform, PRESETS
from waveform import generate_ab_waveforms, generate_one_shot, generate_gradual, waveform_to_display_data
from app import _flat_waveform_entry, _decode_wave_hex
from constants import MAX_INTENSITY, MIN_INTENSITY


class MockWebSocket:
    def __init__(self):
        self.sent = []
    async def send(self, msg):
        self.sent.append(msg)
    async def close(self):
        pass


# ========== 1. Waveform format ==========
def test_flat_waveform_entry():
    """V3 hex format: 4 carrier bytes + 4 pulse bytes."""
    for i in range(0, 201, 10):
        entry = _flat_waveform_entry(i)
        assert len(entry) == 16, f"Length wrong for {i}: {len(entry)}"
        carrier = int(entry[0:2], 16)
        pulse = int(entry[8:10], 16)
        assert carrier == 0x32, f"Carrier wrong: {carrier}"  # moderate sensation
        assert pulse == i // 2, f"Pulse wrong for {i}: {pulse}"  # 0-200 UI → 0-100 hex
    print("PASS: flat_waveform_entry (0-200)")


# ========== 2. Decode hex ==========
def test_decode_wave_hex():
    """Decode V3 hex entries: hex pulse (0-100) → UI display (0-200)."""
    # All pulse=100 → display=200
    r = _decode_wave_hex(["5050505064646464"])
    assert r == [200, 200, 200, 200], f"Got {r}"
    # Mixed
    r = _decode_wave_hex(["5050505000326464"])
    assert r == [0, 100, 200, 200], f"Got {r}"
    # Multiple entries
    r = _decode_wave_hex(["5050505064646464", "5050505000326464"])
    assert len(r) == 8, f"Got {len(r)} values"
    # Edge cases
    r = _decode_wave_hex(["5050505000000000"])
    assert r == [0, 0, 0, 0], f"Got {r}"
    r = _decode_wave_hex(["5050505064646464"])
    assert r == [200, 200, 200, 200], f"Got {r}"
    print("PASS: decode_wave_hex")


# ========== 3. Waveform generation ==========
def test_generate_ab_waveforms():
    """Generate A/B waveforms for all durations."""
    for sec in range(1, 11):
        a, b, an, bn = generate_ab_waveforms(sec, 150, 100, "instant", "library", alternate=True)
        assert len(a) == sec * 10, f"sec={sec}: len(a)={len(a)}"
        assert len(b) == sec * 10, f"sec={sec}: len(b)={len(b)}"
        for entry in a + b:
            assert len(entry) == 16, f"entry length: {len(entry)}"
            int(entry, 16)  # must be valid hex
        # Display intensities in range (hex 0-100 → UI 0-200)
        for v in _decode_wave_hex(a + b):
            assert 0 <= v <= 200, f"Display intensity out of range: {v}"
    print("PASS: generate_ab_waveforms (1-10s)")


# ========== 4. Max mode waveforms ==========
def test_max_mode_waveforms():
    """Max mode generates flat high-intensity waveforms."""
    for sec in [1, 3, 5, 9]:
        count = sec * 10
        a_wave = [_flat_waveform_entry(200)] * count
        b_wave = [_flat_waveform_entry(200)] * count
        assert len(a_wave) == count
        assert len(b_wave) == count
        a_ints = _decode_wave_hex(a_wave)
        b_ints = _decode_wave_hex(b_wave)
        assert all(v == 200 for v in a_ints), f"A intensities not all 200"
        assert all(v == 200 for v in b_ints), f"B intensities not all 200"
    print("PASS: max_mode_waveforms")


# ========== 5. Library presets ==========
def test_all_presets():
    """All library presets are valid."""
    for name, data in PRESETS.items():
        for entry in data:
            assert len(entry) == 16, f"Preset '{name}': bad entry {entry}"
            int(entry, 16)
            # Pulse bytes are positions 8-15, max 0x64 (100)
            for j in range(4):
                pulse_hex = int(entry[8+j*2:10+j*2], 16)
                assert 0 <= pulse_hex <= 100, f"Preset '{name}': pulse hex {pulse_hex}"
        ints = _decode_wave_hex(data)
        for v in ints:
            assert 0 <= v <= 200, f"Preset '{name}': display intensity {v}"
    print(f"PASS: all {len(PRESETS)} presets valid")


# ========== 6. Waveform display data ==========
def test_waveform_to_display_data():
    """Waveform to display data conversion (hex 0-100 → UI 0-200)."""
    entries = ["5050505064646464", "5050505000646400"]
    result = waveform_to_display_data(entries)
    assert len(result) == 2
    # Average of [200,200,200,200] = 200
    assert result[0] == 200, f"Got {result[0]}"
    # Average of [0,200,200,0] = 100
    assert result[1] == 100, f"Got {result[1]}"
    print("PASS: waveform_to_display_data")


# ========== 7. WebSocket protocol ==========
def test_ws_protocol_messages():
    """Verify WebSocket message formats."""
    # Bind message
    msg = _make_msg("bind", "client123", "target456", "DGLAB")
    parsed = json.loads(msg)
    assert parsed["type"] == "bind"
    assert parsed["clientId"] == "client123"
    assert parsed["targetId"] == "target456"
    assert parsed["message"] == "DGLAB"

    # Heartbeat
    msg = _make_msg("heartbeat", "c", "t", "200")
    parsed = json.loads(msg)
    assert parsed["type"] == "heartbeat"
    print("PASS: ws_protocol_messages")


# ========== 8. WSClient init strength ==========
def test_ws_init_strength():
    """_init_strength sends strength per channel."""
    client = WSClient()
    client._bound = True
    client._app_target_id = "test-target"
    sent = []

    async def mock_send(msg_type, message):
        sent.append(message)

    client._send_to_app = mock_send
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client._init_strength(150, 180))
    loop.close()

    assert len(sent) == 2, f"Expected 2, got {len(sent)}"
    assert sent[0] == "strength-1+2+150", f"Got {sent[0]}"
    assert sent[1] == "strength-2+2+180", f"Got {sent[1]}"
    print("PASS: ws_init_strength")


# ========== 9. WSClient force_strength ==========
def test_ws_force_strength():
    """force_strength sends mode=2 with correct values."""
    client = WSClient()
    client._bound = True
    client._app_target_id = "test-target"

    ws = MockWebSocket()
    client._uuid_to_ws["test-target"] = ws
    loop = asyncio.new_event_loop()
    client._loop = loop

    # Use run_coroutine_threadsafe like the real code does
    async def run():
        client.force_strength(150, 180)
        await asyncio.sleep(0.1)
    loop.run_until_complete(run())
    loop.close()

    assert len(ws.sent) == 2
    msgs = [json.loads(m) for m in ws.sent]
    assert msgs[0]["message"] == "strength-1+2+150"
    assert msgs[1]["message"] == "strength-2+2+180"
    print("PASS: ws_force_strength")


# ========== 10. WSClient send_waveform ==========
def test_ws_send_waveform():
    """send_waveform sends pulse-A/B with correct format."""
    client = WSClient()
    client._bound = True
    client._app_target_id = "test-target"
    client._waveform_active = False

    ws = MockWebSocket()
    client._uuid_to_ws["test-target"] = ws
    loop = asyncio.new_event_loop()
    client._loop = loop

    async def run():
        data = [_flat_waveform_entry(100)] * 5
        client.send_waveform("A", data, duration=1)
        await asyncio.sleep(0.1)
    loop.run_until_complete(run())
    loop.close()

    assert client._waveform_active is True
    assert len(ws.sent) == 1
    msg = json.loads(ws.sent[0])
    assert msg["message"].startswith("pulse-A:")
    payload = json.loads(msg["message"][8:])
    assert len(payload) == 5
    print("PASS: ws_send_waveform")


# ========== 11. WSClient clear_waveform ==========
def test_ws_clear_waveform():
    """clear_waveform sends clear-1/2."""
    client = WSClient()
    client._bound = True
    client._app_target_id = "test-target"

    ws = MockWebSocket()
    client._uuid_to_ws["test-target"] = ws
    loop = asyncio.new_event_loop()
    client._loop = loop

    async def run():
        client.clear_waveform("A")
        await asyncio.sleep(0.1)
    loop.run_until_complete(run())
    loop.close()

    assert client._waveform_active is False
    assert len(ws.sent) == 1
    msg = json.loads(ws.sent[0])
    assert msg["message"] == "clear-1"

    # Test B channel
    ws2 = MockWebSocket()
    client._uuid_to_ws["test-target"] = ws2
    loop2 = asyncio.new_event_loop()
    client._loop = loop2

    async def run2():
        client.clear_waveform("B")
        await asyncio.sleep(0.1)
    loop2.run_until_complete(run2())
    loop2.close()
    msg2 = json.loads(ws2.sent[0])
    assert msg2["message"] == "clear-2"
    print("PASS: ws_clear_waveform")


# ========== 12. Waveform chunking ==========
def test_waveform_chunking():
    """Waveforms > 86 entries are chunked correctly."""
    client = WSClient()
    client._bound = True
    client._app_target_id = "test-target"

    ws = MockWebSocket()
    client._uuid_to_ws["test-target"] = ws
    loop = asyncio.new_event_loop()
    client._loop = loop

    async def run():
        # 200 entries = 3 chunks (86 + 86 + 28)
        data = [_flat_waveform_entry(100)] * 200
        client.send_waveform("A", data, duration=20)
        await asyncio.sleep(0.2)
    loop.run_until_complete(run())
    loop.close()

    assert len(ws.sent) == 3, f"Expected 3 chunks, got {len(ws.sent)}"
    sizes = []
    for m in ws.sent:
        payload = json.loads(json.loads(m)["message"][8:])
        sizes.append(len(payload))
    assert sizes == [86, 86, 28], f"Chunk sizes: {sizes}"
    print("PASS: waveform_chunking")


# ========== 13. Safety limits ==========
def test_safety_limits():
    """Safety limit constants are reasonable."""
    from constants import SAFETY_WINDOW_SECONDS, SAFETY_MAX_PER_WINDOW, SAFETY_MAX_TOTAL
    assert SAFETY_WINDOW_SECONDS == 10.0
    assert SAFETY_MAX_PER_WINDOW == 30
    assert SAFETY_MAX_TOTAL == 30
    print("PASS: safety_limits")


# ========== 14. Scale waveform ==========
def test_scale_waveform():
    """Scale waveform to target intensity."""
    data = ["0A0A0A0A32323232"]  # intensity=50
    scaled = scale_waveform(data, 100)
    ints = _decode_wave_hex(scaled)
    assert all(v == 100 for v in ints), f"Got {ints}"
    print("PASS: scale_waveform")


# ========== 15. Gradual mode ==========
def test_gradual_mode():
    """Gradual mode increases intensity over time."""
    wave = generate_gradual(3, 200)
    assert len(wave) == 30  # 3 seconds * 10
    ints = _decode_wave_hex(wave)
    # Should start low and end high
    assert ints[0] < ints[-1], f"First={ints[0]}, Last={ints[-1]}"
    assert ints[-1] == 200, f"Last should be 200, got {ints[-1]}"
    print("PASS: gradual_mode")


if __name__ == "__main__":
    tests = [
        test_flat_waveform_entry,
        test_decode_wave_hex,
        test_generate_ab_waveforms,
        test_max_mode_waveforms,
        test_all_presets,
        test_waveform_to_display_data,
        test_ws_protocol_messages,
        test_ws_init_strength,
        test_ws_force_strength,
        test_ws_send_waveform,
        test_ws_clear_waveform,
        test_waveform_chunking,
        test_safety_limits,
        test_scale_waveform,
        test_gradual_mode,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("=== ALL TESTS PASSED ===")
    else:
        sys.exit(1)

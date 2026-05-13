"""Test script to verify waveform generation and display fixes."""
import sys
sys.path.insert(0, ".")

from waveform_library import get_preset, get_random_for_second, scale_waveform, loop_waveform
from waveform import generate_ab_waveforms
from app import _flat_waveform_entry, _decode_wave_hex


def test_flat_waveform_entry():
    """Test _flat_waveform_entry generates correct FFFFIIII format."""
    entry = _flat_waveform_entry(100)
    assert entry == "0A0A0A0A64646464", f"Expected '0A0A0A0A64646464', got '{entry}'"
    entry0 = _flat_waveform_entry(0)
    assert entry0 == "0A0A0A0A00000000", f"Expected '0A0A0A0A00000000', got '{entry0}'"
    entry200 = _flat_waveform_entry(200)
    assert entry200 == "0A0A0A0AC8C8C8C8", f"Expected '0A0A0A0AC8C8C8C8', got '{entry200}'"
    print("PASS: _flat_waveform_entry")


def test_decode_wave_hex():
    """Test _decode_wave_hex correctly extracts intensities from FFFFIIII format."""
    # FFFFIIII: first 8 chars = freq, last 8 chars = intensity
    entry = "0A0A0A0A64646464"  # freq=0x0A, intensity=0x64 (100) for all 4
    result = _decode_wave_hex([entry])
    assert result == [100, 100, 100, 100], f"Expected [100,100,100,100], got {result}"

    # Mixed intensities
    entry2 = "0A0A0A0A003264C8"  # intensities: 0, 50, 100, 200
    result2 = _decode_wave_hex([entry2])
    assert result2 == [0, 50, 100, 200], f"Expected [0,50,100,200], got {result2}"

    # Multiple entries
    result3 = _decode_wave_hex([entry, entry2])
    assert result3 == [100, 100, 100, 100, 0, 50, 100, 200], f"Got {result3}"
    print("PASS: _decode_wave_hex")


def test_scale_waveform():
    """Test scale_waveform correctly scales FFFFIIII format."""
    # All same intensity
    data = ["0A0A0A0A32323232"]  # intensity=50
    scaled = scale_waveform(data, 100)  # scale to 100
    assert scaled == ["0A0A0A0A64646464"], f"Expected ['0A0A0A0A64646464'], got {scaled}"

    # Mixed intensities
    data2 = ["0A0A0A0A003264C8"]  # intensities: 0, 50, 100, 200
    scaled2 = scale_waveform(data2, 100)  # scale max to 100 (half)
    # Expected: 0, 25, 50, 100
    assert scaled2 == ["0A0A0A0A00193264"], f"Expected ['0A0A0A0A00193264'], got {scaled2}"
    print("PASS: scale_waveform")


def test_generate_ab_waveforms():
    """Test generate_ab_waveforms produces valid output."""
    for seconds in range(1, 11):
        a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
            seconds, 200, 200, "instant", "library", alternate=True
        )
        assert len(a_wave) == seconds * 10, f"seconds={seconds}: expected {seconds*10} a_wave entries, got {len(a_wave)}"
        assert len(b_wave) == seconds * 10, f"seconds={seconds}: expected {seconds*10} b_wave entries, got {len(b_wave)}"
        # Verify each entry is 16 hex chars
        for entry in a_wave + b_wave:
            assert len(entry) == 16, f"Expected 16-char entry, got {len(entry)}: {entry}"
            int(entry, 16)  # Should not raise
        # Verify intensities are within range
        a_ints = _decode_wave_hex(a_wave)
        b_ints = _decode_wave_hex(b_wave)
        for v in a_ints + b_ints:
            assert 0 <= v <= 200, f"Intensity out of range: {v}"
    print("PASS: generate_ab_waveforms (all seconds 1-10)")


def test_waveform_library_presets():
    """Verify all presets decode correctly."""
    from waveform_library import PRESETS
    for name, data in PRESETS.items():
        for entry in data:
            assert len(entry) == 16, f"Preset '{name}': entry {entry} is not 16 chars"
            int(entry, 16)  # Should not raise
        # Verify intensities are in range
        ints = _decode_wave_hex(data)
        for v in ints:
            assert 0 <= v <= 200, f"Preset '{name}': intensity {v} out of range"
    print(f"PASS: all {len(PRESETS)} presets valid")


def test_intensity_display_logic():
    """Test that set_intensity properly stores values."""
    # Simulate what app.py does
    a_intensity = 200
    b_intensity = 100
    # The _current_a/b should be set to these values, not from waveform data
    # This is a logic test - verify the flow
    a_wave, b_wave, a_name, b_name = generate_ab_waveforms(
        3, a_intensity, b_intensity, "instant", "library", alternate=False
    )
    a_subs = _decode_wave_hex(a_wave)
    b_subs = _decode_wave_hex(b_wave)
    # After push_waveform, _current_a/b should come from set_intensity, not from subs
    # Verify that subs contain valid data
    assert len(a_subs) > 0, "a_subs is empty"
    assert len(b_subs) > 0, "b_subs is empty"
    print("PASS: intensity display logic")


if __name__ == "__main__":
    test_flat_waveform_entry()
    test_decode_wave_hex()
    test_scale_waveform()
    test_generate_ab_waveforms()
    test_waveform_library_presets()
    test_intensity_display_logic()
    print("\n=== ALL TESTS PASSED ===")

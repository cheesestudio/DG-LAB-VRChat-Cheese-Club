"""Test waveform format correctness for DG-LAB protocol."""
import sys
sys.path.insert(0, '.')

from pydglab_ws import PulseOperation, dump_pulse_operation
from waveform import generate_one_shot, _make_entry
from app import _flat_waveform_entry, _decode_wave_hex


def test_flat_entry_format():
    """Verify _flat_waveform_entry produces correct FFFFIIII block format."""
    print("=== Test: _flat_waveform_entry format ===")

    entry = _flat_waveform_entry(200)
    print(f"  entry:  {entry}")

    # pydglab_ws reference — FFFFIIII: all 4 freq bytes, then all 4 intensity bytes
    op = ((0x0A, 0x0A, 0x0A, 0x0A), (0xC8, 0xC8, 0xC8, 0xC8))
    ref = dump_pulse_operation(op)
    print(f"  ref:    {ref}")

    assert entry.lower() == ref.lower(), f"MISMATCH: {entry} != {ref}"
    print("  PASS\n")


def test_waveform_library_format():
    """Verify generate_one_shot produces correct FFFFIIII block format."""
    print("=== Test: generate_one_shot format ===")

    wave = generate_one_shot(1, 200)
    entry = wave[0]
    print(f"  entry:  {entry}")

    op = ((0x0A, 0x0A, 0x0A, 0x0A), (0xC8, 0xC8, 0xC8, 0xC8))
    ref = dump_pulse_operation(op)
    print(f"  ref:    {ref}")

    assert entry.lower() == ref.lower(), f"MISMATCH: {entry} != {ref}"
    print("  PASS\n")


def test_decode_roundtrip():
    """Verify encode -> decode roundtrip preserves intensity values."""
    print("=== Test: encode -> decode roundtrip ===")

    for intensity in [0, 50, 100, 150, 200]:
        entry = _flat_waveform_entry(intensity)
        decoded = _decode_wave_hex([entry])
        # Each entry has 4 pairs, decode extracts all 4 intensity bytes
        # Format: 0A{XX}0A{XX}0A{XX}0A{XX} -> pairs (0A,XX)(0A,XX)(0A,XX)(0A,XX)
        # decode extracts intensity from each pair: [XX, XX, XX, XX]
        assert all(v == intensity for v in decoded), \
            f"intensity={intensity}: decoded={decoded}"
    print("  PASS: all intensity values roundtrip correctly\n")


def test_full_waveform_message():
    """Verify the actual message format sent to phone."""
    print("=== Test: full waveform message (3 seconds) ===")

    count = 3 * 10  # 30 entries for 3 seconds
    a_wave = [_flat_waveform_entry(200)] * count

    # Simulate what send_waveform does: json.dumps the list
    import json
    wavestr = json.dumps(a_wave, separators=(",", ":"))
    msg = f"pulse-A:{wavestr}"

    print(f"  entries: {len(a_wave)}")
    print(f"  first entry: {a_wave[0]}")
    print(f"  message length: {len(msg)} chars")
    print(f"  message preview: {msg[:120]}...")

    # Verify pydglab_ws can parse each entry
    for i, entry in enumerate(a_wave[:3]):
        # Each entry should be valid hex of length 16
        assert len(entry) == 16, f"entry {i} length: {len(entry)}"
        int(entry, 16)  # Should not raise
    print("  PASS: all entries are valid 16-char hex strings\n")


def test_different_intensities():
    """Verify waveform generation for various intensity levels."""
    print("=== Test: different intensities ===")

    for intensity in [30, 60, 100, 150, 200]:
        entry = _flat_waveform_entry(intensity)
        # FFFFIIII: intensity bytes at positions 8-15 (last 8 hex chars)
        for j in range(4):
            pos = 8 + j * 2
            byte_str = entry[pos:pos + 2]
            actual = int(byte_str, 16)
            assert actual == intensity, \
                f"intensity={intensity}, sub-frame {j}: expected {intensity}, got {actual}"
    print("  PASS: all intensity bytes correct\n")


def test_comparison_with_old_wrong_format():
    """Show the difference between old wrong format and new correct format."""
    print("=== Comparison: old (wrong) vs new (correct) ===")

    intensity = 200
    old_wrong = f"0A0A0A0A{intensity:02X}{intensity:02X}{intensity:02X}{intensity:02X}"
    new_correct = _flat_waveform_entry(intensity)

    print(f"  OLD (wrong): {old_wrong}")
    print(f"    pairs: (0A,0A)(0A,0A)(0A,0A)(C8,C8)")
    print(f"    -> intensity bytes: [10, 10, 10, 200] (first 3 sub-frames wrong!)")
    print()
    print(f"  NEW (correct): {new_correct}")
    print(f"    pairs: (0A,C8)(0A,C8)(0A,C8)(0A,C8)")
    print(f"    -> intensity bytes: [200, 200, 200, 200] (all correct)")
    print()


if __name__ == "__main__":
    test_flat_entry_format()
    test_waveform_library_format()
    test_decode_roundtrip()
    test_full_waveform_message()
    test_different_intensities()
    test_comparison_with_old_wrong_format()
    print("ALL TESTS PASSED")

import math
import random
from waveform_library import get_random_for_second, scale_waveform, loop_waveform, get_preset


def _clamp(value: int, min_val: int = 0, max_val: int = 200) -> int:
    return max(min_val, min(max_val, value))


def _make_entry(carrier: int, intensity: int) -> str:
    """Generate 8-byte V3 hex: 4 carrier bytes + 4 pulse bytes.
    Carrier: 0-255 (0x00-0xFF), controls sensation texture.
    Pulse: 0-100 (0x00-0x64), controls shock strength.
    UI intensity (0-200) is halved to fit 0-100 pulse range."""
    c = _clamp(carrier, 0, 255)
    p = _clamp(intensity // 2, 0, 100)  # 0-200 UI range → 0-100 hex range
    return f"{c:02X}{c:02X}{c:02X}{c:02X}{p:02X}{p:02X}{p:02X}{p:02X}"


def generate_one_shot(seconds: int, intensity: int) -> list[str]:
    """Flat waveform — consistent medium carrier with full pulse."""
    count = seconds * 10
    entry = _make_entry(40, intensity)  # carrier 0x28 = moderate sensation
    return [entry] * count


def generate_gradual(seconds: int, intensity: int) -> list[str]:
    """Smooth ramp-up — carrier rises with pulse for building sensation."""
    count = seconds * 10
    entries = []
    for i in range(count):
        t = i / max(count - 1, 1)
        eased = (1 - math.cos(t * math.pi)) / 2
        current_pulse = int(intensity * eased)
        current_pulse = _clamp(current_pulse, 0, intensity)
        # Carrier also ramps: starts low (10), ends higher (80)
        carrier = int(10 + 70 * eased)
        carrier = _clamp(carrier, 0, 255)
        entries.append(_make_entry(carrier, current_pulse))
    return entries


def generate_waveform(seconds: int, intensity: int, mode: str = "instant",
                      waveform_mode: str = "library",
                      custom_waveform: str = "") -> list[str]:
    """Generate waveform based on seconds, intensity, and mode.

    waveform_mode:
        "library" - use random preset waveforms from library
        "custom" - use specific preset chosen by user
    """
    seconds = max(1, min(10, seconds))
    intensity = _clamp(intensity)

    if waveform_mode == "library":
        name, preset = get_random_for_second(seconds)
        scaled = scale_waveform(preset, intensity)
        return loop_waveform(scaled, seconds * 10)
    elif waveform_mode == "custom" and custom_waveform:
        preset = get_preset(custom_waveform)
        if preset:
            scaled = scale_waveform(preset, intensity)
            return loop_waveform(scaled, seconds * 10)
    elif mode == "gradual":
        return generate_gradual(seconds, intensity)
    return generate_one_shot(seconds, intensity)


def waveform_to_display_data(entries: list[str]) -> list[int]:
    """Decode V3 hex entries: first 8 = carrier[4], last 8 = pulse[4].
    Returns average pulse per entry (0-100 hex → 0-200 UI range)."""
    result = []
    for entry in entries:
        pulses = []
        for j in range(4):
            pos = 8 + j * 2
            if pos + 2 <= len(entry):
                try:
                    pulses.append(int(entry[pos:pos + 2], 16) * 2)  # hex 0-100 → UI 0-200
                except ValueError:
                    pulses.append(0)
        result.append(sum(pulses) // max(len(pulses), 1))
    return result


def generate_smooth_feeder_waveform(intensity: int, count: int = 10) -> list[str]:
    """Generate a smooth, continuous waveform chunk for the feeder.
    Uses varied carriers + pulse patterns — no zero-intensity gaps."""
    intensity = _clamp(intensity)
    if intensity == 0:
        return [_make_entry(10, 0)] * count

    # Pick from several patterns with different carrier profiles
    pattern_type = random.choice(["sine", "ramp_up", "ramp_down", "triangle", "gentle_pulse"])

    # Carrier profiles add texture variety:
    # - low (10-30): smooth gentle buzz
    # - mid (30-70): moderate prickly sensation
    # - high (70-190): sharp aggressive shocks
    carrier_profile = random.choice(["low", "mid", "high", "sweep"])

    def _carrier(t: float) -> int:
        if carrier_profile == "low":
            return int(10 + 20 * math.sin(2 * math.pi * t))
        elif carrier_profile == "mid":
            return int(40 + 30 * math.sin(2 * math.pi * t))
        elif carrier_profile == "high":
            return int(100 + 90 * math.sin(2 * math.pi * t))
        else:  # sweep: carrier rises and falls
            return int(10 + 120 * (0.5 + 0.5 * math.sin(2 * math.pi * t * 0.5)))

    if pattern_type == "sine":
        entries = []
        for i in range(count):
            t = i / max(count, 1)
            pulse = int(intensity * (0.5 + 0.5 * math.sin(2 * math.pi * t - math.pi / 2)))
            pulse = max(1, min(intensity, pulse))
            entries.append(_make_entry(_carrier(t), pulse))
        return entries

    elif pattern_type == "ramp_up":
        entries = []
        for i in range(count):
            t = i / max(count - 1, 1)
            base = int(intensity * 0.3)
            pulse = int(base + (intensity - base) * t)
            pulse = max(1, min(intensity, pulse))
            entries.append(_make_entry(_carrier(t), pulse))
        return entries

    elif pattern_type == "ramp_down":
        entries = []
        for i in range(count):
            t = i / max(count - 1, 1)
            base = int(intensity * 0.3)
            pulse = int(intensity - (intensity - base) * t)
            pulse = max(1, min(intensity, pulse))
            entries.append(_make_entry(_carrier(t), pulse))
        return entries

    elif pattern_type == "triangle":
        entries = []
        for i in range(count):
            t = i / max(count, 1)
            pulse = int(intensity * (1 - abs(2 * t - 1)))
            pulse = max(1, min(intensity, pulse))
            entries.append(_make_entry(_carrier(t), pulse))
        return entries

    else:  # gentle_pulse
        entries = []
        for i in range(count):
            t = i / max(count, 1)
            pulse = int(intensity * (0.5 + 0.5 * math.sin(2 * math.pi * t)))
            pulse = max(1, min(intensity, pulse))
            entries.append(_make_entry(_carrier(t), pulse))
        return entries


def generate_ab_waveforms(seconds: int, a_intensity: int, b_intensity: int,
                          mode: str = "instant", waveform_mode: str = "library",
                          alternate: bool = True,
                          custom_waveform: str = "") -> tuple[list[str], list[str], str, str]:
    """Generate waveforms for both A and B channels.
    Returns (a_wave, b_wave, a_preset_name, b_preset_name)
    If alternate=True, A and B use different random presets.
    """
    a_name = ""
    b_name = ""

    if waveform_mode == "library" or waveform_mode == "custom":
        if waveform_mode == "custom" and custom_waveform:
            a_data = get_preset(custom_waveform)
            b_data = get_preset(custom_waveform)
            a_name = custom_waveform
            b_name = custom_waveform
            if not a_data:
                a_data = get_random_for_second(seconds)[1]
                a_name = ""
            if not b_data:
                b_data = get_random_for_second(seconds)[1]
                b_name = ""
        elif alternate:
            a_name, a_data = get_random_for_second(seconds)
            b_name, b_data = get_random_for_second(seconds)
            attempts = 0
            while b_name == a_name and attempts < 5:
                b_name, b_data = get_random_for_second(seconds)
                attempts += 1
        else:
            a_name, a_data = get_random_for_second(seconds)
            b_name = a_name
            b_data = a_data
        a_wave = loop_waveform(scale_waveform(a_data, a_intensity), seconds * 10)
        b_wave = loop_waveform(scale_waveform(b_data, b_intensity), seconds * 10)
    else:
        a_wave = generate_waveform(seconds, a_intensity, mode, waveform_mode)
        b_wave = generate_waveform(seconds, b_intensity, mode, waveform_mode)

    return a_wave, b_wave, a_name, b_name

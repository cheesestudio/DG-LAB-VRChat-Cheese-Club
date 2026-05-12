"""VRChat Avatar OSC Parameter Handler - compatible with Shocking-VRChat modes."""
import asyncio
import collections
import json
import math
import threading
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# === Waveform generation (compatible with Shocking-VRChat) ===

def generate_wave_100ms(freq: int, from_: float, to_: float) -> str:
    """Generate a 100ms waveform hex string.
    Compatible with Shocking-VRChat's generate_wave_100ms.
    Each entry: 4 freq bytes + 4 interpolated intensity bytes = 8 bytes = 8 hex chars.
    Output format: ["0A0A0A0A64646464"] — array with single 8-char hex string.
    """
    from_ = int(100 * from_)
    to_ = int(100 * to_)
    ret = [f"{freq:02X}"] * 4
    delta = (to_ - from_) // 4
    ret += [f"{min(max(from_ + delta * i, 0), 100):02X}" for i in range(1, 5)]
    wave_hex = "".join(ret)
    return json.dumps([wave_hex], separators=(",", ":"))


# === Mode Handlers ===

class DistanceMode:
    """Distance mode: continuous strength proportional to OSC value."""

    def __init__(self, config: dict):
        self.freq = config.get("freq_ms", 10)
        self.trigger_bottom = config.get("trigger_range", {}).get("bottom", 0.0)
        self.trigger_top = config.get("trigger_range", {}).get("top", 1.0)
        self.current_strength = 0.0
        self.last_strength = 0.0

    def normalize(self, value: float) -> float:
        if value > self.trigger_bottom:
            out = (value - self.trigger_bottom) / (self.trigger_top - self.trigger_bottom)
            return min(out, 1.0)
        return 0.0

    def on_value(self, value: float):
        self.current_strength = self.normalize(value)

    def get_wave(self) -> Optional[str]:
        if self.current_strength == self.last_strength == 0:
            return None
        wave = generate_wave_100ms(self.freq, self.last_strength, self.current_strength)
        self.last_strength = self.current_strength
        return wave

    @property
    def clear_timeout(self) -> float:
        return 0.5


class ShockMode:
    """Shock mode: trigger burst waveform when value exceeds threshold."""

    def __init__(self, config: dict):
        self.duration = config.get("shock", {}).get("duration", 2)
        self.wave_data = config.get("shock", {}).get(
            "wave", '["0A0A0A0A64646464"]'
        )
        self.trigger_bottom = config.get("trigger_range", {}).get("bottom", 0.0)
        self.trigger_top = config.get("trigger_range", {}).get("top", 1.0)
        self._last_trigger_time = 0.0
        self._last_value = 0.0

    def on_value(self, value: float) -> None:
        self._last_value = value

    def check_and_trigger(self) -> Optional[float]:
        """Check if threshold crossed and return duration, or None."""
        now = time.time()
        if self._last_value > self.trigger_bottom and now > self._last_trigger_time:
            self._last_trigger_time = now + self.duration
            return self.duration
        return None

    @property
    def clear_timeout(self) -> float:
        return self.duration


class TouchMode:
    """Touch mode: velocity/acceleration-based waveform."""

    def __init__(self, config: dict):
        self.freq = config.get("freq_ms", 10)
        self.n_derivative = config.get("n_derivative", 1)
        self.derivative_params = config.get("derivative_params", [
            {"top": 1, "bottom": 0},
            {"top": 5, "bottom": 0},
            {"top": 50, "bottom": 0},
            {"top": 500, "bottom": 0},
        ])
        self.trigger_bottom = config.get("trigger_range", {}).get("bottom", 0.0)
        self.trigger_top = config.get("trigger_range", {}).get("top", 1.0)
        self.dist_arr = collections.deque(maxlen=20)
        self.current_strength = 0.0
        self.last_strength = 0.0

    def normalize(self, value: float) -> float:
        if value > self.trigger_bottom:
            out = (value - self.trigger_bottom) / (self.trigger_top - self.trigger_bottom)
            return min(out, 1.0)
        return 0.0

    def on_value(self, value: float):
        norm = self.normalize(value)
        if norm == 0:
            return
        self.dist_arr.append([time.time(), norm])

    def _compute_derivative(self):
        if len(self.dist_arr) < 4:
            return 0, 0, 0, 0
        data = list(self.dist_arr)
        times = [p[0] for p in data]
        distances = [p[1] for p in data]

        # Moving average (3-point)
        n = 3
        smoothed = []
        for i in range(len(distances) - n + 1):
            smoothed.append(sum(distances[i:i + n]) / n)
        times = times[:len(smoothed)]

        if len(smoothed) < 2:
            return 0, 0, 0, 0

        # Gradient: simple central difference
        def gradient(values, xs):
            result = []
            for i in range(1, len(values) - 1):
                dx = xs[i + 1] - xs[i - 1]
                if abs(dx) > 1e-9:
                    result.append((values[i + 1] - values[i - 1]) / dx)
                else:
                    result.append(0.0)
            return result

        velocity = gradient(smoothed, times)
        acceleration = gradient(velocity, times[:len(velocity)])
        jerk = gradient(acceleration, times[:len(velocity) - 1])

        last_idx = len(smoothed) - 1
        v_last = velocity[-1] if len(velocity) > 1 else 0.0
        a_last = acceleration[-1] if len(acceleration) > 1 else 0.0
        j_last = jerk[-1] if jerk else 0.0
        return float(smoothed[last_idx]), float(v_last), float(a_last), float(j_last)

    def get_wave(self) -> Optional[str]:
        deriv = self._compute_derivative()
        n = min(self.n_derivative, len(deriv) - 1)
        raw = abs(deriv[n])
        params = self.derivative_params[n]
        top = params.get("top", 1)
        bottom = params.get("bottom", 0)
        if top > bottom:
            strength = max(min(raw, top), bottom) / (top - bottom)
        else:
            strength = 0.0
        self.current_strength = strength
        if self.current_strength == self.last_strength == 0:
            return None
        wave = generate_wave_100ms(self.freq, self.last_strength, self.current_strength)
        self.last_strength = self.current_strength
        return wave

    @property
    def clear_timeout(self) -> float:
        return 0.5


# === Avatar Channel Handler ===

class AvatarChannelHandler:
    """Handles OSC messages for one channel (A or B) with one of three modes."""

    def __init__(self, channel: str, mode: str, config: dict):
        self.channel = channel.upper()
        self.mode = mode
        self._cleared = True
        self._clear_time = 0.0
        self._pending_shock_duration: Optional[float] = None

        if mode == "distance":
            self._handler_impl = DistanceMode(config)
        elif mode == "shock":
            self._handler_impl = ShockMode(config)
        elif mode == "touch":
            self._handler_impl = TouchMode(config)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

    @staticmethod
    def sanitize_value(args) -> float:
        val = args[0] if args else 0
        if isinstance(val, float):
            return min(max(val, 0.0), 1.0)
        elif isinstance(val, int):
            return min(max(val, 0), 1)
        elif isinstance(val, bool):
            return 1.0 if val else 0.0
        return 0.0

    def on_osc(self, address: str, *args):
        """Called when an OSC message arrives."""
        val = self.sanitize_value(args)
        logger.info(f"[Avatar] CH{self.channel} mode={self.mode}: {address} = {val}")
        self._cleared = False
        self._clear_time = time.time() + self._handler_impl.clear_timeout
        self._handler_impl.on_value(val)
        if self.mode == "distance":
            logger.info(f"[Avatar] CH{self.channel} strength now: {self._handler_impl.current_strength}")

    def check_clear(self) -> bool:
        """Returns True if channel should be cleared."""
        if not self._cleared and time.time() > self._clear_time:
            self._cleared = True
            self._clear_time = 0.0
            return True
        return False

    def get_wave(self) -> Optional[str]:
        """Get next waveform to send (for distance/touch modes)."""
        if self.mode in ("distance", "touch"):
            return self._handler_impl.get_wave()
        return None

    def pop_shock_duration(self) -> Optional[float]:
        """For shock mode: pop and return pending shock duration if triggered, else None."""
        if self.mode != "shock":
            return None
        duration = self._handler_impl.check_and_trigger()
        if duration is not None:
            logger.info(f"[Avatar] CH{self.channel} shock triggered for {duration}s")
        return duration

    @property
    def is_shock(self) -> bool:
        return self.mode == "shock"


# === OSC Listener & Avatar Manager ===

class AvatarManager:
    """Manages OSC listening and avatar parameter handling for both channels."""

    def __init__(self, on_wave: Callable, on_clear: Callable, on_log: Callable = None):
        self._on_wave = on_wave  # callback(channel, wave_hex_str)
        self._on_clear = on_clear  # callback(channel)
        self._on_log = on_log or (lambda msg, tag: None)

        self._channels = {}  # 'A' or 'B' -> AvatarChannelHandler
        self._osc_server = None
        self._osc_thread = None
        self._running = False
        self._bg_loop = None
        self._bg_tasks = []
        self._bg_thread = None

    def configure(self, channel_a_params: list, channel_a_mode: str, channel_a_config: dict,
                  channel_b_params: list, channel_b_mode: str, channel_b_config: dict):
        """Configure both channels with their OSC paths, modes, and configs."""
        self._channels["A"] = AvatarChannelHandler("A", channel_a_mode, channel_a_config)
        self._channels["B"] = AvatarChannelHandler("B", channel_b_mode, channel_b_config)
        self._channel_a_params = channel_a_params
        self._channel_b_params = channel_b_params

    def start(self, osc_host: str = "127.0.0.1", osc_port: int = 9001):
        """Start background tasks. OSC server is managed by app.py."""
        if self._running:
            return
        self._running = True
        self._on_log(f"Avatar OSC 模式已启动 (A:{self._channels['A'].mode} B:{self._channels['B'].mode})", "info")
        self._start_bg_tasks()

    def _start_bg_tasks(self):
        """Start background asyncio tasks for wave generation."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            for ch in ["A", "B"]:
                handler = self._channels.get(ch)
                if handler and handler.mode in ("distance", "touch"):
                    self._bg_tasks.append(asyncio.ensure_future(self._wave_feeder(ch)))
            self._bg_tasks.append(asyncio.ensure_future(self._clear_checker()))
            self._bg_tasks.append(asyncio.ensure_future(self._shock_checker()))
        else:
            # Run in a separate thread with its own event loop
            def _run():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                self._bg_loop = new_loop
                try:
                    for ch in ["A", "B"]:
                        handler = self._channels.get(ch)
                        if handler and handler.mode in ("distance", "touch"):
                            self._bg_tasks.append(new_loop.create_task(self._wave_feeder(ch)))
                    self._bg_tasks.append(new_loop.create_task(self._clear_checker()))
                    self._bg_tasks.append(new_loop.create_task(self._shock_checker()))
                    new_loop.run_forever()
                finally:
                    pending = [task for task in self._bg_tasks if not task.done()]
                    for task in pending:
                        task.cancel()
                    if pending:
                        new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    new_loop.run_until_complete(new_loop.shutdown_asyncgens())
                    new_loop.close()

            self._bg_thread = threading.Thread(target=_run, daemon=True)
            self._bg_thread.start()

    async def _wave_feeder(self, channel: str):
        """Background task that continuously feeds waveforms for distance/touch modes."""
        interval = 0.05  # 50ms tick
        logger.info(f"[Avatar] wave_feeder started for CH{channel}")
        while self._running:
            await asyncio.sleep(interval)
            handler = self._channels.get(channel)
            if not handler or handler.is_shock:
                continue
            wave = handler.get_wave()
            if wave:
                logger.info(f"[Avatar] CH{channel} sending wave: {wave[:60]}")
                self._on_wave(channel, wave)

    async def _clear_checker(self):
        """Background task that checks for channel clears."""
        while self._running:
            await asyncio.sleep(0.05)
            for ch in ["A", "B"]:
                handler = self._channels.get(ch)
                if handler and handler.check_clear():
                    self._on_clear(ch)
                    logger.info(f"Channel {ch} cleared after timeout")

    async def _shock_checker(self):
        """Background task that checks for shock mode triggers."""
        while self._running:
            await asyncio.sleep(0.05)
            for ch in ["A", "B"]:
                handler = self._channels.get(ch)
                if handler and handler.is_shock:
                    duration = handler.pop_shock_duration()
                    if duration is not None:
                        wave = handler._handler_impl.wave_data
                        logger.info(f"[Avatar] CH{ch} sending shock wave, duration={duration}s")
                        self._on_wave(ch, wave, duration)

    def stop(self):
        """Stop OSC listening and background tasks."""
        self._running = False
        loop = self._bg_loop
        if loop:
            try:
                for task in list(self._bg_tasks):
                    loop.call_soon_threadsafe(task.cancel)
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass
        if self._bg_thread:
            self._bg_thread.join(timeout=2)
            self._bg_thread = None
        self._bg_loop = None
        self._bg_tasks = []
        if self._osc_server:
            try:
                self._osc_server.shutdown()
            except Exception:
                pass
            self._osc_server = None
            self._on_log("Avatar OSC 已停止", "info")


    def send_shock(self, channel: str, duration: float = 2.0, wave_data: str = None):
        """Manually trigger a shock on a channel."""
        if wave_data is None:
            wave_data = '["0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464","0A0A0A0A64646464"]'
        self._on_wave(channel, wave_data)

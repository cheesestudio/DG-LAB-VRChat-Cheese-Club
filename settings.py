import json
import os
import tempfile

DEFAULT_SETTINGS = {
    "port": 9999,
    "a_limit": 200,
    "b_limit": 200,
    "mode": "instant",
    "channel": "A",
    "waveform_mode": "library",
    "poll_interval": 0.3,
    "idle_check_interval": 10,
    "log_dir_override": "",
    "auto_connect": False,
    "osc_port": 9000,
    "theme": "dark",
    "chatbox_send_interval": 3,
    "chatbox_enabled": True,
    "custom_chatbox": "",
    "custom_waveform": "",
    "chatbox_toggles": {"line1": True, "line2": True, "line3": True, "line4": True, "line5": True},
    "http_port": 8800,
    # Avatar OSC settings (compatible with Shocking-VRChat)
    "avatar_osc_port": 9001,
    "avatar_osc_host": "127.0.0.1",
    "avatar_channel_a_mode": "distance",
    "avatar_channel_b_mode": "distance",
    "avatar_channel_a_params": [
        "/avatar/parameters/pcs/contact/enterPass",
        "/avatar/parameters/Shock/TouchAreaA",
        "/avatar/parameters/Shock/TouchAreaC",
        "/avatar/parameters/Shock/wildcard/*",
    ],
    "avatar_channel_b_params": [
        "/avatar/parameters/pcs/contact/enterPass",
        "/avatar/parameters/lms-penis-proximityA*",
        "/avatar/parameters/Shock/TouchAreaB",
        "/avatar/parameters/Shock/TouchAreaC",
    ],
    "avatar_channel_a_config": {
        "trigger_range": {"bottom": 0.0, "top": 1.0},
        "distance": {"freq_ms": 10},
        "shock": {"duration": 2, "wave": '["0A0A0A0A64646464"]'},
        "touch": {
            "freq_ms": 10, "n_derivative": 1,
            "derivative_params": [
                {"top": 1, "bottom": 0}, {"top": 5, "bottom": 0},
                {"top": 50, "bottom": 0}, {"top": 500, "bottom": 0},
            ],
        },
    },
    "avatar_channel_b_config": {
        "trigger_range": {"bottom": 0.0, "top": 1.0},
        "distance": {"freq_ms": 10},
        "shock": {"duration": 2, "wave": '["0A0A0A0A64646464"]'},
        "touch": {
            "freq_ms": 10, "n_derivative": 1,
            "derivative_params": [
                {"top": 1, "bottom": 0}, {"top": 5, "bottom": 0},
                {"top": 50, "bottom": 0}, {"top": 500, "bottom": 0},
            ],
        },
    },
    # 自定义参数联动规则
    # 每条规则: {"path": str, "channel": "A"|"B"|"AB", "type": "bool"|"int"|"float",
    #            "value": any, "enabled": bool, "duration": int}
    "custom_osc_rules": [],
}


class Settings:
    def __init__(self, path: str = None):
        if path is None:

            import sys
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base_dir, "settings.json")
        self._path = path
        self._data: dict = {}
        self.load()

    def load(self) -> dict:
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        for key, value in DEFAULT_SETTINGS.items():
            if key not in self._data:
                self._data[key] = value
            elif isinstance(value, dict) and isinstance(self._data[key], dict):
                self._data[key] = self._deep_merge(value, self._data[key])
        return self._data

    @staticmethod
    def _deep_merge(default: dict, saved: dict) -> dict:
        result = dict(saved)
        for key, value in default.items():
            if key not in result:
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                result[key] = Settings._deep_merge(value, result[key])
        return result

    def save(self):
        dir_name = os.path.dirname(self._path)
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._path)
        except OSError:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        # Input validation for known numeric keys
        if key in ("port", "osc_port", "avatar_osc_port", "http_port", "poll_interval", "idle_check_interval"):
            value = self._clamp_int(value, 1, 65535)
        elif key in ("a_limit", "b_limit"):
            value = self._clamp_int(value, 0, 200)
        elif key == "chatbox_send_interval":
            value = self._clamp_int(value, 1, 60)
        self._data[key] = value

    @staticmethod
    def _clamp_int(value, min_val: int, max_val: int) -> int:
        try:
            return max(min_val, min(max_val, int(value)))
        except (ValueError, TypeError):
            return min_val

    @property
    def data(self) -> dict:
        return self._data

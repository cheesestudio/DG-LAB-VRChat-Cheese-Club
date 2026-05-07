import json
import os
import tempfile

DEFAULT_SETTINGS = {
    "port": 9999,
    "a_limit": 200,
    "b_limit": 200,
    "mode": "instant",
    "channel": "A",
    "seconds_mapping": {
        "1": 30, "2": 50, "3": 200, "4": 80,
        "5": 100, "6": 120, "7": 150, "8": 170, "9": 185, "10": 200,
    },
    "waveform_mode": "library",
    "poll_interval": 0.5,
    "idle_check_interval": 5,
    "log_dir_override": "",
    "auto_connect": False,
    "osc_port": 9000,
    "theme": "dark",
    "chatbox_send_interval": 3,
    "chatbox_enabled": True,
    "custom_chatbox": "我是Saob",
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
}


class Settings:
    def __init__(self, path: str = None):
        if path is None:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
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
        # Ensure seconds_mapping has all keys 1-10
        sm = self._data.get("seconds_mapping", {})
        for k in range(1, 11):
            if str(k) not in sm:
                sm[str(k)] = DEFAULT_SETTINGS["seconds_mapping"][str(k)]
        self._data["seconds_mapping"] = sm
        return self._data

    def save(self):
        dir_name = os.path.dirname(self._path)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value

    @property
    def data(self) -> dict:
        return self._data

import os
import re
import time
import threading
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


SHOCK_PATTERN = re.compile(
    r"\[DGLABCheeseShocking\]LocalShocking调用[:：]\s*mode=(\w+),\s*seconds=(\d+),\s*hand=(\w+)"
)


class LogMonitor:
    def __init__(
        self,
        on_shock_event: Callable[[dict], None],
        on_log_line: Callable[[str], None],
        log_dir: str = "",
        poll_interval: float = 0.5,
        idle_check_interval: float = 10.0,
    ):
        self._on_shock = on_shock_event
        self._on_log_line = on_log_line
        self._poll_interval = poll_interval
        self._idle_check_interval = idle_check_interval

        if log_dir:
            self._log_dir = Path(log_dir)
        else:
            self._log_dir = Path.home() / "AppData" / "LocalLow" / "VRChat" / "VRChat"

        self._current_file: Optional[Path] = None
        self._file_position: int = 0
        self._last_activity_time: float = time.time()
        self._pending_line: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _find_latest_log(self) -> Optional[Path]:
        if not self._log_dir.exists():
            return None
        candidates = []
        for f in self._log_dir.glob("output_log_*.txt"):
            try:
                candidates.append((f.stat().st_mtime, f.name, f))
            except OSError:
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]

    def _check_for_newer_file(self) -> Optional[Path]:
        # If current file doesn't exist, find a new one immediately
        if self._current_file and not self._current_file.exists():
            latest = self._find_latest_log()
            if latest:
                return latest
            return None
        latest = self._find_latest_log()
        if latest and self._current_file and latest != self._current_file:
            return latest
        return None

    def _read_new_lines(self) -> list[str]:
        if not self._current_file or not self._current_file.exists():
            return []
        lines = []
        try:
            with open(self._current_file, "rb") as f:
                f.seek(0, 2)
                file_size = f.tell()
                if self._file_position >= file_size:
                    return []
                f.seek(self._file_position)
                # Read up to 256KB to handle burst log writes without dropping data
                read_size = min(file_size - self._file_position, 262144)
                data = f.read(read_size)
                self._file_position = f.tell()
                if data:
                    text = data.decode("utf-8", errors="replace")
                    new_lines = text.splitlines()
                    # Stitch incomplete line from previous read
                    if self._pending_line:
                        new_lines[0] = self._pending_line + new_lines[0]
                        self._pending_line = None
                    # If data doesn't end with a line break, the last split
                    # element may be incomplete — save it for next read
                    if data and not data.endswith(b'\n') and not data.endswith(b'\r'):
                        if new_lines:
                            self._pending_line = new_lines.pop()
                    lines = new_lines
        except OSError:
            pass
        return lines

    def _process_line(self, line: str):
        # Quick check: only process lines that might be relevant
        if "[DGLABCheeseShocking]" not in line and "[ShockingManager]" not in line and "ShockingPlayer" not in line:
            return
        logger.debug(f"Relevant line: {line[:80]}")
        self._on_log_line(line)
        match = SHOCK_PATTERN.search(line)
        if match:
            event = {
                "mode": match.group(1),
                "seconds": int(match.group(2)),
                "hand": match.group(3),
            }
            self._on_shock(event)

    def _monitor_loop(self):
        _last_file_check = time.time()
        while not self._stop_event.is_set():
            # Find initial file if not set
            if self._current_file is None or not self._current_file.exists():
                self._current_file = self._find_latest_log()
                if self._current_file:
                    # Start from end of file - ignore old content
                    try:
                        self._file_position = self._current_file.stat().st_size
                    except OSError:
                        self._file_position = 0
                    self._on_log_line(f"[日志] 开始监控: {self._current_file.name}")

            # Read new lines
            new_lines = self._read_new_lines()
            if new_lines:
                self._last_activity_time = time.time()
                for line in new_lines:
                    try:
                        self._process_line(line)
                    except Exception:
                        pass  # Never let a single bad line kill the monitor thread

            # Check for newer log file — run periodically, not just when idle
            now = time.time()
            if now - _last_file_check >= self._idle_check_interval:
                _last_file_check = now
                newer = self._check_for_newer_file()
                if newer:
                    self._on_log_line(f"[日志] 检测到新日志文件: {newer.name}")
                    self._current_file = newer
                    try:
                        self._file_position = newer.stat().st_size
                    except OSError:
                        self._file_position = 0
                    self._last_activity_time = time.time()

            self._stop_event.wait(self._poll_interval)

    def start(self):
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def current_file(self) -> Optional[Path]:
        return self._current_file

    @property
    def log_dir(self) -> Path:
        return self._log_dir

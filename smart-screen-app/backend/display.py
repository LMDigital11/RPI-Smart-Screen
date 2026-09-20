import glob
import os

from config import config


def _backlight_paths():
    for pattern in (
        "/sys/class/backlight/*/brightness",
        "/sys/devices/platform/rpi-backlight/backlight/*/brightness",
    ):
        for path in glob.glob(pattern):
            yield path


def _write(path, value):
    try:
        with open(path, "w") as f:
            f.write(str(value))
    except OSError:
        pass


def get_max_brightness():
    for brightness in _backlight_paths():
        max_path = brightness.replace("/brightness", "/max_brightness")
        try:
            with open(max_path) as f:
                return int(f.read().strip())
        except OSError:
            pass
    return 255


def set_power(powered):
    for brightness in _backlight_paths():
        _write(brightness, get_max_brightness() if powered else 0)
    import sys

    if sys.platform != "win32":
        _write_vcgencmd("display_power", "1" if powered else "0")


def _write_vcgencmd(command, value):
    try:
        import subprocess

        subprocess.run(
            ["vcgencmd", command, value], capture_output=True, text=True, timeout=5
        )
    except Exception:
        pass


def status():
    return {
        "supported": len(list(_backlight_paths())) > 0,
        "brightness_max": get_max_brightness(),
        "sleep": config.get()["sleep"],
    }
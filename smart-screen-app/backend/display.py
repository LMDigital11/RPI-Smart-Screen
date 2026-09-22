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


def get_brightness():
    path = next(_backlight_paths(), None)
    if not path:
        return None
    max_b = get_max_brightness()
    if max_b <= 0:
        return None
    try:
        with open(path) as f:
            value = int(f.read().strip())
    except (OSError, ValueError):
        return None
    return round(100 * value / max_b)


def set_brightness(percent):
    percent = max(0, min(100, int(percent)))
    max_b = get_max_brightness()
    for path in _backlight_paths():
        _write(path, round(max_b * percent / 100))
    return percent


def set_power(powered):
    if powered:
        set_brightness(config.get()["display"].get("brightness", 100))
    else:
        for brightness in _backlight_paths():
            _write(brightness, 0)
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
        "brightness": get_brightness(),
        "display": config.get()["display"],
        "sleep": config.get()["sleep"],
    }
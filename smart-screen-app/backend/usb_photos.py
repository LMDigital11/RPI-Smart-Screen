import os
import subprocess
import time

from config import config

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"}

USB_MOUNT_POINTS = ["/media", "/media/pi", "/mnt", "/run/media"]


def list_drives():
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,LABEL,SIZE,MOUNTPOINT,TYPE"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = __import__("json").loads(result.stdout)
        blocks = data.get("blockdevices", [])
    except Exception:
        blocks = []

    drives = []
    for block in blocks:
        for part in block.get("children", []):
            if part.get("type") == "part":
                name, label = part.get("name"), part.get("label") or "USB"
                drives.append(
                    {
                        "name": name,
                        "label": label,
                        "size": part.get("size", ""),
                        "mounted": part.get("mountpoint") is not None,
                        "mountpoint": part.get("mountpoint") or "",
                        "device": "/dev/" + name,
                    }
                )
    return drives


def mount(device_or_name):
    name = device_or_name[len("/dev/"):] if device_or_name.startswith("/dev/") else device_or_name
    try:
        result = subprocess.run(
            ["udisksctl", "mount", "-b", "/dev/" + name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        import re as _re

        match = _re.search(r"at\s+(.+?)[\r\n]", result.stdout)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    time.sleep(1)
    return current_mountpoint(name)


def current_mountpoint(drive_name):
    for drive in list_drives():
        if drive["name"] == drive_name and drive["mountpoint"]:
            return drive["mountpoint"]
    return None


def list_photos(drive_name=None):
    mountpoint = None
    if drive_name:
        mountpoint = mount(drive_name)
    if not mountpoint:
        preferred = config.get()["slideshow"].get("usb_drive", "")
        for base in USB_MOUNT_POINTS:
            if not os.path.isdir(base):
                continue
            candidates = [base]
            if preferred:
                candidates = [
                    os.path.join(base, d)
                    for d in os.listdir(base)
                    if preferred.lower() in d.lower()
                ] or [base]
            for root in candidates:
                for entry in os.scandir(root):
                    if entry.is_dir():
                        image_dir = entry.path if _has_images(entry.path) else None
                        if image_dir:
                            mountpoint = image_dir
                            break
                if mountpoint:
                    break
            if mountpoint:
                break

    if not mountpoint:
        return []

    photos = []
    for root, _, files in os.walk(mountpoint):
        for name in sorted(files):
            if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                photos.append(os.path.join(root, name).replace(os.sep, "/"))
    return photos


def _has_images(path):
    try:
        for name in os.listdir(path)[:200]:
            if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                return True
    except OSError:
        pass
    return False
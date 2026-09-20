import subprocess

from config import config


def _nmcli(args):
    try:
        result = subprocess.run(
            ["nmcli"] + args,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout, result.returncode == 0
    except FileNotFoundError:
        return "", False


def _parse_scan(output):
    networks = []
    for line in output.splitlines():
        fields = line.split(":")
        if len(fields) < 2:
            continue
        ssid = fields[0] or "(hidden)"
        signal = fields[1] if fields[1] else "0"
        networks.append({"ssid": ssid, "signal": int(signal)})
    networks.sort(key=lambda n: n["signal"], reverse=True)
    seen, unique = set(), []
    for net in networks:
        if net["ssid"] not in seen:
            seen.add(net["ssid"])
            unique.append(net)
    return unique


def scan():
    stdout, _ = _nmcli(
        ["-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list", "--rescan", "yes"]
    )
    return _parse_scan(stdout) if stdout else []


def status():
    ssid = ""
    signal = None
    stdout, _ = _nmcli(
        ["-t", "-f", "ACTIVE,SSID,SIGNAL", "-g", "active,ssid,signal", "dev", "wifi"]
    )
    for line in stdout.splitlines():
        parts = line.split(":")
        if parts and parts[0] == "yes" and len(parts) >= 2:
            ssid = parts[1]
            try:
                signal = int(parts[2])
            except ValueError:
                pass
    saved = config.get()["wifi"].get("ssid", "")
    return {"ssid": ssid or "", "connected": bool(ssid), "stored_ssid": saved, "signal": signal}


def connect(ssid, password):
    args = ["dev", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    stdout, ok = _nmcli(args)
    if not ok and "password" in stdout.lower() and not password:
        args = ["dev", "wifi", "connect", ssid, "password", stdin_password()]
        stdout, ok = _nmcli(args)
    if ok:
        cfg = config.get()
        cfg["wifi"]["ssid"] = ssid
        cfg["wifi"]["connected"] = True
        config.save()
    return ok


def stdin_password():
    return ""
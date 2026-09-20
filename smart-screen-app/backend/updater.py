import os
import re
import shutil
import subprocess

from config import config

REPO_DIR = "/opt/smart-screen-src"
APP_DIR = "/opt/smart-screen"
VERSION_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")
)
SCRIPT = "/usr/local/sbin/smart-screen-update"


def current_version():
    try:
        with open(VERSION_PATH, encoding="utf-8") as f:
            return f.read().strip() or "1.0.0"
    except OSError:
        return "1.0.0"


def local_short_commit():
    match = re.search(r"[0-9a-fA-F]{8,}", current_version())
    return match.group(0)[:8] if match else None


def _run(cmd, timeout=120):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except OSError as exc:
        return False, "", str(exc)
    except subprocess.TimeoutExpired:
        return False, "", "command timed out"


def remote_commit(repo_url, branch):
    ok, out, _ = _run(
        ["git", "ls-remote", repo_url, "refs/heads/" + branch], timeout=60
    )
    if not ok or not out:
        return None
    return out.split("\t")[0].strip()


_last_check = {}


def status():
    cfg = config.get().get("update") or {}
    base = {
        "repo_configured": bool((cfg.get("repo_url") or "").strip()),
        "repo_url": (cfg.get("repo_url") or "").strip(),
        "branch": (cfg.get("branch") or "main").strip(),
        "current_version": current_version(),
        "git_available": shutil.which("git") is not None,
        "script_present": os.path.isfile(SCRIPT),
        "last_error": "",
        "last_check_at": None,
    }
    if _last_check:
        base.update(_last_check)
    return base


def check():
    cfg = config.get().get("update") or {}
    repo_url = (cfg.get("repo_url") or "").strip()
    branch = (cfg.get("branch") or "main").strip()
    git_available = shutil.which("git") is not None
    script_present = os.path.isfile(SCRIPT)
    status = {
        "repo_configured": bool(repo_url),
        "repo_url": repo_url,
        "branch": branch,
        "current_version": current_version(),
        "remote_commit": None,
        "update_available": False,
        "git_available": git_available,
        "script_present": script_present,
        "last_error": "",
    }
    if not repo_url:
        status["last_error"] = "No update repo configured. Add it in this section."
        return status
    if not git_available:
        status["last_error"] = "git is not installed on this device."
        return status
    commit = remote_commit(repo_url, branch)
    status["remote_commit"] = commit
    if commit:
        local = local_short_commit()
        status["update_available"] = not local or not commit.startswith(local)
    else:
        status["last_error"] = (
            "Could not reach the repo — check URL, branch, network, or that "
            "credentials are embedded for a private repo."
        )
    _last_check["update_available"] = status["update_available"] if commit else False
    _last_check["remote_commit"] = commit
    _last_check["last_check_at"] = (
        __import__("datetime").datetime.now().strftime("%H:%M:%S")
    )
    return status


def apply():
    cfg = config.get().get("update") or {}
    repo_url = (cfg.get("repo_url") or "").strip()
    branch = (cfg.get("branch") or "main").strip()
    if not repo_url:
        return {"ok": False, "error": "No update repo configured."}
    if not os.path.isfile(SCRIPT):
        return {
            "ok": False,
            "error": "Updater script missing on this device. Reinstall the app once "
            "(deploy/install.sh) or rebuild the .img.",
        }
    ok, out, err = _run(["sudo", SCRIPT, repo_url, branch], timeout=600)
    return {"ok": ok, "output": (out or err)[:2000]}
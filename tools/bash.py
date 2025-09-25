import shlex, subprocess, os
WORKDIR = os.getcwd()
DISALLOWED = ("git","ssh","sudo")
def call(command, timeout=120000, description=""):
    if not isinstance(command, str) or not command.strip():
        return {"success": False, "output": "Missing command", "meta": {}}
    parts = shlex.split(command)
    if any(p in DISALLOWED for p in parts):
        return {"success": False, "output": f"Command contains disallowed token: {DISALLOWED}", "meta": {}}
    try:
        proc = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, timeout=timeout/1000)
        out = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "Command timed out", "meta": {}}
    except Exception as e:
        return {"success": False, "output": f"Execution error: {e}", "meta": {}}
    return {"success": True, "output": out.strip(), "meta": {"returncode": proc.returncode}}

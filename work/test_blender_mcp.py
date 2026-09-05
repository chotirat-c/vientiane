import json
import os
import queue
import subprocess
import sys
import threading
import time


UVX = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work\uv-python\bin\uvx.exe"
WORK = r"C:\Users\mikasaloli\Documents\Codex\2026-09-05\ho\work"


def reader(stream, output_queue):
    for line in iter(stream.readline, ""):
        output_queue.put(line.rstrip("\r\n"))


env = os.environ.copy()
env.update(
    {
        "UV_CACHE_DIR": os.path.join(WORK, "uv-cache"),
        "UV_TOOL_DIR": os.path.join(WORK, "uv-tools"),
        "UV_PYTHON_INSTALL_DIR": os.path.join(WORK, "uv-python-installs"),
        "BLENDER_HOST": "localhost",
        "BLENDER_PORT": "9876",
    }
)

proc = subprocess.Popen(
    [UVX, "blender-mcp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    env=env,
    bufsize=1,
)

stdout_queue = queue.Queue()
stderr_queue = queue.Queue()
threading.Thread(target=reader, args=(proc.stdout, stdout_queue), daemon=True).start()
threading.Thread(target=reader, args=(proc.stderr, stderr_queue), daemon=True).start()


def send(message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def response_for(request_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = stdout_queue.get(timeout=0.25)
        except queue.Empty:
            if proc.poll() is not None:
                raise RuntimeError(f"MCP server exited with code {proc.returncode}")
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") == request_id:
            return message
    errors = []
    while not stderr_queue.empty():
        errors.append(stderr_queue.get_nowait())
    raise TimeoutError("Timed out waiting for MCP response.\n" + "\n".join(errors[-20:]))


try:
    send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "codex-blender-test", "version": "1.0"},
            },
        }
    )
    initialized = response_for(1)
    if "error" in initialized:
        raise RuntimeError(initialized["error"])
    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_response = response_for(2)
    tools = tools_response.get("result", {}).get("tools", [])
    names = [tool.get("name", "") for tool in tools]
    scene_tool = next(
        (
            name
            for name in names
            if name in {"get_scene_info", "blender_scene_get_info", "scene_get_info"}
        ),
        None,
    )
    if scene_tool is None:
        scene_tool = next((name for name in names if "scene" in name and "info" in name), None)
    result = None
    if scene_tool:
        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": scene_tool, "arguments": {}},
            }
        )
        result = response_for(3)
    print(
        json.dumps(
            {
                "connected": True,
                "server": initialized.get("result", {}).get("serverInfo"),
                "tool_count": len(names),
                "scene_tool": scene_tool,
                "scene_result": result,
            },
            indent=2,
        )
    )
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)

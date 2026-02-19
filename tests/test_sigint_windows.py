import os
import sys
import time
import signal
import subprocess

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test (uses CTRL_C_EVENT)")
def test_cli_handles_ctrl_c_windows():
    """Start the CLI and send CTRL_C_EVENT, expect graceful shutdown (exit code 0)."""
    python = sys.executable
    cmd = [python, "-u", "-m", "src.main"]

    # Start subprocess in new process group so CTRL_C_EVENT can be sent
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=CREATE_NEW_PROCESS_GROUP,
    )

    # Wait for the CLI banner to appear (with timeout)
    start = time.time()
    banner_seen = False
    try:
        while time.time() - start < 15:
            line = p.stdout.readline()
            if not line:
                break
            if "teleChatBot - CLI Mode" in line:
                banner_seen = True
                break
        assert banner_seen, "CLI banner not printed before timeout"

        # Give it a moment to finish initialization
        time.sleep(1)

        # Send CTRL_C_EVENT to the process group
        p.send_signal(signal.CTRL_C_EVENT)

        # Wait for process to exit
        rc = p.wait(timeout=10)

        # Expect clean exit (0)
        assert rc == 0, f"Process exited with code {rc}"

    finally:
        if p.poll() is None:
            p.kill()
            p.wait()

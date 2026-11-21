import subprocess
import threading
import uuid


def run_pytest_in_docker(
    project_path,
    docker_binary="docker",
    image="combinator-ai-test-runner:py312",
    timeout_seconds=120,
    output_limit_bytes=16 * 1024,
):
    unavailable = _check_runner(docker_binary, image)
    if unavailable is not None:
        return unavailable

    container_name = "combinator-test-" + uuid.uuid4().hex[:16]
    command = [
        docker_binary,
        "run",
        "--rm",
        "--name",
        container_name,
        "--pull=never",
        "--network=none",
        "--read-only",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=64",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65534:65534",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "--mount",
        "type=bind,source={},target=/workspace,readonly".format(project_path),
        "--workdir=/workspace",
        "--env=HOME=/tmp",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        "--env=PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
        image,
        "timeout",
        "--signal=KILL",
        "--kill-after=5s",
        str(timeout_seconds),
        "python",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
    ]

    output = bytearray()
    output_lock = threading.Lock()
    truncated = [False]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
        )
    except FileNotFoundError:
        return _unavailable("Docker could not be started.")
    except OSError:
        return {
            "status": "error",
            "return_code": None,
            "output": "The Docker test runner could not be started.",
            "truncated": False,
        }

    def collect_output():
        if process.stdout is None:
            return
        while True:
            chunk = process.stdout.read(4096)
            if not chunk:
                return
            with output_lock:
                remaining = output_limit_bytes - len(output)
                if remaining > 0:
                    output.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated[0] = True

    reader = threading.Thread(target=collect_output, daemon=True)
    reader.start()
    try:
        return_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        cleanup_error = _stop_container(docker_binary, container_name)
        try:
            process.kill()
        except OSError:
            pass
        process.wait(timeout=10)
        reader.join(timeout=2)
        if process.stdout is not None:
            process.stdout.close()
        if cleanup_error:
            return {
                "status": "cleanup_failed",
                "return_code": None,
                "output": _decode_output(output),
                "truncated": truncated[0],
                "message": cleanup_error,
            }
        return {
            "status": "timed_out",
            "return_code": None,
            "output": _decode_output(output),
            "truncated": truncated[0],
            "timeout_seconds": timeout_seconds,
        }
    reader.join(timeout=2)
    if process.stdout is not None:
        process.stdout.close()

    if return_code in (125, 126, 127):
        return {
            "status": "error",
            "return_code": return_code,
            "output": _decode_output(output),
            "truncated": truncated[0],
            "message": "Docker could not start the isolated test container.",
        }
    if return_code == 137:
        status = "resource_limit"
    else:
        status = "passed" if return_code == 0 else "failed"
    return {
        "status": status,
        "return_code": return_code,
        "output": _decode_output(output),
        "truncated": truncated[0],
        "runner": "Docker isolated pytest runner",
    }


def _check_runner(docker_binary, image):
    try:
        result = subprocess.run(
            [docker_binary, "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except FileNotFoundError:
        return _unavailable("Docker is not installed or is not on PATH.")
    except subprocess.TimeoutExpired:
        return _unavailable("Docker did not respond; verify that its service is running.")
    except OSError:
        return _unavailable("Docker could not be reached.")

    if result.returncode != 0:
        return _unavailable(
            "Docker or the local pytest runner image is unavailable. Follow the README setup steps."
        )
    return None


def _stop_container(docker_binary, container_name):
    try:
        result = subprocess.run(
            [docker_binary, "rm", "--force", container_name],
            capture_output=True,
            timeout=8,
            check=False,
            shell=False,
        )
        if result.returncode != 0:
            return "Docker did not confirm that the timed-out container was removed."
    except FileNotFoundError:
        return "Docker disappeared while cleaning up the timed-out test container."
    except subprocess.TimeoutExpired:
        return "Docker timed out while cleaning up the test container."
    except OSError:
        return "Docker failed to clean up the timed-out test container."
    return None


def _unavailable(message):
    return {
        "status": "unavailable",
        "return_code": None,
        "output": "",
        "truncated": False,
        "message": message,
    }


def _decode_output(output):
    return bytes(output).decode("utf-8", errors="replace")

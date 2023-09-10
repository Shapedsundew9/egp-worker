"""Test cases for the worker process script."""
from subprocess import run, PIPE, CompletedProcess
from os.path import dirname, join


WORKER_SCRIPT: str = join(dirname(__file__), "..", "egp_worker", "egp_worker.py")

def test_init_parameterless() -> None:
    """Test that the worker process can be initialized."""
    result: CompletedProcess[bytes] = run(["python", WORKER_SCRIPT], stdout=PIPE, stderr=PIPE, check=False, shell=True)
    print(result.stdout.decode("utf-8"))
    assert result.returncode == 0, result.stderr.decode("utf-8")

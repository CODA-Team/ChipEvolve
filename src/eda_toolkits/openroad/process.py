"""Stream native logs to both durable tool files and the public execution log."""
import subprocess

from ..activity import native_activity


def run_logged(command, workspace, *, environment=None, append=False):
    with native_activity(environment) as active_environment:
        return _run_logged(command, workspace, active_environment, append)


def _run_logged(command, workspace, environment, append):
    with (workspace / 'extractor.log').open('a' if append else 'w') as output:
        with subprocess.Popen(command, cwd=workspace, env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1) as process:
            assert process.stdout is not None
            for line in process.stdout:
                output.write(line)
                output.flush()
                print('[tool] ' + line.rstrip('\n'), flush=True)
            return process.wait()

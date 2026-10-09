"""Reusable read-only native sessions for the strong direct baseline.

No product parsers or execution packages. Sessions preserve one fixed snapshot,
are suspended between queries and resume only under the shared EDA host lease.
The outer episode supervisor owns their PID/start identity and cleanup.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from direct_native import start_ticks, measure, group_alive


SERVER = r'''
set ready [open /work/ready w]; puts $ready ready; close $ready
while {1} {
  foreach request [lsort [glob -nocomplain /work/requests/*.tcl]] {
    set stem [file rootname $request]
    if {[file exists ${stem}.done]} {continue}
    sta::redirect_file_begin ${stem}.out
    set code [catch {uplevel #0 [list source $request]} message options]
    if {$code != 0} {puts "QUERY_ERROR $message"}
    sta::redirect_file_end
    set mark [open ${stem}.done w]; puts $mark $code; close $mark
  }
  after 25
}
'''


def stop_group(pid):
    os.killpg(pid, signal.SIGSTOP)
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        try:
            text = Path(f'/proc/{pid}/stat').read_text()
            if text[text.rfind(')')+2:].split()[0] == 'T':
                return
        except OSError:
            return
        time.sleep(.01)
    raise RuntimeError('native session did not suspend')


def run_session(folder, *, command, lines, script, env, seconds):
    """Caller holds the EDA lease through load/query and suspension."""
    started = time.monotonic()
    registry = folder / 'process.json'
    reused = registry.is_file()
    if reused:
        identity = json.loads(registry.read_text())
        if identity['terminal'] or start_ticks(identity['pid']) != identity['start_ticks']:
            raise RuntimeError('prior native session exited; original failure retained')
        pid = identity['pid']
        before = measure(pid)['cpu_seconds']
        os.killpg(pid, signal.SIGCONT)
    else:
        (folder / 'requests').mkdir()
        (folder / 'session.tcl').write_text('\n'.join(lines) + '\n' + SERVER)
        with (folder / 'startup.log').open('w') as log:
            process = subprocess.Popen(command, cwd=folder, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        pid = process.pid
        identity = {'pid': pid, 'start_ticks': start_ticks(pid), 'terminal': False,
                    'session': True, 'suspended': False}
        registry.write_text(json.dumps(identity)+'\n')
        before = 0
    peak = {'cpu_seconds': 0, 'rss_bytes': 0, 'processes': 0}
    exceeded = None
    timed_out = False
    output = None
    exit_code = None
    try:
        while not (folder / 'ready').is_file():
            if not group_alive(pid):
                raise RuntimeError('native session input load failed; see startup.log')
            if time.monotonic()-started >= seconds:
                timed_out = True
                break
            time.sleep(.025)
        if not timed_out:
            token = str(time.time_ns())
            request = folder / 'requests' / (token+'.tcl')
            temp = request.with_suffix('.pending')
            temp.write_text(script+'\n'); temp.replace(request)
            done = request.with_suffix('.done')
            output = request.with_suffix('.out')
            while not done.is_file():
                if not group_alive(pid):
                    raise RuntimeError('native query killed its session; see startup.log')
                current = measure(pid)
                peak = {key: max(peak[key], value) for key, value in current.items()}
                if current['rss_bytes'] > 24*1024**3:
                    exceeded = '24 GiB aggregate resident-memory limit'
                    break
                if time.monotonic()-started >= seconds:
                    timed_out = True
                    break
                time.sleep(.025)
            if done.is_file():
                exit_code = int(done.read_text().strip())
        if timed_out or exceeded:
            os.killpg(pid, signal.SIGKILL)
            deadline = time.monotonic()+1
            while group_alive(pid) and time.monotonic()<deadline:
                time.sleep(.025)
            if group_alive(pid):
                raise RuntimeError('native session survived timeout cleanup')
            identity.update(terminal=True, suspended=False)
        else:
            stop_group(pid)
            identity['suspended'] = True
        registry.write_text(json.dumps(identity)+'\n')
    except BaseException:
        if start_ticks(pid) == identity['start_ticks']:
            try: os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError: pass
        registry.write_text(json.dumps({**identity, 'terminal': True})+'\n')
        raise
    if output is None:
        output = folder / 'startup.log'
    if not output.is_file():
        output.write_text('')
    return {'exit_code': exit_code, 'timed_out': timed_out, 'exceeded': exceeded,
            'session_reused': reused, 'session_identity': identity,
            'output_path': str(output), 'process_seconds': time.monotonic()-started,
            'resources': {'cpu_seconds': max(0, peak['cpu_seconds']-before),
                          'peak_memory_bytes': peak['rss_bytes'],
                          'peak_processes': peak['processes']}}

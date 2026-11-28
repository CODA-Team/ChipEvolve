"""Plain native-baseline supervision and receipts, independent of all EF packages."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def start_ticks(pid):
    try:
        text=Path(f'/proc/{pid}/stat').read_text()
        return int(text[text.rfind(')')+2:].split()[19])
    except (OSError,ValueError,IndexError):return None


def measure(pid):
    pending=[pid];seen=set();rss=0;cpu=0.0
    while pending:
        child=pending.pop()
        if child in seen:continue
        seen.add(child)
        try:
            stat=Path(f'/proc/{child}/stat').read_text();fields=stat[stat.rfind(')')+2:].split()
            cpu+=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
            rss+=int(Path(f'/proc/{child}/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            for thread in Path(f'/proc/{child}/task').iterdir():
                pending.extend(int(v) for v in (thread/'children').read_text().split())
        except (OSError,ValueError,IndexError):continue
    return {'cpu_seconds':cpu,'rss_bytes':rss,'processes':len(seen)}


def group_alive(pgid):
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit():continue
        try:
            stat=(directory/'stat').read_text();fields=stat[stat.rfind(')')+2:].split()
            if int(fields[2])==pgid and fields[0]!='Z':return True
        except (OSError,ValueError,IndexError):continue
    return False


def terminate(process):
    # A completed leader may leave native/container descendants in its group.
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:
        process.wait();return
    end=time.monotonic()+2
    while group_alive(process.pid) and time.monotonic()<end:time.sleep(.05)
    if group_alive(process.pid):
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        end=time.monotonic()+1
        while group_alive(process.pid) and time.monotonic()<end:time.sleep(.05)
    process.wait()


def supervise(command,*,folder,env,seconds,output_path=None):
    process=None;identity=None;started=time.monotonic();timed_out=False;exceeded=None
    peaks={'cpu_seconds':0,'rss_bytes':0,'processes':0}
    try:
        with (output_path or folder/'output.txt').open('w') as output:
            process=subprocess.Popen(command,cwd=folder,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            identity=start_ticks(process.pid)
            (folder/'process.json').write_text(json.dumps({'pid':process.pid,'start_ticks':identity,'terminal':False})+'\n')
            next_measure=0
            while process.poll() is None:
                elapsed=time.monotonic()-started
                if elapsed>=seconds:
                    timed_out=True;terminate(process);break
                if elapsed>=next_measure:
                    current=measure(process.pid);next_measure=elapsed+.5
                    peaks={key:max(peaks[key],value) for key,value in current.items()}
                    if current['rss_bytes']>24*1024**3:
                        exceeded='24 GiB aggregate resident-memory limit';terminate(process);break
                time.sleep(.05)
            process.wait()
    finally:
        if process is not None:
            terminate(process)
            (folder/'process.json').write_text(json.dumps({'pid':process.pid,'start_ticks':identity,'terminal':True,'exit_code':process.returncode})+'\n')
    return {'exit_code':process.returncode,'timed_out':timed_out,'exceeded':exceeded,
            'resources':{'cpu_seconds':peaks['cpu_seconds'],'peak_memory_bytes':peaks['rss_bytes'],'peak_processes':peaks['processes']},
            'process_seconds':time.monotonic()-started}


def cleanup_owned(episode):
    receipts=[]
    for path in (Path(episode)/'native').glob('*/process.json'):
        info=json.loads(path.read_text())
        if info['terminal'] or info.get('start_ticks') is None:continue
        if start_ticks(info['pid'])!=info['start_ticks']:continue
        try:
            os.killpg(info['pid'],signal.SIGCONT)
            os.killpg(info['pid'],signal.SIGTERM)
        except ProcessLookupError:continue
        end=time.monotonic()+2
        while group_alive(info['pid']) and time.monotonic()<end:time.sleep(.05)
        if group_alive(info['pid']):
            try:os.killpg(info['pid'],signal.SIGKILL)
            except ProcessLookupError:pass
            end=time.monotonic()+1
            while group_alive(info['pid']) and time.monotonic()<end:time.sleep(.05)
        receipts.append({'registry':str(path),'pid':info['pid'],'identity_verified':True,'termination_requested':True})
        if not group_alive(info['pid']):
            path.write_text(json.dumps({**info,'terminal':True,'cleanup_completed':True})+'\n')
    return receipts

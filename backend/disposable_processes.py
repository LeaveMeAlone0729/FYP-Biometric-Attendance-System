"""Windows process ownership for the disposable launcher; never trust a bare PID."""
import ctypes
import json
import ntpath
import os
from pathlib import Path
import subprocess
from contextlib import contextmanager
from manual_android_test import require

QUIET=getattr(subprocess,'CREATE_NO_WINDOW',0)


@contextmanager
def lifecycle_lock(env):
    import msvcrt
    with (env/'lifecycle.lock').open('a+b') as lock:
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:require(False,'DISPOSABLE_LIFECYCLE_BUSY')
        try:yield
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def canonical_path(value):return ntpath.normcase(ntpath.normpath(str(value)))


def split_command(command):
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    shell.CommandLineToArgvW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    count=ctypes.c_int();argv=shell.CommandLineToArgvW(command,ctypes.byref(count))
    require(bool(argv),'PROCESS_COMMAND_UNREADABLE')
    try:return [argv[i] for i in range(count.value)]
    finally:kernel.LocalFree(argv)


def normalized_argument(value):
    for prefix in ('--defaults-file=','session.save_path='):
        if value.startswith(prefix):return prefix+canonical_path(value[len(prefix):])
    return canonical_path(value) if ntpath.isabs(value) else value


def query_process(pid):
    require(type(pid) is int and pid>0,'INVALID_STORED_PROCESS_ID')
    command=('Get-CimInstance Win32_Process -Filter "ProcessId='+str(pid)+'" | '
        'Select-Object ProcessId,ExecutablePath,CommandLine,'
        '@{Name="created_at";Expression={$_.CreationDate.ToUniversalTime().ToString("o")}} | ConvertTo-Json -Compress')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
        capture_output=True,text=True,timeout=8,creationflags=QUIET)
    require(result.returncode==0,'PROCESS_INSPECTION_FAILED')
    return json.loads(result.stdout) if result.stdout.strip() else None


def listener_pids(port):
    command=('Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | '
        'Where-Object LocalPort -eq '+str(int(port))+' | Select-Object -ExpandProperty OwningProcess -Unique | ConvertTo-Json -Compress')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],
        capture_output=True,text=True,timeout=8,creationflags=QUIET)
    require(result.returncode==0,'LISTENER_INSPECTION_FAILED')
    data=json.loads(result.stdout) if result.stdout.strip() else []
    return data if isinstance(data,list) else [data]


def matches(row,args,images):
    if not row or not row.get('created_at') or not row.get('ExecutablePath') or not row.get('CommandLine'):return False
    allowed={canonical_path(p) for p in images}
    if canonical_path(row['ExecutablePath']) not in allowed:return False
    actual=split_command(row['CommandLine'])
    return (len(actual)==len(args) and canonical_path(actual[0]) in allowed
        and [normalized_argument(a) for a in actual[1:]]==[normalized_argument(a) for a in args[1:]])


def record(row):
    return dict(pid=row['ProcessId'],created_at=row['created_at'],executable=canonical_path(row['ExecutablePath']))


def read_state(env):
    path=env/'processes.json'
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(env,state):
    # No partial JSON if interrupted. No credentials or arbitrary process commands.
    temp=env/('processes.'+str(os.getpid())+'.tmp')
    temp.write_text(json.dumps(state,indent=2));os.replace(temp,env/'processes.json')


def register(env,kind,pid,args,images):
    row=query_process(pid)
    require(matches(row,args,images),'LAUNCHED_PROCESS_IDENTITY_MISMATCH')
    state=read_state(env);state[kind]=record(row);save_state(env,state)


def verified_pid(env,kind,args,images,port):
    state=read_state(env);stored=state.get(kind)
    pid=stored.get('pid') if isinstance(stored,dict) else stored
    row=query_process(pid) if pid else None
    if row:
        require(all(row.get(k) for k in ('created_at','ExecutablePath','CommandLine')),'PROCESS_IDENTITY_UNREADABLE')
    valid=matches(row,args,images)
    owners=listener_pids(port)
    require(len(owners)<=1,'MULTIPLE_DISPOSABLE_PORT_OWNERS')
    for owner_pid in owners:
        require(matches(query_process(owner_pid),args,images),'FOREIGN_PROCESS_ON_DISPOSABLE_PORT')
    if valid and (not isinstance(stored,dict) or record(row)==stored):
        if not isinstance(stored,dict):state[kind]=record(row);save_state(env,state)
        return pid
    # Missing/recycled PID: inspect the ROLE'S port, never act on the unrelated PID.
    if owners:
        owner=query_process(owners[0])
        require(matches(owner,args,images),'FOREIGN_PROCESS_ON_DISPOSABLE_PORT')
        state[kind]=record(owner);save_state(env,state);return owners[0]
    if valid:
        # A newly started, correctly bound process can be adopted after PID reuse.
        state[kind]=record(row);save_state(env,state);return pid
    if stored is not None:
        with (env/'process-state-history.jsonl').open('a') as log:
            log.write(json.dumps(dict(kind=kind,pid=pid,event='STALE_STATE_RETIRED',
                reason='PROCESS_EXITED' if row is None else 'PID_NO_LONGER_OWNED'))+'\n')
        state.pop(kind,None);save_state(env,state)
    return None


def forget(env,kind,pid):
    state=read_state(env);stored=state.get(kind)
    if (stored.get('pid') if isinstance(stored,dict) else stored)==pid:
        state.pop(kind,None);save_state(env,state)


class ObservedProcess:
    def __init__(self,pid):
        self.pid=pid;row=query_process(pid);self.born=row['created_at'] if row else None
    def poll(self):
        row=query_process(self.pid)
        return None if row and row['created_at']==self.born else 0


def terminate_php(env,pid):
    """Terminate only the verified PHP process object, never a recycled PID."""
    import datetime
    from ctypes import wintypes
    stored=read_state(env).get('phpmyadmin')
    require(isinstance(stored,dict) and stored['pid']==pid,'PHP_IDENTITY_REQUIRED')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1001,False,pid)  # QUERY_LIMITED_INFORMATION | TERMINATE
    require(bool(handle),'PHP_PROCESS_HANDLE_UNAVAILABLE')
    try:
        created,exited,cpu,user=(wintypes.FILETIME() for _ in range(4))
        require(kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(cpu),ctypes.byref(user)),
            'PHP_PROCESS_TIME_UNAVAILABLE')
        born=datetime.datetime.fromisoformat(stored['created_at'])
        delta=born-datetime.datetime(1601,1,1,tzinfo=datetime.timezone.utc)
        expected=(delta.days*86400+delta.seconds)*1000000+delta.microseconds
        actual=((created.dwHighDateTime<<32)|created.dwLowDateTime)//10
        require(actual==expected,'PHP_PROCESS_CREATION_TIME_CHANGED')
        require(kernel.TerminateProcess(handle,0),'PHP_STOP_FAILED')
    finally:kernel.CloseHandle(handle)

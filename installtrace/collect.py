"""Read-only Windows collectors. Never launch or modify a target installer."""
import base64
import ctypes
import hashlib
import json
import os
import platform
import stat
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from .core import CATEGORIES

class Cancelled(Exception):
    pass


def section():
    return {'status': 'complete', 'records': {}, 'errors': []}


def issue(sec, message):
    sec['status'] = 'partial'
    if len(sec['errors']) < 200:
        sec['errors'].append(str(message))


def check(cancel):
    if cancel.is_set():
        raise Cancelled('Capture cancelled; no partial snapshot was saved.')


def normalized_roots(roots):
    # Keep absent roots: an installation may create one later.
    items = sorted({os.path.normcase(os.path.abspath(os.path.expandvars(p))) for p in roots if p.strip()})
    return [p for p in items if not any(p != q and p.startswith(q.rstrip(os.sep) + os.sep) for q in items)]


def default_roots():
    roots = [os.environ.get(k, '') for k in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramData')]
    roots += [os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')]
    return [p for p in roots if p]


def collect_files(roots, hash_limit, cancel, progress):
    sec = section()
    stack = list(roots)
    seen = 0
    while stack:
        check(cancel)
        folder = stack.pop()
        try:
            st = os.lstat(folder)
            if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & 0x400:
                issue(sec, f'Reparse point skipped: {folder}')
                continue
            with os.scandir(folder) as entries:
                for entry in entries:
                    check(cancel)
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if entry.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                            issue(sec, f'Reparse point skipped: {entry.path}')
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            stack.append(entry.path)
                            continue
                        if not stat.S_ISREG(info.st_mode):
                            continue
                        record = {'size': info.st_size, 'modified_ns': info.st_mtime_ns}
                        if hash_limit and info.st_size <= hash_limit:
                            try:
                                h = hashlib.sha256()
                                with open(entry.path, 'rb') as f:
                                    while chunk := f.read(1024 * 1024):
                                        check(cancel)
                                        h.update(chunk)
                                after = entry.stat(follow_symlinks=False)
                                if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                                    issue(sec, f'Changed during scan: {entry.path}')
                                    continue
                                record['sha256'] = h.hexdigest()
                            except OSError as exc:
                                issue(sec, f'Hash failed: {entry.path}: {exc}')
                                continue
                        record['hash_status'] = 'sha256' if 'sha256' in record else 'metadata-only'
                        sec['records'][os.path.normcase(entry.path)] = record
                        seen += 1
                        if seen % 250 == 0:
                            progress(f'Files: {seen:,} inspected…')
                    except OSError as exc:
                        issue(sec, f'{entry.path}: {exc}')
        except FileNotFoundError:
            # A root that does not yet exist is valid empty coverage.
            # A discovered subfolder vanishing is a concurrent-scan gap.
            if folder not in roots:
                issue(sec, f'Directory vanished during scan: {folder}')
        except OSError as exc:
            issue(sec, f'{folder}: {exc}')
    return sec


def collect_registry(cancel):
    import winreg
    sec = section()
    paths = [r'Software\Microsoft\Windows\CurrentVersion\Run',
             r'Software\Microsoft\Windows\CurrentVersion\RunOnce',
             r'Software\Microsoft\Windows\CurrentVersion\Uninstall']
    for hive_name, hive in [('HKLM', winreg.HKEY_LOCAL_MACHINE), ('HKCU', winreg.HKEY_CURRENT_USER)]:
        for view_name, view in [('64', winreg.KEY_WOW64_64KEY), ('32', winreg.KEY_WOW64_32KEY)]:
            for root in paths:
                pending = [(root, True)]
                while pending:
                    check(cancel)
                    path, top = pending.pop()
                    prefix = f'{hive_name}[{view_name}]\\{path}'
                    try:
                        with winreg.OpenKey(hive, path, 0, winreg.KEY_READ | view) as key:
                            count_sub, count_values, _ = winreg.QueryInfoKey(key)
                            sec['records'][prefix.lower()] = {'key_exists': True}
                            for i in range(count_values):
                                name, value, kind = winreg.EnumValue(key, i)
                                if isinstance(value, bytes):
                                    value = {'base64': base64.b64encode(value).decode('ascii')}
                                identity = (prefix + '\\@' + name).lower()
                                sec['records'][identity] = {'type': kind, 'value': value}
                            for i in range(count_sub):
                                pending.append((path + '\\' + winreg.EnumKey(key, i), False))
                    except FileNotFoundError:
                        if not top:
                            issue(sec, 'Registry key vanished: ' + prefix)
                    except OSError as exc:
                        issue(sec, f'{prefix}: {exc}')
    return sec


PS = {
 'services': "@(Get-CimInstance Win32_Service -ErrorAction Stop | ForEach-Object { [PSCustomObject]@{id=$_.Name; path=$_.PathName; startMode=$_.StartMode; account=$_.StartName; displayName=$_.DisplayName} }) | ConvertTo-Json -Depth 8 -Compress",
 'tasks': "@(Get-ScheduledTask -ErrorAction Stop | ForEach-Object { [PSCustomObject]@{id=($_.TaskPath+$_.TaskName); xml=(Export-ScheduledTask -TaskName $_.TaskName -TaskPath $_.TaskPath -ErrorAction Stop)} }) | ConvertTo-Json -Depth 8 -Compress"
}


def powershell_section(category, cancel):
    sec = section()
    script = "$ErrorActionPreference='Stop'; [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); " + PS[category]
    command = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    exe = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    try:
        p = subprocess.Popen([exe, '-NoProfile', '-NonInteractive', '-EncodedCommand', command],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        elapsed = 0
        try:
            while True:
                check(cancel)
                try:
                    output, error = p.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    elapsed += 0.25
                    if elapsed >= 90:
                        raise TimeoutError('Collector exceeded 90 seconds')
            if p.returncode:
                raise RuntimeError(error.decode('utf-8', errors='replace')[:2000])
            data = json.loads(output.decode('utf-8-sig')) if output.strip() else []
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                raise ValueError('Collector returned an invalid record set')
            for row in data:
                identity = str(row.pop('id')).lower()
                sec['records'][identity] = row
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate()
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        sec['status'] = 'unavailable'
        sec['records'] = {}
        sec['errors'].append(str(exc))
    return sec


def capture(roots, hash_mb=16, cancel=None, progress=lambda _: None):
    if os.name != 'nt':
        raise RuntimeError('Live capture requires Windows 10/11. Demo and comparison work on other platforms.')
    cancel = cancel or threading.Event()
    roots = normalized_roots(roots)
    if not roots:
        raise ValueError('Choose at least one folder to inspect.')
    if hash_mb < 0 or hash_mb > 1024:
        raise ValueError('Hash limit must be between 0 and 1024 MiB.')
    started = datetime.now(timezone.utc).isoformat()
    result = {'schema': 1, 'created': started, 'machine': {
        'hostname': platform.node(), 'user': os.environ.get('USERDOMAIN', '') + '\\' + os.environ.get('USERNAME', ''),
        'elevated': bool(ctypes.windll.shell32.IsUserAnAdmin())},
        'scope': {'roots': roots, 'hash_mb': hash_mb, 'collector_version': 1,
                  'registry': 'Run, RunOnce, Uninstall; HKCU/HKLM; 32/64-bit'}, 'sections': {}}
    for cat in CATEGORIES:
        check(cancel)
        progress('Collecting ' + cat + '…')
        if cat == 'files':
            value = collect_files(roots, hash_mb * 1024 * 1024, cancel, progress)
        elif cat == 'registry':
            value = collect_registry(cancel)
        else:
            value = powershell_section(cat, cancel)
        result['sections'][cat] = value
    check(cancel)
    result['completed'] = datetime.now(timezone.utc).isoformat()
    return result

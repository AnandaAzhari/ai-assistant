"""Prevent two local pollers from recovering each other's in-flight work."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path


class TelegramAlreadyRunning(RuntimeError):
    pass


@contextmanager
def telegram_process_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise TelegramAlreadyRunning(
                    'Bot ini sudah dijalankan dari folder project ini. Tutup terminal Telegram atau penemuan ID yang lain.'
                ) from None
            raise
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    # Keep the file: unlinking after unlock allows two processes to lock different inodes.

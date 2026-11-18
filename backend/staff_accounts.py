"""Default accounts for the localhost Local-mode demonstration portal."""
from functools import lru_cache

from security import hash_password


@lru_cache(maxsize=1)
def default_local_accounts():
    # Local-mode portal only. Full mode continues to require its private account.
    return tuple(dict(username=username, password_hash=hash_password(password), role=role)
                 for username, password, role in (
                     ('admin', 'Admin@123', 'admin'),
                     ('teacher', 'Teacher@123', 'teacher'),
                 ))

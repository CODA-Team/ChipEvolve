"""An optional host lease serializes native EDA across execution and direct tools."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

from .environment import require_eda_memory


@contextmanager
def native_activity(environment=None):
    env = dict(os.environ if environment is None else environment)
    configured = env.get('EDA_ACTIVITY_LOCK')
    if not configured or env.get('EDA_ACTIVITY_LEASE_HELD') == configured:
        yield env
        return
    path = Path(configured)
    if not path.is_absolute():
        raise ValueError('EDA_ACTIVITY_LOCK must be an absolute runtime path')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        print('[activity] waiting for native EDA host lease', flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        require_eda_memory()
        print('[activity] native EDA host lease acquired', flush=True)
        env['EDA_ACTIVITY_LEASE_HELD'] = configured
        yield env

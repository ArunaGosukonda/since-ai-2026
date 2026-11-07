"""Run cross-validation folds in parallel processes.

``n_jobs``: None means one process per fold up to the number of CPUs; the
DSA_JOBS environment variable overrides it (e.g. DSA_JOBS=1 to debug).
Results come back in fold order, so they equal a sequential run.
"""
import os

from joblib import Parallel, delayed


def resolve(n_jobs, n_tasks):
    env = os.environ.get("DSA_JOBS")
    if env:
        n_jobs = int(env)
    if not n_jobs:
        n_jobs = os.cpu_count() or 1
    return max(1, min(int(n_jobs), n_tasks))


def map_folds(fn, tasks, n_jobs=None):
    """[fn(*task) for task in tasks], one process per task where possible."""
    tasks = list(tasks)
    n = resolve(n_jobs, len(tasks))
    if n == 1:
        return [fn(*t) for t in tasks]
    return Parallel(n_jobs=n, backend="loky")(delayed(fn)(*t) for t in tasks)

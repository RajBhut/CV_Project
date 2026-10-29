from concurrent.futures import ThreadPoolExecutor

from app.services.analyzer import run_analysis

_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scenetrace-analysis")


def enqueue(job_id: str) -> None:
    _worker.submit(run_analysis, job_id)

"""Bounded, cancellable, ephemeral pixel-processing jobs for the local editor."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid

from map_pixel_processor import process, Cancelled

_LOCK = threading.Lock()
_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix='map-pixel')
_JOBS = {}
TTL_SECONDS = 1800


def _purge():
    now = time.monotonic()
    expired = [key for key, job in _JOBS.items() if job['state'] not in ('queued', 'running') and now - job['updated'] > TTL_SECONDS]
    for key in expired:
        del _JOBS[key]
    finished = sorted((j['updated'], key) for key, j in _JOBS.items() if j['state'] not in ('queued', 'running'))
    for _, key in finished[:-2]:
        del _JOBS[key]


def _public(job):
    return {key: job[key] for key in ('id', 'state', 'progress', 'message', 'elapsedSeconds')}


def start(payload):
    with _LOCK:
        _purge()
        if any(j['state'] in ('queued', 'running') for j in _JOBS.values()):
            raise ValueError('Đang có một lượt xử lý. Đợi hoàn tất hoặc hủy lượt đang chạy.')
        job_id = uuid.uuid4().hex
        job = {'id': job_id, 'state': 'queued', 'progress': 0, 'message': 'Đang chuẩn bị…',
               'elapsedSeconds': 0, 'updated': time.monotonic(), 'cancel': threading.Event()}
        _JOBS[job_id] = job

    def run():
        began = time.monotonic()
        with _LOCK:
            job['state'] = 'running'
            job['began'] = began
        def progress(percent, message):
            with _LOCK:
                job.update(progress=max(job['progress'], percent), message=message,
                           elapsedSeconds=round(time.monotonic() - began, 1), updated=time.monotonic())
        try:
            result = process(payload, progress, job['cancel'].is_set)
            with _LOCK:
                if job['cancel'].is_set():
                    job.update(state='cancelled', message='Đã hủy; ảnh nguồn không thay đổi.')
                else:
                    job.update(state='done', result=result, progress=100, message='Hoàn tất. Xem trước khi áp dụng.')
        except Cancelled as exc:
            with _LOCK:
                job.update(state='cancelled', message=str(exc))
        except Exception as exc:
            with _LOCK:
                job.update(state='failed', message=str(exc))
        finally:
            with _LOCK:
                job.update(updated=time.monotonic(), elapsedSeconds=round(time.monotonic() - began, 1))
    _WORKER.submit(run)
    return {'id': job_id, 'state': 'queued', 'progress': 0, 'message': 'Đang chuẩn bị…', 'elapsedSeconds': 0}


def status(job_id):
    with _LOCK:
        _purge()
        if job_id not in _JOBS:
            raise KeyError('Lượt xử lý không còn trên server. Hãy tạo lượt mới.')
        if _JOBS[job_id]['state'] == 'running':
            _JOBS[job_id]['elapsedSeconds'] = round(time.monotonic() - _JOBS[job_id]['began'], 1)
        return _public(_JOBS[job_id])


def result(job_id):
    with _LOCK:
        if job_id not in _JOBS:
            raise KeyError('Lượt xử lý không còn trên server.')
        if _JOBS[job_id]['state'] != 'done':
            raise ValueError('Kết quả chưa sẵn sàng.')
        return _JOBS[job_id]['result']


def cancel(job_id):
    with _LOCK:
        if job_id not in _JOBS:
            raise KeyError('Lượt xử lý không còn trên server.')
        job = _JOBS[job_id]
        if job['state'] in ('queued', 'running'):
            job['cancel'].set(); job['message'] = 'Đang hủy…'
        return _public(job)

"""GitLab issue checkpoints owned by the scheduler's service account."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid

PREFIX = 'VibeOps 작업 상태\n\n```json\n'
ACTIVE = 'vibeops-running'


@contextmanager
def scheduler_lock():
    """Serialize local ticks. The OS releases the lock on process exit."""
    folder = Path.home() / '.vibeops'
    folder.mkdir(exist_ok=True)
    with (folder / 'scheduler.lock').open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def notes(client, path):
    page = 1
    while True:
        response = client.get(path + '/notes', params={'page': page, 'per_page': 100,
                                                       'order_by': 'created_at', 'sort': 'desc'})
        response.raise_for_status()
        yield from response.json()
        if not response.headers.get('x-next-page'):
            break
        page = int(response.headers['x-next-page'])


def load(client, path, bot, revision):
    for note in notes(client, path):
        if note['author']['id'] == bot and note['body'].startswith(PREFIX):
            return json.loads(note['body'][len(PREFIX):].removesuffix('\n```'))
        if note['author']['id'] == bot and note['body'].startswith(('SDLC 승인 요청', 'SDLC ')):
            raise ValueError('Legacy ticket requires reconciliation before dispatch')
    return dict(revision=revision, stage=0, gate=uuid.uuid4().hex, head=None,
                running=False, session=None, verified=None, mr=None, notice=None)


def save(client, path, row):
    body = PREFIX + json.dumps(row, ensure_ascii=False) + '\n```'
    client.post(path + '/notes', json={'body': body}).raise_for_status()

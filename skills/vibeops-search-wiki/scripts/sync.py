"""Resolve a published wiki to an immutable local checkout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def git(*args):
    return subprocess.check_output(['git', *map(str, args)], text=True,
                                   timeout=120, env={**os.environ, 'GIT_TERMINAL_PROMPT':'0'}).strip()


CONFIG = Path(__file__).resolve().parents[3] / 'config' / 'shared-knowledge.json'


def matching_checkout(path, url, commit):
    if not path:
        return None
    root = Path(path).expanduser().resolve()
    if not root.is_dir() or not any((root / 'openwiki').rglob('*.md')):
        return None
    try:
        if (git('-C', root, 'remote', 'get-url', 'origin') == url
                and git('-C', root, 'rev-parse', 'HEAD') == commit
                and not git('-C', root, 'status', '--porcelain', '--ignored', '--untracked-files=all', '--', 'openwiki')):
            return dict(root=str(root), commit=commit, status='local')
    except subprocess.SubprocessError:
        return None
    return None


def sync(url, branch, local=None):
    if not (url.startswith(('https://', 'ssh://', 'git@')) or Path(url).is_absolute()):
        raise ValueError('Use HTTPS, SSH or an absolute local Git path')
    git('check-ref-format', 'refs/heads/' + branch)
    key = hashlib.sha256((url + '\n' + branch).encode()).hexdigest()
    root = Path.home() / '.cache' / 'sdlc-wiki' / key
    root.mkdir(parents=True, exist_ok=True)
    stamp = root / 'current'
    old = stamp.read_text().strip() if stamp.exists() else ''
    cached = bool(old and (root / old / 'openwiki').is_dir())
    def result(commit, status):
        return dict(root=str(root / commit), commit=commit, status=status)
    try:
        ref = 'refs/heads/' + branch
        commit = git('ls-remote', '--exit-code', url, ref).split()[0]
        checkout = matching_checkout(local, url, commit)
        if checkout:
            return checkout
        dest = root / commit
        with tempfile.TemporaryDirectory(dir=root) as tmp:
            path = Path(tmp) / 'repo'
            if dest.exists() and not matching_checkout(dest, url, commit):
                raise ValueError('Wiki cache differs from its recorded commit')
            if not dest.exists():
                git('clone', '--depth', '1', '--single-branch', '--branch', branch, '--', url, path)
                if git('-C', path, 'rev-parse', 'HEAD') != commit or not any((path/'openwiki').rglob('*.md')):
                    raise ValueError('Unpublished wiki or branch changed during clone')
                try:
                    path.rename(dest)
                except OSError:
                    if not dest.is_dir(): raise
            marker = Path(tmp) / 'current'
            marker.write_text(commit)
            marker.replace(stamp)
        return result(commit, 'verified')
    except (ValueError, OSError, subprocess.SubprocessError):
        if cached and matching_checkout(root / old, url, old):
            return result(old, 'stale-unverified')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    parser.add_argument('--url', default=os.getenv('SDLC_WIKI_URL') or config['url'])
    parser.add_argument('--branch', default=os.getenv('SDLC_WIKI_BRANCH') or config['branch'])
    parser.add_argument('--ttl', type=int, help='Compatibility option; the remote commit is always checked')
    parser.add_argument('--local', default=os.getenv('SDLC_WIKI_LOCAL') or config.get('local_checkout'))
    args = parser.parse_args()
    print(json.dumps(sync(args.url, args.branch, args.local)))

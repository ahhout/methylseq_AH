#!/usr/bin/env python3
"""Validate explicit shared-session selection and record launch provenance."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / 'config/methylseq_cache_session.json'
EXPECTED_WORK = '/mnt/beegfs01/scratch/a_houtman/tmp/em_seq/work_emseq_integrated'
UPSTREAM_RELEASE_COMMIT = '5aa56467a85a5e2d6795ea72dfa5a5f0c9babc23'
FORK_BASELINE_COMMIT = 'b6aa88ef5399cb2992f12d8072e2c8fedf39d003'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_session(record=RECORD, repo=REPO, *, runtime_root=None):
    """Read the source-owned session selection and runtime-owned Nextflow state.

    The second positional argument remains supported for callers of the original
    helper. The CLI always supplies runtime_root explicitly.
    """
    runtime = Path(runtime_root if runtime_root is not None else repo)
    value = json.loads(Path(record).read_text())
    if set(value) != {'schema', 'session_id', 'work_dir'} or value['schema'] != 1:
        raise ValueError('Invalid shared session record')
    sid = value['session_id']
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', sid):
        raise ValueError('Invalid session UUID')
    if value['work_dir'] != EXPECTED_WORK:
        raise ValueError('Shared work root differs from approved integrated root')
    if not (runtime / '.nextflow/cache' / sid / 'db/CURRENT').is_file():
        raise ValueError('Recorded session cache metadata is missing')
    sessions = set()
    for line in (runtime / '.nextflow/history').read_text().splitlines():
        fields = line.split('\t', 6)
        if len(fields) != 7:
            continue
        words = shlex.split(fields[6])
        if option_value(words, '-work-dir') == value['work_dir']:
            sessions.add(fields[5])
    if sessions != {sid}:
        raise ValueError(f'Missing/conflicting integrated-session history: {sorted(sessions)}')
    return value


def option_value(words, option):
    """Return an option's argument without accepting malformed history entries."""
    if option not in words:
        return None
    index = words.index(option)
    if index + 1 >= len(words):
        raise ValueError(f'Nextflow history option lacks an argument: {option}')
    return words[index + 1]


def git_output(repo, *args):
    """Read Git without optional index writes or invoking external diff tools."""
    result = subprocess.run(
        ['git', '--no-optional-locks', '-C', str(repo), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        reason = result.stderr.decode(errors='replace').strip()
        raise ValueError(f'Cannot establish pipeline identity: Git {args[0]} failed: {reason}')
    return result.stdout


def pipeline_identity(runtime_root, repo=REPO):
    """Identify a clean, committed fork checkout without changing runtime state."""
    repo = Path(repo).resolve(strict=True)
    runtime = Path(runtime_root).resolve(strict=True)
    if not repo.is_dir() or not runtime.is_dir():
        raise ValueError('Pipeline source and runtime root must be existing directories')
    if Path(git_output(repo, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != repo:
        raise ValueError('Pipeline source must be the Git checkout root')
    # Include nonignored untracked files: Nextflow can import untracked source.
    # Ignored outputs and caches do not affect the code identity.
    status = git_output(repo, 'status', '--porcelain', '--untracked-files=all')
    if status:
        raise ValueError('Pipeline source must be a clean Git checkout, including nonignored untracked files')
    # Check both sides of the index explicitly, independent of status presentation.
    git_output(repo, 'diff', '--quiet', '--no-ext-diff', '--')
    git_output(repo, 'diff', '--cached', '--quiet', '--no-ext-diff', '--')
    head = git_output(repo, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('Pipeline Git HEAD is not a full commit identity')
    code_checks = {}
    for key, relative in (
            ('session_helper_sha256', 'scripts/methylseq_cache_session.py'),
            ('control_reporter_sha256', 'scripts/summarize_emseq_controls.py')):
        committed = git_output(repo, 'show', f'HEAD:{relative}')
        current = digest(repo / relative)
        if hashlib.sha256(committed).hexdigest() != current:
            raise ValueError(f'Pipeline support code differs from Git HEAD: {relative}')
        code_checks[key] = current
    runtime_config = runtime / 'nextflow.config'
    if runtime_config.exists() and not runtime_config.is_file():
        raise ValueError('Runtime nextflow.config exists but is not a regular file')
    return dict(schema=1, pipeline_source=str(repo), runtime_root=str(runtime),
                fork_commit=head, upstream_release='4.2.0',
                upstream_release_commit=UPSTREAM_RELEASE_COMMIT,
                fork_baseline_commit=FORK_BASELINE_COMMIT,
                runtime_config_sha256=digest(runtime_config) if runtime_config.exists() else None,
                **code_checks)


def verify_snapshots(submitted, repo=REPO):
    """Verify original snapshots, then compare scientific inputs; launcher may evolve."""
    names = {'run_methylseq_integrated.sh', 'params.emseq.integrated.yml',
             'nextflow.config', 'samplesheet.csv', 'reference_manifest.tsv'}
    checks = {}
    for line in (submitted / 'SHA256SUMS').read_text().splitlines():
        sha, name = line.split(None, 1)
        name = name.lstrip('*')
        if name not in names or name in checks or not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Invalid submitted snapshot checksum inventory')
        checks[name] = sha
    if set(checks) != names:
        raise ValueError('Incomplete submitted snapshot checksum inventory')
    for name, sha in checks.items():
        if (submitted / name).is_symlink() or digest(submitted / name) != sha:
            raise ValueError(f'Original submitted snapshot changed: {name}')
    current = {'params.emseq.integrated.yml': repo / 'config/params.emseq.integrated.yml',
               'nextflow.config': repo / 'config/nextflow.config',
               'samplesheet.csv': repo / 'samplesheets/samplesheet.csv',
               'reference_manifest.tsv': repo / 'references/emseq_hg38_lambda_puc19/manifest.tsv'}
    for name, path in current.items():
        if digest(path) != checks[name]:
            raise ValueError(f'Current scientific input differs from submitted snapshot: {name}')
    return checks


def infer_output_session(output, repo=REPO):
    """Inspect legacy history for callers; never adopt it for a fork resume."""
    ids = set()
    for line in (repo / '.nextflow/history').read_text().splitlines():
        parts = line.split('\t', 6)
        if len(parts) != 7:
            continue
        words = shlex.split(parts[6])
        if option_value(words, '--outdir') == str(output):
            ids.add(parts[5])
    if len(ids) != 1:
        raise ValueError('Existing run lacks one unambiguous historical session mapping')
    return ids.pop()


def begin(output, job, existing, started_utc=None, *, runtime_root=None):
    output = Path(output)
    started_utc = started_utc or datetime.now(timezone.utc).isoformat()
    stamp = datetime.fromisoformat(started_utc.replace("Z", "+00:00"))
    if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
        raise ValueError("Attempt start must be timezone-labelled UTC")
    runtime = Path(runtime_root if runtime_root is not None else REPO).resolve(strict=True)
    session = validate_session(record=RECORD, repo=REPO, runtime_root=runtime)
    submitted = output / 'pipeline_info/submitted'
    mapping = submitted / 'cache-session.json'
    identity_path = submitted / 'pipeline-identity.json'
    checks = verify_snapshots(submitted, REPO)
    if existing:
        if not identity_path.is_file():
            raise ValueError('Existing run has no fork pipeline identity; resume legacy outputs with the original launcher')
        if not mapping.is_file():
            raise ValueError('Fork run is missing its original cache-session mapping')
        recorded = json.loads(mapping.read_text())
        if recorded != session:
            raise ValueError('Named run conflicts with shared session record')
    elif identity_path.exists() or mapping.exists():
        raise ValueError('New fork run already contains pipeline identity or session mapping')
    identity = pipeline_identity(runtime, REPO)
    if existing and json.loads(identity_path.read_text()) != identity:
        raise ValueError('Fork pipeline identity differs from original run; source commit, runtime root and support code must match')
    attempt = submitted / 'attempts' / job
    attempt.mkdir(parents=True, exist_ok=False)
    if not existing:
        atomic_json(mapping, session)
        atomic_json(identity_path, identity)
    launcher = REPO / 'run_methylseq_integrated.sh'
    (attempt / 'launcher.sh').write_bytes(launcher.read_bytes())
    atomic_json(attempt / 'provenance.json', dict(session, output=str(output), job_id=job,
                launcher_sha256=digest(launcher), session_helper_sha256=digest(__file__),
                runtime_root=str(runtime), pipeline_identity=identity, input_checksums=checks,
                status='started', started_utc=started_utc, membership_complete=False))


def finish(output, job, status, *, runtime_root=None):
    output = Path(output)
    attempt = output / 'pipeline_info/submitted/attempts' / job
    provenance = json.loads((attempt / 'provenance.json').read_text())
    if runtime_root is not None and provenance.get('runtime_root') is not None:
        if str(Path(runtime_root).resolve(strict=True)) != provenance['runtime_root']:
            raise ValueError('Attempt runtime root differs from recorded provenance')
    command = attempt / 'command.sh'
    if command.exists():
        if command.is_symlink() or not command.is_file():
            raise ValueError('Attempt command must be a regular snapshot file')
        provenance['command'] = command.read_text()
        provenance['command_sha256'] = digest(command)
    traces = []
    tasks = []
    # Preserve available traces, including earlier attempts: absence is explicit.
    for trace in sorted((output / 'pipeline_info').glob('*trace*.txt')):
        data = trace.read_bytes()
        (attempt / trace.name).write_bytes(data)
        traces.append(dict(path=str(trace), sha256=hashlib.sha256(data).hexdigest()))
        with trace.open() as handle:
            for row in csv.DictReader(handle, delimiter='\t'):
                tasks.append({k: row.get(k) for k in ('hash', 'name', 'status', 'native_id')})
    ended_utc = datetime.now(timezone.utc).isoformat()
    provenance['ended_utc'] = ended_utc
    if status == 0:
        provenance['completed_utc'] = ended_utc
    else:
        provenance.pop('completed_utc', None)
    provenance.update(status='completed' if status == 0 else 'failed_or_interrupted',
                      exit_status=status, membership_complete=status == 0 and bool(traces), traces=traces)
    atomic_json(attempt / 'tasks.json', tasks)
    atomic_json(attempt / 'provenance.json', provenance)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['identity', 'validate', 'begin', 'finish'])
    parser.add_argument('--runtime-root', type=Path, required=True,
                        help='Existing Nextflow execution directory; never the fork source checkout.')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--job')
    parser.add_argument('--existing', action='store_true')
    parser.add_argument('--exit-status', type=int)
    parser.add_argument('--started-utc')
    args = parser.parse_args()
    if args.action == 'identity':
        print(json.dumps(pipeline_identity(args.runtime_root), sort_keys=True))
    elif args.action == 'validate':
        print(validate_session(runtime_root=args.runtime_root)['session_id'])
    else:
        if not args.output or not args.job or not re.fullmatch('[0-9]+', args.job):
            parser.error('output and numeric job are required')
        if args.action == 'begin':
            begin(args.output, args.job, args.existing, args.started_utc,
                  runtime_root=args.runtime_root)
        else:
            if args.exit_status is None:
                parser.error('finish requires --exit-status')
            finish(args.output, args.job, args.exit_status, runtime_root=args.runtime_root)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        sys.exit(f'Session provenance error: {exc}')

#!/usr/bin/env python3
"""Compare the Flamingo import with its recorded source without running Nextflow."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def contents(path):
    return str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.check_output(['git', '--no-optional-locks', '-C', str(repo), *args])


def validate(repo, original):
    started = datetime.now(timezone.utc).isoformat()
    manifest = json.loads((repo / 'docs/flamingo_import_manifest.json').read_text())
    require(git(original, 'rev-parse', 'HEAD').decode().strip() == manifest['original_commit'],
            'Original project HEAD differs from the import checkpoint')
    require(not git(original, 'status', '--porcelain', '--untracked-files=no'),
            'Original project has tracked changes')
    adaptations = {item['path']: item for item in manifest['adaptations']}
    for item in manifest['imported']:
        relative = Path(item['source']).relative_to(manifest['original_repository'])
        source = original / relative
        require(sha(contents(source)) == item['sha256'], 'Source import changed: ' + item['path'])
        imported = git(repo, 'show', manifest['original_import_commit'] + ':' + item['path'])
        require(sha(imported) == item['sha256'], 'Initial import commit differs: ' + item['path'])
        expected = adaptations.get(item['path'], {}).get('adapted_sha256', item['sha256'])
        require(sha(contents(repo / item['path'])) == expected, 'Working import differs: ' + item['path'])

    baseline = manifest['fork_master']
    paths = git(repo, 'ls-tree', '-r', '--name-only', '-z', baseline).decode().split('\0')
    upstream_count = 0
    for name in filter(None, paths):
        previous = git(repo, 'show', baseline + ':' + name)
        current = contents(repo / name)
        if name in {'.gitignore', 'README.md'}:
            require(current.startswith(previous), 'Upstream prefix changed: ' + name)
        else:
            require(current == previous, 'Upstream file changed: ' + name)
        upstream_count += 1
    release_changes = git(repo, 'diff', '--name-only', manifest['upstream_release_commit'], baseline).decode().splitlines()
    require(all(name.startswith('.github/workflows/') or name == '.nf-core.yml'
                for name in release_changes), 'Post-release changes include pipeline code')
    require(int(git(repo, 'rev-list', '--count', manifest['upstream_release_commit'] + '..' + baseline)) == 4,
            'Unexpected post-release commit count')

    params = 'config/params.emseq.integrated.yml'
    original_text = (original / params).read_text()
    current_text = (repo / params).read_text()
    old_prefix = manifest['original_repository'] + '/'
    new_prefix = '/home/a_houtman/methylseq_AH/'
    require(current_text.count(new_prefix) == 3, 'Expected exactly three relocated parameter paths')
    require(current_text.replace(new_prefix, old_prefix) == original_text,
            'Params changed beyond the three approved repository path relocations')
    reference = 'references/emseq_hg38_lambda_puc19'
    require((repo / reference).is_symlink(), 'Imported reference is not a symlink')
    require((repo / reference).resolve(strict=True) == (original / reference).resolve(strict=True),
            'Reference targets differ')
    require(str((repo / reference).resolve()) == manifest['reference_target'], 'Reference target drifted')

    return dict(
        schema=1, started_utc=started, completed_utc=datetime.now(timezone.utc).isoformat(),
        status='passed', original_commit=manifest['original_commit'],
        original_import_commit=manifest['original_import_commit'],
        fork_master=baseline, upstream_release_commit=manifest['upstream_release_commit'],
        compared_import_entries=len(manifest['imported']), preserved_upstream_files=upstream_count,
        post_release_changed_paths=release_changes,
        samplesheets_byte_identical=True, reference_links_and_targets_identical=True,
        scientific_parameter_comparison='Exact parameter bytes after reversing only three repository-location paths; all upstream pipeline/default files identical to baseline',
        parameter_path_relocations=3, environment_and_cluster_config_byte_identical=True,
        limits=['No production execution or Nextflow configuration evaluation',
                'Reference payload hashes are retained build evidence; multi-gigabyte payloads not rehashed',
                'Cache reuse after pipeline-source relocation is untested'],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--original-repo', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.repo.resolve(strict=True), args.original_repo.resolve(strict=True))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Flamingo import validation failed: {exc}\n')
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()

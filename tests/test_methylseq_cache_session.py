import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('session', SOURCE / 'scripts/methylseq_cache_session.py')
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)
SID = '17da6065-5303-40ef-8047-5c8ff69a052d'
OTHER = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        self.runtime = self.root / 'runtime'
        (self.runtime / '.nextflow/cache' / SID / 'db').mkdir(parents=True)
        (self.runtime / '.nextflow/cache' / SID / 'db/CURRENT').write_text('MANIFEST-test\n')
        self.record = self.repo / 'record.json'
        self.value = dict(schema=1, session_id=SID, work_dir=session.EXPECTED_WORK)
        self.record.write_text(json.dumps(self.value))
        self.history = self.runtime / '.nextflow/history'
        self.history.write_text(f'date\tduration\tname\tOK\tcommit\t{SID}\tnextflow run pipeline -work-dir {session.EXPECTED_WORK} --outdir /example\n')

    def validate(self):
        return session.validate_session(self.record, self.repo, runtime_root=self.runtime)

    def test_runtime_cache_selection_ignores_unrelated_latest_history(self):
        with self.history.open('a') as handle:
            handle.write(f'date\t-\tother\tOK\tx\t{OTHER}\tnextflow run other -work-dir /other\n')
        self.assertEqual(self.validate()['session_id'], SID)
        self.assertFalse((self.repo / '.nextflow').exists())

    def test_positional_api_remains_compatible(self):
        # The prior API used its repository argument for both locations.
        self.assertEqual(session.validate_session(self.record, self.runtime)['session_id'], SID)

    def test_missing_runtime_cache_fails(self):
        (self.runtime / '.nextflow/cache' / SID / 'db/CURRENT').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.validate()

    def test_conflicting_history_fails(self):
        with self.history.open('a') as handle:
            handle.write(f'd\t-\tn\tOK\tx\t{OTHER}\tnextflow run p -work-dir {session.EXPECTED_WORK}\n')
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            self.validate()

    def test_missing_record_fails(self):
        self.record.unlink()
        with self.assertRaises(OSError):
            self.validate()

    def snapshots(self):
        submitted = self.repo / 'submitted'
        submitted.mkdir()
        paths = {'params.emseq.integrated.yml': 'config/params.emseq.integrated.yml',
                 'nextflow.config': 'config/nextflow.config',
                 'samplesheet.csv': 'samplesheets/samplesheet.csv',
                 'reference_manifest.tsv': 'references/emseq_hg38_lambda_puc19/manifest.tsv',
                 'run_methylseq_integrated.sh': 'run_methylseq_integrated.sh'}
        sums = []
        for name, relative in paths.items():
            data = ('original ' + name).encode()
            (submitted / name).write_bytes(data)
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            sums.append(hashlib.sha256(data).hexdigest() + '  ' + name)
        (submitted / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
        return submitted

    def test_low_level_snapshot_contract_still_allows_launcher_revision(self):
        submitted = self.snapshots()
        (self.repo / 'run_methylseq_integrated.sh').write_text('new bookkeeping')
        session.verify_snapshots(submitted, self.repo)
        self.assertEqual(session.infer_output_session(Path('/example'), self.runtime), SID)

    def test_changed_scientific_input_fails(self):
        submitted = self.snapshots()
        (self.repo / 'samplesheets/samplesheet.csv').write_text('changed samples')
        with self.assertRaisesRegex(ValueError, 'scientific input'):
            session.verify_snapshots(submitted, self.repo)

    def test_tampered_original_launcher_fails(self):
        submitted = self.snapshots()
        (submitted / 'run_methylseq_integrated.sh').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'snapshot changed'):
            session.verify_snapshots(submitted, self.repo)

    def test_ambiguous_legacy_output_mapping_fails(self):
        with self.history.open('a') as handle:
            handle.write(f'd\t-\tn\tOK\tx\t{OTHER}\tnextflow run p --outdir /example\n')
        with self.assertRaisesRegex(ValueError, 'unambiguous'):
            session.infer_output_session(Path('/example'), self.runtime)

    def test_cli_requires_explicit_runtime_root(self):
        for action in ('validate', 'begin', 'finish'):
            with self.subTest(action=action):
                result = subprocess.run(['python3', str(SOURCE / 'scripts/methylseq_cache_session.py'), action],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertIn('--runtime-root', result.stderr)

    def test_launcher_uses_explicit_uuid_and_exit_recording(self):
        text = (SOURCE / 'run_methylseq_integrated.sh').read_text()
        self.assertIn('-resume "$SESSION_ID"', text)
        self.assertNotIn('    -resume\n', text)
        self.assertIn('trap record_attempt_exit EXIT', text)
        self.assertIn('flock -n 9', text)

    def test_interrupted_attempt_records_incomplete_membership(self):
        output = self.repo / 'out'
        attempt = output / 'pipeline_info/submitted/attempts/1'
        attempt.mkdir(parents=True)
        (attempt / 'provenance.json').write_text('{}')
        session.finish(output, '1', 143, runtime_root=self.runtime)
        record = json.loads((attempt / 'provenance.json').read_text())
        self.assertFalse(record['membership_complete'])
        self.assertEqual(record['status'], 'failed_or_interrupted')


class LauncherIntegrationTests(unittest.TestCase):
    """Execute temporary launchers with mock runtimes; never run methylseq."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'source'
        self.repo.mkdir()
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir()
        self.work = self.root / 'scratch/work_emseq_integrated'
        self.work.mkdir(parents=True)
        self.results = self.root / 'results'
        self.results.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        for sub in ('scripts', 'config', 'samplesheets',
                    'references/emseq_hg38_lambda_puc19/BismarkIndex/Bisulfite_Genome/CT_conversion',
                    'references/emseq_hg38_lambda_puc19/BismarkIndex/Bisulfite_Genome/GA_conversion'):
            (self.repo / sub).mkdir(parents=True, exist_ok=True)
        cache = self.runtime / '.nextflow/cache' / SID / 'db'
        cache.mkdir(parents=True)
        (cache / 'CURRENT').write_text('MANIFEST-test\n')
        launcher = (SOURCE / 'run_methylseq_integrated.sh').read_text().replace(
            '/home/a_houtman/methylseq_AH', str(self.repo)).replace(
            '/home/a_houtman/em_seq', str(self.runtime)).replace(
            '/mnt/beegfs01/scratch/a_houtman/tmp/em_seq', str(self.root / 'scratch')).replace(
            '/mnt/beegfs01/scratch/a_houtman/nextflow/nf-core-methylseq/results', str(self.results))
        self.launcher = self.repo / 'run_methylseq_integrated.sh'
        self.launcher.write_text(launcher)
        helper = (SOURCE / 'scripts/methylseq_cache_session.py').read_text().replace(session.EXPECTED_WORK, str(self.work))
        (self.repo / 'scripts/methylseq_cache_session.py').write_text(helper)
        for name in ('params.emseq.integrated.yml', 'nextflow.config'):
            (self.repo / 'config' / name).write_text('original\n')
        (self.repo / 'main.nf').write_text('// mock pipeline source\n')
        (self.repo / 'nextflow.config').write_text('manifest.version = "4.2.0"\n')
        (self.repo / 'config/methylseq_cache_session.json').write_text(
            json.dumps(dict(schema=1, session_id=SID, work_dir=str(self.work))))
        (self.runtime / '.nextflow/history').write_text(
            f'd\t-\told\tOK\tx\t{SID}\tnextflow run p -work-dir {self.work}\n' +
            f'd\t-\tunrelated\tOK\tx\t{OTHER}\tnextflow run p -work-dir /unrelated\n')
        ref = self.repo / 'references/emseq_hg38_lambda_puc19'
        (ref / 'manifest.tsv').write_text('reference\n')
        (ref / 'BismarkIndex/genome.fa').write_text('>phage_lambda\nA\n>plasmid_puc19c\nC\n')
        (ref / 'BismarkIndex/Bisulfite_Genome/CT_conversion/index.bt2').write_text('index')
        raw = self.root / 'raw.fq'
        raw.write_text('raw')
        (self.repo / 'samplesheets/samplesheet.csv').write_text(
            'sample,fastq_1,fastq_2,genome\nsample,' + str(raw) + ',,\n')
        self.executable(self.repo / 'scripts/summarize_emseq_controls.py', '#!/usr/bin/env python3\n')
        (self.repo / '.gitignore').write_text('outputs/\nlogs/\n.nextflow*\n__pycache__/\n')
        conda = self.root / 'conda'
        (conda / 'etc/profile.d').mkdir(parents=True)
        (conda / 'etc/profile.d/conda.sh').write_text('conda() { return 0; }\n')
        self.executable(self.bin / 'conda', '#!/bin/sh\nprintf "%s\\n" ' + shlex.quote(str(conda)) + '\n')
        self.executable(self.bin / 'apptainer', '#!/bin/sh\necho "apptainer version 1.3.6"\n')
        self.executable(self.bin / 'nextflow', f'''#!/usr/bin/env python3
import sys, os, json
from pathlib import Path
args = sys.argv[1:]
with open({str(self.root / 'commands.jsonl')!r}, 'a') as handle:
    handle.write(json.dumps(dict(argv=args, cwd=os.getcwd())) + '\\n')
out = Path(args[args.index('--outdir') + 1])
(out / 'pipeline_info/execution_trace_mock.txt').write_text('hash\\tname\\tstatus\\n00/abcdef\\tmock\\tCOMPLETED\\n')
sys.exit(int(os.environ.get('MOCK_NF_EXIT', '0')))
''')
        envfile = self.root / 'bashenv'
        envfile.write_text('module() { printf "%s\\n" "$*" >> ' +
                           shlex.quote(str(self.root / 'modules.log')) + '; }\n')
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'], BASH_ENV=str(envfile),
                        RUN_NAME='2026-09-21_10-30-emseq-integrated-fixture-v1',
                        SLURM_JOB_ID='1', RESUME_EXISTING='false')
        self.output = self.results / 'bulk' / self.env['RUN_NAME']
        self.submitted = self.output / 'pipeline_info/submitted'
        self.git('init', '-q')
        self.git('config', 'user.name', 'Launcher fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.commit('Create launcher fixture')

    def executable(self, path, text):
        path.write_text(text)
        path.chmod(0o755)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args],
                              capture_output=True, text=True, check=True).stdout.strip()

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-q', '-m', message)

    def run_launcher(self, **changes):
        return subprocess.run(['bash', str(self.launcher)], env=dict(self.env, **changes),
                              capture_output=True, text=True, timeout=30)

    def commands(self):
        path = self.root / 'commands.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def provenance(self, job):
        return json.loads((self.submitted / 'attempts' / str(job) / 'provenance.json').read_text())

    def successful_run(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_new_and_resumed_analysis_pin_fork_source_runtime_and_session(self):
        self.successful_run()
        manifest = (self.submitted / 'run_manifest.tsv').read_bytes()
        first = self.provenance(1)
        identity = json.loads((self.submitted / 'pipeline-identity.json').read_text())
        self.assertEqual(identity['pipeline_source'], str(self.repo))
        self.assertEqual(identity['runtime_root'], str(self.runtime))
        self.assertEqual(identity['fork_commit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual(identity['upstream_release'], '4.2.0')
        self.assertRegex(identity['upstream_release_commit'], r'^[0-9a-f]{40}$')
        self.assertRegex(identity['fork_baseline_commit'], r'^[0-9a-f]{40}$')
        self.assertEqual(identity['session_helper_sha256'], session.digest(self.repo / 'scripts/methylseq_cache_session.py'))
        self.assertEqual(identity['control_reporter_sha256'], session.digest(self.repo / 'scripts/summarize_emseq_controls.py'))
        second = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
        self.assertEqual(second.returncode, 0, second.stderr)
        commands = self.commands()
        self.assertEqual(len(commands), 2)
        for command in commands:
            args = command['argv']
            self.assertEqual(args[args.index('run') + 1], str(self.repo))
            self.assertNotIn('-r', args)
            self.assertEqual(args[args.index('-resume') + 1], SID)
            self.assertEqual(args[args.index('-work-dir') + 1], str(self.work))
            self.assertEqual(command['cwd'], str(self.runtime))
        self.assertFalse((self.repo / '.nextflow').exists())
        self.assertIn('load containers/apptainer/1.3.6', (self.root / 'modules.log').read_text())
        resumed = self.provenance(2)
        self.assertTrue(resumed['membership_complete'])
        self.assertIn('started_utc', resumed)
        self.assertIn('completed_utc', resumed)
        self.assertNotEqual(resumed['job_id'], first['job_id'])
        self.assertEqual(first['pipeline_identity'], identity)
        self.assertEqual(resumed['pipeline_identity'], identity)
        self.assertEqual((self.submitted / 'run_manifest.tsv').read_bytes(), manifest)
        self.assertEqual(first['started_utc'], self.provenance(1)['started_utc'])
        for name, expected in first['input_checksums'].items():
            self.assertEqual(session.digest(self.submitted / name), expected)
        self.assertEqual(shlex.split(first['command']), ['nextflow'] + commands[0]['argv'])
        self.assertEqual(first['command_sha256'], session.digest(self.submitted / 'attempts/1/command.sh'))

    def test_new_outputs_require_valid_utc_date_hour_and_minute(self):
        for name in ('2026-09-21-emseq-integrated-fixture-v1',
                     '2026-09-21_24-00-emseq-integrated-fixture-v1',
                     '2026-09-21_10-60-emseq-integrated-fixture-v1',
                     '2026-02-29_10-30-emseq-integrated-fixture-v1',
                     '2026-13-01_10-30-emseq-integrated-fixture-v1'):
            with self.subTest(name=name):
                result = self.run_launcher(RUN_NAME=name)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.commands(), [])
                self.assertFalse((self.results / 'bulk' / name).exists())

    def test_changed_scientific_inputs_prevent_nextflow_invocation(self):
        self.successful_run()
        for relative in ('config/params.emseq.integrated.yml', 'samplesheets/samplesheet.csv'):
            with self.subTest(relative=relative):
                path = self.repo / relative
                original = path.read_bytes()
                # Keep the samplesheet parseable so snapshot validation decides.
                path.write_bytes(original.replace(b'sample,', b'renamed,') if relative.endswith('.csv') else b'changed interpretation\n')
                self.commit('Change fixture input')
                result = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('scientific input', result.stderr)
                self.assertEqual(len(self.commands()), 1)
                path.write_bytes(original)
                self.commit('Restore fixture input')

    def test_revised_launcher_commit_prevents_resume(self):
        self.successful_run()
        self.launcher.write_text(self.launcher.read_text() + '\n# bookkeeping revision\n')
        self.commit('Revise fixture launcher')
        result = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), 'identity|commit')
        self.assertEqual(len(self.commands()), 1)

    def test_stale_sbatch_spool_copy_fails_before_output_creation(self):
        spool = self.root / 'slurm-spooled-launcher.sh'
        spool.write_bytes(self.launcher.read_bytes())
        self.launcher.write_text(self.launcher.read_text() + '\n# committed after submission\n')
        self.commit('Revise launcher after simulated submission')
        result = subprocess.run(['bash', str(spool)], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Submitted launcher differs', result.stderr)
        self.assertEqual(self.commands(), [])
        self.assertFalse(self.output.exists())

    def test_tampered_snapshot_prevents_resume(self):
        self.successful_run()
        (self.submitted / 'run_methylseq_integrated.sh').write_text('tampered\n')
        result = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('snapshot changed', result.stderr)
        self.assertEqual(len(self.commands()), 1)

    def test_missing_fork_identity_rejects_legacy_resume(self):
        self.successful_run()
        (self.submitted / 'pipeline-identity.json').unlink()
        result = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), 'identity|legacy|original launcher')
        self.assertEqual(len(self.commands()), 1)

    def test_tampered_fork_identity_prevents_resume(self):
        self.successful_run()
        path = self.submitted / 'pipeline-identity.json'
        identity = json.loads(path.read_text())
        identity['fork_commit'] = '0' * 40
        path.write_text(json.dumps(identity))
        result = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('identity', result.stderr.lower())
        self.assertEqual(len(self.commands()), 1)

    def test_changed_runtime_config_prevents_resume(self):
        self.successful_run()
        (self.runtime / 'nextflow.config').write_text('// newly introduced runtime settings\n')
        result = self.run_launcher(SLURM_JOB_ID='2', RESUME_EXISTING='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('identity', result.stderr.lower())
        self.assertEqual(len(self.commands()), 1)

    def test_missing_submitted_snapshot_directory_rejects_resume(self):
        self.output.mkdir(parents=True)
        (self.output / 'historical.txt').write_text('legacy\n')
        result = self.run_launcher(RESUME_EXISTING='true')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('snapshot', result.stderr)
        self.assertEqual(self.commands(), [])

    def test_dirty_tracked_checkout_prevents_nextflow_invocation(self):
        (self.repo / 'main.nf').write_text('// changed tracked pipeline\n')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(result.stderr.lower(), 'dirty|uncommitted|clean')
        self.assertEqual(self.commands(), [])

    def test_missing_required_files_and_directories_fail_early(self):
        for relative, base in (
                ('config/nextflow.config', self.repo),
                ('config/params.emseq.integrated.yml', self.repo),
                ('samplesheets/samplesheet.csv', self.repo),
                ('scripts/methylseq_cache_session.py', self.repo),
                ('scripts/summarize_emseq_controls.py', self.repo),
                ('main.nf', self.repo),
                ('nextflow.config', self.repo),
                ('references/emseq_hg38_lambda_puc19/manifest.tsv', self.repo),
                ('references/emseq_hg38_lambda_puc19/BismarkIndex/genome.fa', self.repo),
                ('.nextflow/cache/' + SID + '/db/CURRENT', self.runtime),
                ('.nextflow/history', self.runtime)):
            with self.subTest(relative=relative):
                path = base / relative
                hidden = path.with_name(path.name + '.hidden')
                path.rename(hidden)
                try:
                    result = self.run_launcher()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.commands(), [])
                    self.assertFalse(self.output.exists())
                finally:
                    hidden.rename(path)

    def test_missing_source_runtime_and_work_parent_fail_early(self):
        for path in (self.repo, self.runtime, self.root / 'scratch', self.work, self.results):
            with self.subTest(path=path):
                # Launch an external copy so the source-directory guard executes.
                external = self.root / 'launch-copy.sh'
                external.write_bytes(self.launcher.read_bytes())
                hidden = path.with_name(path.name + '-hidden')
                path.rename(hidden)
                try:
                    result = subprocess.run(['bash', str(external)], env=self.env,
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.commands(), [])
                    self.assertFalse(self.output.exists())
                finally:
                    hidden.rename(path)

    def test_failed_attempt_is_marked_incomplete(self):
        result = self.run_launcher(MOCK_NF_EXIT='7')
        self.assertEqual(result.returncode, 7, result.stderr)
        record = self.provenance(1)
        self.assertFalse(record['membership_complete'])
        self.assertEqual(record['exit_status'], 7)
        self.assertIn('started_utc', record)
        self.assertIn('ended_utc', record)
        self.assertNotIn('completed_utc', record)
        self.assertEqual(record['pipeline_identity']['fork_commit'], self.git('rev-parse', 'HEAD'))
        self.assertTrue(record['input_checksums'])

    def test_maintenance_lock_prevents_nextflow_invocation(self):
        import fcntl
        with (self.root / 'scratch/.methylseq-cache-maintenance.lock').open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('in use', result.stderr)
        self.assertEqual(self.commands(), [])
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()

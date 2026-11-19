"""CLI behaviour is the complete user surface for S-05.01.01."""
import json

from offsetx_apollo_builder.crawl_cli import main
from offsetx_apollo_builder.crawl import FrontierRunner
from test_crawl_frontier import page


def arguments(tmp_path):
    return ['--db', str(tmp_path/'crawl.db'), '--allow', 'example.test', '--delay', '0']


def test_seed_inspect_and_run_commands_share_a_real_persisted_queue(tmp_path, capsys, monkeypatch):
    args = arguments(tmp_path)
    assert main(args + ['inspect']) == 0
    assert json.loads(capsys.readouterr().out)['total'] == 0
    assert main(args + ['seed', 'https://example.test/a']) == 0
    assert json.loads(capsys.readouterr().out)['added'] == 1
    from offsetx_apollo_builder import crawl_cli
    class Fetcher:
        def fetch(self, url):
            return page(url)
    monkeypatch.setattr(crawl_cli, 'FrontierRunner', lambda f: FrontierRunner(f, fetcher=Fetcher()))
    assert main(args + ['run', '--max-pages', '1']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['fetched'] == 1
    assert main(args + ['inspect']) == 0
    assert json.loads(capsys.readouterr().out)['urls'][0]['checks'] == 1


def test_cli_reports_refused_target_without_traceback_or_partial_seed(tmp_path, capsys):
    args = arguments(tmp_path)
    assert main(args + ['seed', 'https://example.test/a', 'http://127.0.0.1/private']) == 2
    assert 'refused' in json.loads(capsys.readouterr().err)['error']
    assert main(args + ['inspect']) == 0
    assert json.loads(capsys.readouterr().out)['total'] == 0


def test_failed_batch_has_nonzero_exit_and_persists_retry(tmp_path, capsys, monkeypatch):
    from offsetx_apollo_builder import crawl_cli
    from offsetx_apollo_builder.discovery import DiscoveryFetchError
    args = arguments(tmp_path)
    assert main(args + ['seed', 'https://example.test/a']) == 0
    capsys.readouterr()
    class Fetcher:
        def fetch(self, url):
            raise DiscoveryFetchError('network unavailable')
    monkeypatch.setattr(crawl_cli, 'FrontierRunner', lambda f: FrontierRunner(f, fetcher=Fetcher()))
    assert main(args + ['run', '--max-pages', '1']) == 1
    assert json.loads(capsys.readouterr().out)['failed'] == 1


def test_watch_stops_cleanly_when_interrupted(tmp_path, capsys, monkeypatch):
    from offsetx_apollo_builder import crawl_cli
    monkeypatch.setattr(crawl_cli.time, 'sleep', lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert main(arguments(tmp_path) + ['watch', '--poll-seconds', '0.1']) == 130
    assert json.loads(capsys.readouterr().out)['attempted'] == 0


def test_remove_command_is_explicit_and_idempotent(tmp_path, capsys):
    args = arguments(tmp_path)
    assert main(args + ['seed', 'https://example.test/a']) == 0
    capsys.readouterr()
    assert main(args + ['remove', 'https://example.test/a']) == 0
    assert json.loads(capsys.readouterr().out)['removed'] is True
    assert main(args + ['remove', 'https://example.test/a']) == 0
    assert json.loads(capsys.readouterr().out)['removed'] is False

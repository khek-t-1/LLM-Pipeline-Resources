#!/usr/bin/env python3
"""Stream a large public Gofile ZIP into resumable GitHub Release parts."""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path('/home/user/llm_resources_release')
STATE_PATH = ROOT / 'stream_state.json'
TEMP_PART = Path('/tmp/llm-resources-current.part')
TOKEN_PATH = Path('/home/user/.llm_release_oauth_token')
REPO = 'khek-t-1/LLM-Pipeline-Resources'
TAG = 'v1.0'
TITLE = 'LLM Pipeline Resources — Full Standalone Bundle (14.1 GB)'
GOFILE_CODE = 'IQ22UNfo'
ARCHIVE_NAME = 'llm-resources-full.zip'
EXPECTED_BYTES = 14_095_115_088
EXPECTED_MD5 = '7fbd96c0a166300db65dfccc850c30ab'
PART_SIZE = 512 * 1024 * 1024
PART_COUNT = math.ceil(EXPECTED_BYTES / PART_SIZE)
API = f'https://api.github.com/repos/{REPO}'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'


def log(message: str) -> None:
    print(message, flush=True)


def atomic_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class GitHub:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'Arena-LLM-Resources-Streamer',
        })

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop('timeout', (20, 120))
        return self.session.request(method, url, timeout=timeout, **kwargs)

    def assets(self, release_id: int) -> list[dict]:
        result = []
        page = 1
        while True:
            response = self.request('GET', f'{API}/releases/{release_id}/assets', params={'per_page': 100, 'page': page})
            response.raise_for_status()
            batch = response.json()
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    def initialize_if_empty(self) -> str:
        response = self.request('GET', API)
        response.raise_for_status()
        repo = response.json()
        if not repo.get('permissions', {}).get('push'):
            raise RuntimeError('No push permission on target repository')
        default_branch = repo.get('default_branch') or 'main'
        branch = self.request('GET', f'{API}/branches/{default_branch}')
        if branch.status_code == 200:
            return branch.json()['commit']['sha']
        if branch.status_code != 404:
            branch.raise_for_status()

        log(f'Empty repository detected; initializing {default_branch} with documentation...')
        user_response = self.request('GET', 'https://api.github.com/user')
        user_response.raise_for_status()
        user = user_response.json()
        identity = {
            'name': user.get('name') or user['login'],
            'email': f"{user.get('id')}+{user['login']}@users.noreply.github.com",
            'date': datetime.now(timezone.utc).isoformat(),
        }
        # Git Data blobs cannot be created while a repository has zero commits.
        # Create the root README commit through the Contents API first.
        root_commit = self.request('PUT', f'{API}/contents/README.md', json={
            'message': 'Initial commit: LLM Pipeline Resources documentation',
            'content': base64.b64encode((ROOT / 'README.md').read_bytes()).decode('ascii'),
            'branch': default_branch,
            'author': identity,
            'committer': identity,
        })
        if root_commit.status_code not in (200, 201):
            raise RuntimeError(f'Root README commit failed: {root_commit.status_code} {root_commit.text[:800]}')
        root_commit_data = root_commit.json()['commit']
        root_sha = root_commit_data['sha']
        log(f'Root README commit pushed: {root_sha}')

        files = {
            'JOIN.md': ROOT / 'JOIN.md',
            'docs/RELEASE_PLAN.md': ROOT / 'RELEASE_PLAN.md',
            'docs/ARCHIVE_SUMMARY.json': ROOT / 'archive_summary.json',
            'scripts/stream_release.py': Path(__file__).resolve(),
        }
        tree = []
        for remote_path, local_path in files.items():
            content = base64.b64encode(local_path.read_bytes()).decode('ascii')
            blob = self.request('POST', f'{API}/git/blobs', json={'content': content, 'encoding': 'base64'})
            if blob.status_code not in (200, 201):
                raise RuntimeError(f'Blob creation failed for {remote_path}: {blob.text[:500]}')
            tree.append({'path': remote_path, 'mode': '100644', 'type': 'blob', 'sha': blob.json()['sha']})
        gitignore = self.request('POST', f'{API}/git/blobs', json={
            'content': base64.b64encode(b'*.part\n.stream*\n__pycache__/\n').decode('ascii'),
            'encoding': 'base64',
        })
        gitignore.raise_for_status()
        tree.append({'path': '.gitignore', 'mode': '100644', 'type': 'blob', 'sha': gitignore.json()['sha']})

        created_tree = self.request('POST', f'{API}/git/trees', json={
            'base_tree': root_commit_data['tree']['sha'], 'tree': tree,
        })
        if created_tree.status_code not in (200, 201):
            raise RuntimeError(f'Tree creation failed: {created_tree.text[:500]}')
        commit = self.request('POST', f'{API}/git/commits', json={
            'message': 'Add release plan, archive summary, join guide, and streaming pipeline',
            'tree': created_tree.json()['sha'],
            'parents': [root_sha],
            'author': identity,
            'committer': identity,
        })
        if commit.status_code not in (200, 201):
            raise RuntimeError(f'Documentation commit failed: {commit.text[:500]}')
        sha = commit.json()['sha']
        ref = self.request('PATCH', f'{API}/git/refs/heads/{default_branch}', json={'sha': sha, 'force': False})
        if ref.status_code not in (200, 201):
            raise RuntimeError(f'Main ref update failed: {ref.text[:500]}')
        log(f'Documentation commit pushed: {sha}')
        return sha

    def ensure_release(self, target_sha: str) -> dict:
        tag = self.request('GET', f'{API}/git/ref/tags/{TAG}')
        if tag.status_code == 404:
            created = self.request('POST', f'{API}/git/refs', json={'ref': f'refs/tags/{TAG}', 'sha': target_sha})
            if created.status_code not in (200, 201):
                raise RuntimeError(f'Tag creation failed: {created.text[:500]}')
            log(f'Remote tag created: {TAG}')
        else:
            tag.raise_for_status()
            log(f'Remote tag already exists: {TAG}')

        notes = (ROOT / 'RELEASE_NOTES.md').read_text(encoding='utf-8')
        release = self.request('GET', f'{API}/releases/tags/{TAG}')
        if release.status_code == 404:
            release = self.request('POST', f'{API}/releases', json={
                'tag_name': TAG,
                'target_commitish': target_sha,
                'name': TITLE,
                'body': notes,
                'draft': False,
                'prerelease': False,
            })
            if release.status_code not in (200, 201):
                raise RuntimeError(f'Release creation failed: {release.text[:800]}')
            log('GitHub Release created.')
        else:
            release.raise_for_status()
            release = self.request('PATCH', f'{API}/releases/{release.json()["id"]}', json={
                'name': TITLE, 'body': notes, 'draft': False, 'prerelease': False,
            })
            release.raise_for_status()
            log('Existing release found; resuming assets.')
        return release.json()

    def delete_asset(self, asset: dict) -> None:
        response = self.request('DELETE', f'{API}/releases/assets/{asset["id"]}')
        if response.status_code not in (200, 204):
            raise RuntimeError(f'Could not delete asset {asset["name"]}: {response.text[:400]}')

    def upload(self, upload_base: str, path: Path, expected_size: int | None = None, asset_name: str | None = None) -> dict:
        size = path.stat().st_size if expected_size is None else expected_size
        upload_name = asset_name or path.name
        last_error = ''
        for attempt in range(1, 7):
            try:
                log(f'  Upload attempt {attempt}: {upload_name} ({size / 1024**2:.1f} MiB)')
                with path.open('rb') as handle:
                    response = self.request(
                        'POST', upload_base,
                        params={'name': upload_name},
                        headers={'Content-Type': 'application/octet-stream'},
                        data=handle,
                        timeout=(20, 600),
                    )
                if response.status_code in (200, 201):
                    asset = response.json()
                    if asset.get('size') != size:
                        raise IOError(f'GitHub size mismatch: {asset.get("size")} != {size}')
                    return asset
                last_error = f'HTTP {response.status_code}: {response.text[:500]}'
            except Exception as error:
                last_error = f'{type(error).__name__}: {error}'
            log(f'  Upload retry needed: {last_error}')
            if attempt < 6:
                time.sleep(min(45, 2 ** attempt))
        raise RuntimeError(f'Upload failed for {upload_name}: {last_error}')


def gofile_source() -> tuple[requests.Session, str, str]:
    session = requests.Session()
    session.headers.update({'User-Agent': UA, 'Referer': 'https://gofile.io/'})
    account = session.post('https://api.gofile.io/accounts', timeout=30).json()['data']
    token = account['token']
    session.cookies.set('accountToken', token, domain='.gofile.io', path='/')
    work = Path('/tmp/llm-stream-gofile')
    work.mkdir(exist_ok=True)
    wt_path = work / 'wt.js'
    wt_response = session.get('https://gofile.io/js/wt.obf.js', timeout=30)
    wt_response.raise_for_status()
    wt_path.write_bytes(wt_response.content)
    runner = work / 'run.js'
    runner.write_text(
        "const fs=require('fs'),vm=require('vm');const ctx={console,navigator:{userAgent:" + json.dumps(UA) +
        ",language:'en-US'}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(" + json.dumps(str(wt_path)) +
        ",'utf8'),ctx);process.stdout.write(ctx.generateWT(process.argv[2]));",
        encoding='utf-8',
    )
    website_token = subprocess.check_output(['node', str(runner), token], text=True).strip()
    headers = {
        'Authorization': f'Bearer {token}',
        'X-Website-Token': website_token,
        'X-BL': 'en-US',
        'Origin': 'https://gofile.io',
        'Referer': 'https://gofile.io/',
    }
    response = session.get(f'https://api.gofile.io/contents/{GOFILE_CODE}', params={
        'page': 1, 'pageSize': 100, 'sortField': 'name', 'sortDirection': 1,
    }, headers=headers, timeout=30)
    response.raise_for_status()
    data = response.json()
    files = [x for x in data['data'].get('children', {}).values() if x['type'] == 'file']
    if len(files) != 1:
        raise RuntimeError(f'Expected one Gofile file, found {len(files)}')
    item = files[0]
    if int(item['size']) != EXPECTED_BYTES or item.get('md5') != EXPECTED_MD5:
        raise RuntimeError('Remote archive identity/size changed; refusing to upload a different archive')
    return session, item['link'], token


def download_part(session: requests.Session, url: str, token: str, index: int) -> tuple[str, int]:
    start = index * PART_SIZE
    expected = min(PART_SIZE, EXPECTED_BYTES - start)
    end = start + expected - 1
    last_error = ''
    for attempt in range(1, 7):
        offset = TEMP_PART.stat().st_size if TEMP_PART.exists() else 0
        if offset > expected:
            TEMP_PART.unlink()
            offset = 0
        digest = hashlib.sha256()
        if offset:
            with TEMP_PART.open('rb') as existing:
                for chunk in iter(lambda: existing.read(4 * 1024 * 1024), b''):
                    digest.update(chunk)
        range_start = start + offset
        log(f'  Range attempt {attempt}: bytes={range_start}-{end}; local={offset / 1024**2:.1f} MiB')
        try:
            with session.get(url, headers={
                'Range': f'bytes={range_start}-{end}',
                'Cookie': f'accountToken={token}',
                'Authorization': f'Bearer {token}',
            }, stream=True, timeout=(20, 180)) as response:
                if response.status_code != 206:
                    raise IOError(f'Expected HTTP 206, got {response.status_code}')
                with TEMP_PART.open('ab') as output:
                    for chunk in response.iter_content(4 * 1024 * 1024):
                        if not chunk:
                            continue
                        output.write(chunk)
                        digest.update(chunk)
            actual = TEMP_PART.stat().st_size
            if actual != expected:
                raise IOError(f'Part size {actual} != {expected}')
            return digest.hexdigest(), expected
        except Exception as error:
            last_error = f'{type(error).__name__}: {error}'
            log(f'  Range retry needed: {last_error}')
            if attempt < 6:
                time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f'Part {index:02d} download failed: {last_error}')


def main() -> int:
    started = time.time()
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {
        'archive': ARCHIVE_NAME, 'archiveBytes': EXPECTED_BYTES, 'partSize': PART_SIZE, 'parts': {},
    }
    state.setdefault('parts', {})
    github = GitHub(TOKEN_PATH.read_text().strip())
    target_sha = github.initialize_if_empty()
    release = github.ensure_release(target_sha)
    release_id = release['id']
    upload_base = release['upload_url'].split('{', 1)[0]
    release_url = release['html_url']
    existing = {a['name']: a for a in github.assets(release_id)}
    source, source_url, source_token = gofile_source()
    archive_hasher = hashlib.sha256()
    archive_hash_complete = True
    skipped_any = False
    uploaded = []
    skipped = []

    log(f'=== Streaming {EXPECTED_BYTES / 1e9:.3f} GB into {PART_COUNT} parts ===')
    for index in range(PART_COUNT):
        name = f'{ARCHIVE_NAME}.{index:02d}.part'
        start = index * PART_SIZE
        expected = min(PART_SIZE, EXPECTED_BYTES - start)
        saved = state['parts'].get(str(index))
        old_asset = existing.get(name)
        if old_asset and old_asset.get('size') == expected and saved and saved.get('sha256') and saved.get('bytes') == expected:
            log(f'[{index + 1}/{PART_COUNT}] SKIP verified existing part {name}')
            skipped.append(name)
            skipped_any = True
            archive_hash_complete = False
            continue
        if old_asset and old_asset.get('size') != expected:
            github.delete_asset(old_asset)
            existing.pop(name, None)

        log(f'[{index + 1}/{PART_COUNT}] Processing {name} ({expected / 1024**2:.1f} MiB)')
        TEMP_PART.unlink(missing_ok=True)
        part_hash, actual_size = download_part(source, source_url, source_token, index)
        with TEMP_PART.open('rb') as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
                archive_hasher.update(chunk)

        if old_asset and old_asset.get('size') == expected:
            asset = old_asset
            log('  Asset already on GitHub; hash recovered from source, upload skipped.')
            skipped.append(name)
        else:
            asset = github.upload(upload_base, TEMP_PART, expected, asset_name=name)
            existing[name] = asset
            uploaded.append(name)
        state['parts'][str(index)] = {
            'name': name, 'bytes': actual_size, 'sha256': part_hash,
            'githubAssetId': asset['id'], 'uploaded': True,
        }
        atomic_json(STATE_PATH, state)
        TEMP_PART.unlink(missing_ok=True)
        elapsed = max(time.time() - started, 1)
        completed = sum(int(state['parts'][str(i)]['bytes']) for i in range(PART_COUNT) if str(i) in state['parts'])
        log(f'  Completed {completed / 1e9:.3f}/{EXPECTED_BYTES / 1e9:.3f} GB; elapsed {elapsed / 60:.1f} min')

    if skipped_any:
        archive_hash_complete = False
    if archive_hash_complete:
        state['archiveSha256'] = archive_hasher.hexdigest()
    archive_sha = state.get('archiveSha256', '')
    if archive_sha:
        log(f'Archive SHA-256: {archive_sha}')
    else:
        log('Archive SHA-256 unavailable after a resumed run; per-part hashes remain complete.')

    checksum_path = ROOT / 'SHA256SUMS.txt'
    checksum_path.write_text(''.join(
        f"{state['parts'][str(i)]['sha256']}  {ARCHIVE_NAME}.{i:02d}.part\n" for i in range(PART_COUNT)
    ), encoding='utf-8')
    manifest_path = ROOT / 'MANIFEST.csv'
    with manifest_path.open('w', newline='', encoding='utf-8') as handle:
        fields = ['archive', 'archive_bytes', 'archive_sha256', 'gofile_md5', 'part', 'part_bytes', 'part_sha256']
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i in range(PART_COUNT):
            part = state['parts'][str(i)]
            writer.writerow({
                'archive': ARCHIVE_NAME, 'archive_bytes': EXPECTED_BYTES,
                'archive_sha256': archive_sha, 'gofile_md5': EXPECTED_MD5,
                'part': part['name'], 'part_bytes': part['bytes'], 'part_sha256': part['sha256'],
            })
    atomic_json(STATE_PATH, state)

    metadata_files = [checksum_path, manifest_path, ROOT / 'JOIN.md', ROOT / 'ZIP_CONTENTS.csv']
    # ZIP_CONTENTS.csv is the release-asset spelling of the inspected local listing.
    contents_source = ROOT / 'zip_contents.csv'
    contents_asset = ROOT / 'ZIP_CONTENTS.csv'
    if contents_source.exists() and not contents_asset.exists():
        contents_asset.write_bytes(contents_source.read_bytes())
    metadata_files = [checksum_path, manifest_path, ROOT / 'JOIN.md', contents_asset]
    for path in metadata_files:
        size = path.stat().st_size
        old = existing.get(path.name)
        if old and old.get('size') == size and path.name not in ('SHA256SUMS.txt', 'MANIFEST.csv'):
            log(f'SKIP metadata {path.name}')
            continue
        if old:
            github.delete_asset(old)
            existing.pop(path.name, None)
        asset = github.upload(upload_base, path, size)
        existing[path.name] = asset
        uploaded.append(path.name)

    final_assets = github.assets(release_id)
    final_map = {asset['name']: asset for asset in final_assets}
    expected_sizes = {
        **{f'{ARCHIVE_NAME}.{i:02d}.part': min(PART_SIZE, EXPECTED_BYTES - i * PART_SIZE) for i in range(PART_COUNT)},
        **{path.name: path.stat().st_size for path in metadata_files},
    }
    missing = [name for name, size in expected_sizes.items() if name not in final_map or final_map[name].get('size') != size]
    report = {
        'repository': REPO, 'tag': TAG, 'targetCommit': target_sha, 'releaseUrl': release_url,
        'finishedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'elapsedSeconds': round(time.time() - started, 1),
        'archiveBytes': EXPECTED_BYTES, 'archiveSha256': archive_sha,
        'partCount': PART_COUNT, 'expectedAssets': len(expected_sizes),
        'assetsOnRelease': len(final_assets), 'uploadedThisRun': uploaded,
        'skippedAlreadyPresent': skipped, 'missingOrWrongSize': missing,
        'verificationPassed': not missing,
    }
    atomic_json(ROOT / 'github_release_report.json', report)
    if missing:
        log(f'GITHUB_RELEASE_INCOMPLETE: {release_url}; missing={missing}')
        return 1
    log(f'GITHUB_RELEASE_COMPLETE: {release_url}')
    log(f'Verified {len(expected_sizes)} expected assets on GitHub.')
    return 0


if __name__ == '__main__':
    exit_code = 1
    try:
        exit_code = main()
    finally:
        TEMP_PART.unlink(missing_ok=True)
        # Keep a failed run's short-lived token available for immediate retries;
        # always remove it after a fully verified release.
        if exit_code == 0:
            TOKEN_PATH.unlink(missing_ok=True)
    raise SystemExit(exit_code)

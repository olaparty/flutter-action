#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import shutil
import zipfile
import tarfile
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("The requests module is not installed, attempting to install...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests
    except subprocess.CalledProcessError:
        print("Installation failed. Please install the requests module manually.")
        sys.exit(1)
    else:
        print("The requests module has been successfully installed.")

def filter_releases(data, channel, arch, version):
    releases = data['releases']
    releases = [r for r in releases if r['channel'] in ('any', channel)]
    releases = [r for r in releases if r.get('dart_sdk_arch') == arch or (arch == 'x64' and 'dart_sdk_arch' not in r)]
    
    if version != 'any':
        version = version.lstrip('v')
        releases = [r for r in releases if r['version'] == version or 
                    (r['version'].startswith(f"{version}.") and r['version'] != version)]
    
    return releases[:1] if version == 'any' else releases

def transform_path(path, os_name):
    return path.lstrip('/').replace('/', '\\') if os_name == 'windows' else path

def download_and_extract_archive(archive_url, dest_folder):
    archive_name = os.path.basename(archive_url)
    archive_local = Path(os.environ['RUNNER_TEMP']) / archive_name

    response = requests.get(archive_url, timeout=15)
    response.raise_for_status()

    with open(str(archive_local), 'wb') as f:
        f.write(response.content)

    os.makedirs(dest_folder, exist_ok=True)

    if archive_name.endswith('.zip'):
        with zipfile.ZipFile(str(archive_local), 'r') as zip_ref:
            zip_ref.extractall(os.environ['RUNNER_TEMP'])
        shutil.rmtree(dest_folder)  # Remove the folder to allow a simple rename
        os.rename(str(Path(os.environ['RUNNER_TEMP']) / 'flutter'), dest_folder)
    else:
        with tarfile.open(str(archive_local), 'r') as tar_ref:
            tar_ref.extractall(dest_folder)

    os.remove(str(archive_local))

def expand_key(key, version_manifest, os_name):
    replacements = {
        ':channel:': version_manifest['channel'],
        ':version:': version_manifest['version'],
        ':arch:': version_manifest.get('dart_sdk_arch', 'x64'),
        ':hash:': version_manifest['hash'],
        ':sha256:': version_manifest['sha256'],
        ':os:': os_name
    }
    for placeholder, value in replacements.items():
        key = key.replace(placeholder, value)
    return key

def set_github_output(name, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'{name}={value}', file=fh)

def action():
    parser = argparse.ArgumentParser(description='Flutter Cache Setup')
    parser.add_argument('-c', '--cache-path', default='', help='Cache path for Flutter installation')
    parser.add_argument('-k', '--cache-key', default='', help='Cache key for Flutter installation')
    parser.add_argument('-p', '--print-only', action='store_true', help='Print only, do not perform installation')
    parser.add_argument('-t', '--test-mode', action='store_true', help='Enable test mode')
    parser.add_argument('-a', '--arch', default='', help='Target architecture (e.g., x64)')
    parser.add_argument('-n', '--version', default='', help='Flutter version (e.g., v2.5.0)')
    parser.add_argument('-r', '--repo-url', default='', help='URL of the Flutter repository')
    parser.add_argument('--channel', default='stable', help='Flutter channel (e.g., stable)')

    args = parser.parse_args()

    os_name = os.environ.get('RUNNER_OS', 'macos').lower()
    manifest_base_url = "https://storage.googleapis.com/flutter_infra_release/releases"
    manifest_json_path = f"releases_{os_name}.json"
    manifest_url = f"{manifest_base_url}/{manifest_json_path}"

    channel = args.channel or 'stable'
    version = args.version or 'any'
    arch = args.arch.lower() or 'x64'

    if not args.cache_path or args.cache_path == "''":
        cache_path = os.path.join(os.environ.get('RUNNER_TEMP', ''), "flutter/:channel:-:version:-:arch:")
        if os.environ.get('USE_CACHE') == 'false':
            home_dir = os.environ.get('HOME') or str(Path.home())
            cache_path = os.path.join(home_dir, "_flutter/:channel:-:version:-:arch:")
        print(f"Using default cache path {cache_path}")
    else:
        cache_path = args.cache_path

    cache_key = args.cache_key or "flutter-:os:-:channel:-:version:-:arch:-:hash:"

    if channel == 'master' or args.repo_url:
        version_manifest = {
            'channel': channel,
            'version': channel,
            'dart_sdk_arch': arch,
            'hash': channel,
            'sha256': channel
        }
    else:
        if args.test_mode:
            with open(os.path.join(os.path.dirname(__file__), 'test', manifest_json_path)) as file:
                release_manifest = json.load(file)
        else:
            response = requests.get(manifest_url, timeout=15)
            response.raise_for_status()
            release_manifest = response.json()

        version_releases = filter_releases(release_manifest, channel, arch, version)
        version_manifest = version_releases[0] if version_releases else {
            'channel': channel,
            'version': channel,
            'dart_sdk_arch': arch,
            'hash': channel,
            'sha256': channel
        }

    cache_key = expand_key(cache_key, version_manifest, os_name)
    cache_path = transform_path(expand_key(cache_path, version_manifest, os_name), os_name)
    print(f"CACHE-KEY={cache_key}")
    print(f"CACHE-PATH={cache_path}")

    if args.print_only:
        info = {
            'CHANNEL': version_manifest['channel'],
            'VERSION': version_manifest['version'],
            'ARCHITECTURE': version_manifest.get('dart_sdk_arch', 'x64'),
            'CACHE-KEY': cache_key,
            'CACHE-PATH': cache_path
        }
        for key, value in info.items():
            print(f"{key}={value}")
            if not args.test_mode:
                set_github_output(key, value)
    else:
        cache_bin_folder = os.path.join(cache_path, 'bin')
        if not os.path.exists(os.path.join(cache_bin_folder, 'flutter')):
            if channel == 'master' and not args.repo_url:
                args.repo_url = 'https://github.com/flutter/flutter.git'

            if args.repo_url:
                print(f"Cloning Flutter repo from {args.repo_url} (channel: {channel}) to {cache_path}")
                subprocess.run(["git", "clone", "-b", channel, args.repo_url, cache_path], check=True)
            else:
                archive_url = version_manifest['archive']
                print(f"Downloading Flutter archive from {archive_url} to {cache_path}")
                download_and_extract_archive(archive_url, cache_path)

        with open(os.environ['GITHUB_PATH'], 'a') as fp:
            fp.write(f'{cache_bin_folder}\n')

if __name__ == '__main__':
    action()
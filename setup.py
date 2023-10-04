#!/usr/bin/env python

import os
import sys
import subprocess
import json
import requests
import shutil
import zipfile
import tarfile
import argparse

def check_command(command):
    try:
        subprocess.check_output(["command", "-v", command])
        return True
    except subprocess.CalledProcessError:
        return False

def filter_by_channel(data, channel):
    return [release for release in data['releases'] if release['channel'] == 'any' or release['channel'] == channel]

def filter_by_arch(data, arch):
    return [release for release in data if release.get('dart_sdk_arch') == arch or (arch == 'x64' and 'dart_sdk_arch' not in release)]

def filter_by_version(data, version):
    version = version.lstrip('v')
    if version == 'any':
        return [data[0]]
    else:
        return [release for release in data if release['version'] == version or (release['version'].startswith(version + '.') and release['version'] != version)]

def not_found_error(channel, version, arch):
    print(f"Unable to determine Flutter version for channel: {channel} version: {version} architecture: {arch}")
    sys.exit(1)

def transform_path(path, os_name):
    if os_name == 'windows':
        return path.lstrip('/').replace('/', '\\')
    else:
        return path

def download_archive(archive_url, dest_folder):
    archive_name = os.path.basename(archive_url)
    archive_local = os.path.join(os.environ['RUNNER_TEMP'], archive_name)

    response = requests.get(archive_url, timeout=15)
    response.raise_for_status()

    with open(archive_local, 'wb') as file:
        file.write(response.content)

    os.makedirs(dest_folder, exist_ok=True)

    if archive_name.endswith('.zip'):
        with zipfile.ZipFile(archive_local, 'r') as zip_ref:
            zip_ref.extractall(os.environ['RUNNER_TEMP'])
            shutil.rmtree(dest_folder)  # Remove the folder to allow a simple rename
            os.rename(os.path.join(os.environ['RUNNER_TEMP'], 'flutter'), dest_folder)
    else:
        with tarfile.open(archive_local, 'r') as tar_ref:
            tar_ref.extractall(dest_folder)

    os.remove(archive_local)

def expand_key(key, version_manifest, os_name):
    version_channel = version_manifest['channel']
    version_version = version_manifest['version']
    version_arch = version_manifest.get('dart_sdk_arch', 'x64')
    version_hash = version_manifest['hash']
    version_sha256 = version_manifest['sha256']

    key = key.replace(':channel:', version_channel)
    key = key.replace(':version:', version_version)
    key = key.replace(':arch:', version_arch)
    key = key.replace(':hash:', version_hash)
    key = key.replace(':sha256:', version_sha256)
    key = key.replace(':os:', os_name)

    return key

def main():
    os_name = os.environ['RUNNER_OS'].lower()
    manifest_base_url = "https://storage.googleapis.com/flutter_infra_release/releases"
    manifest_json_path = f"releases_{os_name}.json"
    manifest_url = f"{manifest_base_url}/{manifest_json_path}"

    if not check_command('jq'):
        print("jq not found, please install it, https://stedolan.github.io/jq/download/")
        sys.exit(1)

    # Create the argument parser
    parser = argparse.ArgumentParser(description='Flutter Cache Setup')

    # Add the command line arguments
    parser.add_argument('-c', '--cache-path', dest='cache_path', default='',
                        help='Cache path for Flutter installation')
    parser.add_argument('-k', '--cache-key', dest='cache_key', default='',
                        help='Cache key for Flutter installation')
    parser.add_argument('-p', '--print-only', dest='print_only', action='store_true',
                        help='Print only, do not perform installation')
    parser.add_argument('-t', '--test-mode', dest='test_mode', action='store_true',
                        help='Enable test mode')
    parser.add_argument('-a', '--arch', dest='arch', default='',
                        help='Target architecture (e.g., x64)')
    parser.add_argument('-n', '--version', dest='version', default='',
                        help='Flutter version (e.g., v2.5.0)')
    parser.add_argument('-r', '--repo-url', dest='repo_url', default='',
                        help='URL of the Flutter repository')

    # Parse the command line arguments
    args = parser.parse_args()

    # Access the parsed arguments
    cache_path = args.cache_path
    cache_key = args.cache_key
    print_only = args.print_only
    test_mode = args.test_mode
    arch = args.arch.lower()
    version = args.version
    repo_url = args.repo_url

    # Access any additional non-flag arguments (e.g., channel)
    channel = args.channel if args.channel else 'stable'
    version = version if version else 'any'
    arch = arch if arch else 'x64'

    if not cache_path:
        cache_path = f"{os.environ['RUNNER_TEMP']}/flutter/:channel:-:version:-:arch:"
        if os.environ.get('USE_CACHE') == 'false':
            cache_path = f"{os.environ['HOME']}/_flutter/:channel:-:version:-:arch:"
    
    if not cache_key:
        cache_key = "flutter-:os:-:channel:-:version:-:arch:-:hash:"

    if channel == 'master' or repo_url:
        version_manifest = {
            'channel': channel,
            'version': channel,
            'dart_sdk_arch': arch,
            'hash': channel,
            'sha256': channel
        }
    else:
        if test_mode:
            with open(os.path.join(os.path.dirname(__file__), 'test', manifest_json_path)) as file:
                release_manifest = json.load(file)
        else:
            response = requests.get(manifest_url, timeout=15)
            response.raise_for_status()
            release_manifest = response.json()

        channel_releases = filter_by_channel(release_manifest, channel)
        arch_releases = filter_by_arch(channel_releases, arch)
        version_releases = filter_by_version(arch_releases, version)

        if not version_releases:
            not_found_error(channel, version, arch)

        version_manifest = version_releases[0]

    cache_key = expand_key(cache_key, version_manifest, os_name)
    cache_path = expand_key(transform_path(cache_path, os_name), version_manifest, os_name)

    if print_only:
        info_channel = version_manifest['channel']
        info_version = version_manifest['version']
        info_architecture = version_manifest.get('dart_sdk_arch', 'x64')

        if test_mode:
            print(f"CHANNEL={info_channel}")
            print(f"VERSION={info_version}")
            print(f"ARCHITECTURE={info_architecture}")
            print(f"CACHE-KEY={cache_key}")
            print(f"CACHE-PATH={cache_path}")
        else:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as file:
                file.write(f"CHANNEL={info_channel}\n")
                file.write(f"VERSION={info_version}\n")
                file.write(f"ARCHITECTURE={info_architecture}\n")
                file.write(f"CACHE-KEY={cache_key}\n")
                file.write(f"CACHE-PATH={cache_path}\n")

    cache_bin_folder = os.path.join(cache_path, 'bin')
    if not os.path.exists(os.path.join(cache_bin_folder, 'flutter')):
        if channel == 'master' and not repo_url:
            repo_url = 'https://github.com/flutter/flutter.git'

        if repo_url:
            subprocess.run(['git', 'clone', '-b', channel, repo_url, cache_path])
        else:
            archive_url = version_manifest['archive']
            download_archive(archive_url, cache_path)

    with open(os.environ['GITHUB_PATH'], 'a') as file:
        file.write(f"{cache_bin_folder}\n")

if __name__ == '__main__':
    main()

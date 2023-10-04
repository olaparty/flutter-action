#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import shutil
import zipfile
import tarfile
import argparse
import subprocess

try:
    import requests
except ImportError:
    print("The requests module is not installed, attempting to install...")

    # Use subprocess to run the pip install command
    try:
        os.system("pip3 install requests")
    except subprocess.CalledProcessError:
        print("Installation failed. Please install the requests module manually.")
    else:
        print("The requests module has been successfully installed.")

# Attempt to import the requests module again
try:
    import requests
except ImportError:
    print("Failed to import the requests module. Please check the installation.")


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

def set_github_output(name, value):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'{name}={value}', file=fh)

def action():
    os_name = os.environ.get('RUNNER_OS', default='macos').lower()
    manifest_base_url = "https://storage.googleapis.com/flutter_infra_release/releases"
    manifest_json_path = f"releases_{os_name}.json"
    manifest_url = f"{manifest_base_url}/{manifest_json_path}"

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
    parser.add_argument('--channel', dest='channel', default='stable',
                        help='Flutter channel (e.g., stable)')

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
    print(f"!!!! cache path {cache_path}")
    if not cache_path or cache_path == '':
        cache_path = f"{os.environ.get('RUNNER_TEMP', default='')}/flutter/:channel:-:version:-:arch:"
        if os.environ.get('USE_CACHE') == 'false':
            cache_path = f"{os.environ.get('HOME')}/_flutter/:channel:-:version:-:arch:"
            print(f"Using default cache path {cache_path}")
    
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
    print(f"CACHE-KEY={cache_key}")
    print(f"CACHE-PATH={cache_path}")
    
    if print_only:
        info_channel = version_manifest['channel']
        info_version = version_manifest['version']
        info_architecture = version_manifest.get('dart_sdk_arch', 'x64')

        print(f"CHANNEL={info_channel}")
        print(f"VERSION={info_version}")
        print(f"ARCHITECTURE={info_architecture}")
        
        if not test_mode:
            set_github_output('CHANNEL', info_channel)
            set_github_output('VERSION', info_version)
            set_github_output('ARCHITECTURE', info_architecture)
            set_github_output('CACHE-KEY', cache_key)
            set_github_output('CACHE-PATH', cache_path)
        

    cache_bin_folder = os.path.join(cache_path, 'bin')
    if not os.path.exists(os.path.join(cache_bin_folder, 'flutter')):
        if channel == 'master' and not repo_url:
            repo_url = 'https://github.com/flutter/flutter.git'

        if repo_url:
            print(f"clone flutter repo from {repo_url} and channel {channel} to cache path {cache_path}")
            os.system(f"git clone -b {channel} {repo_url} {cache_path}")
            # subprocess.run(['git', 'clone', '-b', channel, repo_url, cache_path])
        else:
            archive_url = version_manifest['archive']
            print(f"download flutter archive from {archive_url} and cache path {cache_path}")
            download_archive(archive_url, cache_path)
            
    # Append the new path to the current GITHUB_PATH 
    with open(os.environ['GITHUB_PATH'], 'a') as fp:
        fp.write(f'{cache_bin_folder}\n')

if __name__ == '__main__':
    action()

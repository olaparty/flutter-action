# flutter-action

Flutter environment for use in GitHub Actions. It works on Linux, Windows, and macOS.

## Usage

Use specific version and channel:

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    flutter-version: '3.7.7'
    channel: 'stable'
- run: flutter --version
```

Use specific repo and branch(channel):

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    flutter-repo: 'https://github.com/olapaty/flutter.git'
    channel: 'main'
- run: flutter --version
```

Use latest release for particular channel:

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    channel: 'stable' # or: 'beta', 'dev' or 'master'
- run: flutter --version
```

Use latest release for particular version and/or channel:

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    flutter-version: '1.22.x'
    channel: 'dev'
- run: flutter --version
```

Use particular version on any channel:

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    flutter-version: '2.x'
    channel: 'any'
- run: flutter --version
```

Build Android APK and app bundle:

```yaml
steps:
- uses: actions/checkout@v3
- uses: actions/setup-java@v2
  with:
    distribution: 'zulu'
    java-version: '11'
- uses: olaparty/flutter-action@v2
  with:
    flutter-version: '3.7.7'
- run: flutter pub get
- run: flutter test
- run: flutter build apk
- run: flutter build appbundle
```

Build for iOS (macOS only):

```yaml
jobs:
  build:
    runs-on: macos-latest
    steps:
    - uses: actions/checkout@v3
    - uses: olaparty/flutter-action@v2
      with:
        channel: 'stable'
        architecture: x64
    - run: flutter pub get
    - run: flutter test
    - run: flutter build ios --release --no-codesign
```

Build for the web:

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    channel: 'stable'
- run: flutter pub get
- run: flutter test
- run: flutter build web
```

Build for Windows:

```yaml
jobs:
 build:
   runs-on: windows-latest
   steps:
     - uses: actions/checkout@v3
     - uses: olaparty/flutter-action@v2
       with:
         channel: 'beta'
     - run: flutter config --enable-windows-desktop
     - run: flutter build windows
```

Build for Linux desktop:

```yaml
jobs:
 build:
   runs-on: ubuntu-latest
   steps:
     - uses: actions/checkout@v3
     - uses: olaparty/flutter-action@v2
       with:
         channel: 'stable'
     - run: |
        sudo apt-get update -y
        sudo apt-get install -y ninja-build libgtk-3-dev
     - run: flutter config --enable-linux-desktop
     - run: flutter build linux
```

Build for macOS desktop:

```yaml
jobs:
 build:
   runs-on: macos-latest
   steps:
     - uses: actions/checkout@v3
     - uses: olaparty/flutter-action@v2
       with:
         channel: 'stable'
         architecture: x64
     - run: flutter config --enable-macos-desktop
     - run: flutter build macos
```

Integration with `actions/cache`:

```yaml
steps:
- uses: actions/checkout@v3
- uses: olaparty/flutter-action@v2
  with:
    channel: 'stable'
    cache: true
    cache-key: 'flutter-:os:-:channel:-:version:-:arch:-:hash:' # optional, change this to force refresh cache
    cache-path: '${{ runner.tool_cache }}/flutter/:channel:-:version:-:arch:' # optional, change this to specify the cache path
    architecture: x64 # optional, x64 or arm64
- run: flutter --version
```

Note: `cache-key` and `cache-path` has support for several dynamic values:

- `:os:`
- `:channel:`
- `:version:`
- `:arch:`
- `:hash:`
- `:sha256:`

Use outputs from `flutter-action`:

```yaml
steps:
- uses: actions/checkout@v3
- id: flutter-action
  uses: olaparty/flutter-action@v2
  with:
    channel: 'stable'
- run: |
    echo CACHE-PATH=${{ steps.flutter-action.outputs.CACHE-PATH }}
    echo CACHE-KEY=${{ steps.flutter-action.outputs.CACHE-KEY }}
    echo CHANNEL=${{ steps.flutter-action.outputs.CHANNEL }}
    echo VERSION=${{ steps.flutter-action.outputs.VERSION }}
    echo ARCHITECTURE=${{ steps.flutter-action.outputs.ARCHITECTURE }}
  shell: bash
```

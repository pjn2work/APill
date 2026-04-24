# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run locally (desktop window + browser at localhost:8550):**
```bash
python main.py
```

**Build Android APK:**
```bash
flet build apk --yes --template /tmp/flet-build-template.zip --skip-flutter-doctor
```

**Install on connected Android device:**
```bash
adb install -r build/apk/APill.apk
```

**If the app shows a blank screen after reinstalling** (Flet caches the Python bundle on device):
```bash
adb shell am force-stop com.pjn2work.apill
adb shell pm clear com.pjn2work.apill
adb install -r build/apk/APill.apk
```

**After changing `requirements.txt`, delete the hash stamp before building:**
```bash
rm -f build/.hash/package
flet build apk --yes --template /tmp/flet-build-template.zip --skip-flutter-doctor
```

**One-time setup for Android SDK (SSL workaround on macOS):**
```bash
yes | ~/Library/Android/sdk/cmdline-tools/latest/bin/sdkmanager --no_https "platforms;android-35"
```

**The build template must be downloaded AND patched (lost on reboot — redo when `/tmp` is cleared):**
```bash
curl -L -o /tmp/flet-build-template.zip "https://github.com/flet-dev/flet/releases/download/v0.84.0/flet-build-template.zip"
cd /tmp && unzip -o flet-build-template.zip -d flet-build-template > /dev/null
sed -i '' 's/sourceCompatibility = JavaVersion.VERSION_17/isCoreLibraryDesugaringEnabled = true\n        sourceCompatibility = JavaVersion.VERSION_17/' \
  "/tmp/flet-build-template/build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts"
sed -i '' 's/^dependencies {}$/dependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")\n}/' \
  "/tmp/flet-build-template/build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts"
cd /tmp/flet-build-template && zip -r /tmp/flet-build-template.zip . > /dev/null && cd -
```

**If flet_audio/flet_android_notifications break after hash stamp deletion (pubspec.yaml path missing):**
```bash
mkdir -p build/flutter-packages/flet_audio
cp -r .venv/lib/python3.14/site-packages/flutter/flet_audio/. build/flutter-packages/flet_audio/
cp -r .venv/lib/python3.14/site-packages/flutter/flet_android_notifications build/flutter-packages/
cd build/flutter && flutter pub get && cd ../..
SERIOUS_PYTHON_SITE_PACKAGES=$(pwd)/build/site-packages flutter build apk --release
cp build/flutter/build/app/outputs/flutter-apk/app-release.apk build/apk/APill.apk
```

## Architecture

The entire app lives in `main.py` (~1100 lines), structured in clearly marked sections:

### Data Layer
- **`PillManager`** — reads/writes `pills_data.json`. Pills are stored in `agenda` keyed by UUID; the `id` field is injected at read time (`get_all()`), not persisted.
- **Pill schema:** `name`, `description`, `category`, `start_date` (ISO date), `start_time` (HH:MM), `times_per_day`, `duration_days`, `active`, `last_alarm_time`, `snoozed_until`, `completed_takes`.
- **`calculate_expected_takes(pill)`** — derives how many doses should have been taken by now from `start_date`/`start_time`, used on every load to auto-disable completed pills.

### Schedule Logic
- **`get_today_schedule(pill)`** — returns today's dose times as `datetime` objects. Doses are evenly spaced from `start_time` with interval `= 1440 / times_per_day` minutes, wrapping at midnight.
- **`get_next_alarm(pill)`** — returns the next upcoming dose datetime (tomorrow's first dose if all today's have passed).

### Alarm Loop
- **`alarm_loop(page, manager)`** — async background task, runs every `ALARM_CHECK_INTERVAL` (10s). Fires `ft.AlertDialog` alarm popups for due pills. Handles snooze expiry. Started via `asyncio.create_task()` in `main()`.
- On Android/iOS, plays audio via `flet_audio` (`fta.Audio`) added to `page.services`.

### UI / Navigation
Navigation uses **manual `page.views` stack** (not `page.go()`/routing), with `on_route_change` as a fallback handler.

- **`on_view_pop`** handles the Android system back button: calls `page.go("/")` which triggers `on_route_change` to rebuild the dashboard. All secondary views push only **1 view** (themselves) to keep back-button behavior consistent — do not push 2 views (e.g. dashboard + timeline), as Flet auto-pops without firing `on_view_pop` when there are 2+ views.
- **`refresh_views(page)`** — rebuilds whichever view is currently on top after data changes.

**Views:**
| View | Route | Created by |
|------|-------|------------|
| Dashboard (active pills list) | `/` | `create_dashboard_view()` |
| Timeline (full-day schedule) | `/timeline` | `create_timeline_view()` |
| Categories (edit labels) | `/categories` | `create_categories_view()` |
| Edit/Add pill | modal `AlertDialog` | `show_pill_dialog()` |

### Key Constants
```python
ALARM_CHECK_INTERVAL = 10   # seconds between alarm checks
TIMELINE_SCALE = 1.0        # pixels per minute in the timeline view
CATEGORIES = {              # fixed keys; only display names are user-editable
    "primary", "secondary", "tertiary", "quaternary"
}
```

### Build Notes
- Output APK: `build/apk/APill.apk` (~81MB). The `build/` directory is gitignored.
- Flet 0.84.0, Flutter 3.41.7, Java 17 (OpenJDK via Homebrew), Python 3.14 venv.
- Python 3.11+ on macOS has SSL issues with external HTTPS — use `curl` for any manual downloads.
- `flet_audio` plugin: after a working build, subsequent builds may break if `build/flutter-packages/flet_audio` is missing from `pubspec.yaml`. Fix: copy from `.venv` and run `flutter pub get` in `build/flutter/`.
- **Never add Flet extension packages to `exclude` in `[tool.flet.app]`** — doing so strips the Python module from the bundle, causing `ModuleNotFoundError` at runtime. Only exclude data files (e.g. `pills_data.json`).
- `page.window.full_screen` is desktop-only in Flet 0.84 — has no effect on Android/iOS.

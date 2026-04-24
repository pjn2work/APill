# APill - Medication Reminder App

A simple medication reminder and schedule tracking application built with Flet.

## Features

- ⏰ Multiple daily alarms for each medication
- 📅 Timeline view showing full day schedule
- 🏷️ Customizable categories with color coding
- ✅ Track completed and remaining doses
- 🔔 Snooze functionality
- 🔄 Auto-disable when all doses are complete
- 📊 Visual progress tracking

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

## Installation & Local Testing

1. **Install Dependencies**

```bash
pip install flet
```

2. **Run Locally**

```bash
python main.py
```

The app will open in a window. You can also access it at `http://127.0.0.1:8550` in your browser.

## Building for Mobile

### Android (APK)

#### Step 1 — One-time environment setup (macOS)

Install the required Android SDK platform. The bundled `sdkmanager` needs `--no_https` to reach Google's servers:

```bash
yes | ~/Library/Android/sdk/cmdline-tools/latest/bin/sdkmanager --no_https "platforms;android-35"
```

#### Step 2 — Download and patch the Flet build template

Python 3.11+ on macOS has SSL issues downloading from GitHub. The template file lives in `/tmp` and is lost on reboot, so re-run this whenever it's missing.

Download:

```bash
curl -L -o /tmp/flet-build-template.zip \
  "https://github.com/flet-dev/flet/releases/download/v0.84.0/flet-build-template.zip"
```

Patch it to enable Java core library desugaring (required by `flet-android-notifications`):

```bash
cd /tmp && unzip -o flet-build-template.zip -d flet-build-template > /dev/null

# Enable desugaring in compileOptions
sed -i '' 's/sourceCompatibility = JavaVersion.VERSION_17/isCoreLibraryDesugaringEnabled = true\n        sourceCompatibility = JavaVersion.VERSION_17/' \
  "/tmp/flet-build-template/build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts"

# Add desugar library to dependencies
sed -i '' 's/^dependencies {}$/dependencies {\n    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.4")\n}/' \
  "/tmp/flet-build-template/build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts"

cd /tmp/flet-build-template && zip -r /tmp/flet-build-template.zip . > /dev/null
cd -
```

#### Step 3 — Delete the package hash stamp

Flet has a caching bug: adding or changing packages in `requirements.txt` does not invalidate the cached site-packages. Always delete the hash stamp before building to ensure new packages are bundled:

```bash
rm -f build/.hash/package
```

#### Step 4 — Build the APK

```bash
flet build apk --yes --template /tmp/flet-build-template.zip --skip-flutter-doctor
```

The APK will be generated at `build/apk/APill.apk` (~81 MB).

> **If pubspec.yaml is missing flet_audio after the build**, run:
> ```bash
> cd build/flutter && flutter pub get
> ```

#### Step 5 — Install on device via ADB

1. Enable **USB debugging** in Developer Options on your phone
2. Connect the phone via USB and accept the trust prompt
3. Verify the device is detected:

```bash
adb devices
```

4. Install (use `-r` to reinstall without uninstalling first):

```bash
adb install -r build/apk/APill.apk
```

> **If the app shows a blank screen after reinstalling**, Flet caches the Python bundle on the device and may not clear it on `adb install -r`. Force-clear the cache before reinstalling:
> ```bash
> adb shell am force-stop com.pjn2work.apill
> adb shell pm clear com.pjn2work.apill
> adb install -r build/apk/APill.apk
> ```

### iOS (IPA)

Building for iOS requires a Mac with Xcode installed.

```bash
flet build ipa
```

The IPA will be generated at `build/ipa/`. You'll need to sign it with your Apple Developer account to install on a physical device.

## ⚠️ Important Android Configuration

Since the alarm checker runs in the background, Android may suspend the app. To ensure alarms work reliably:

### 1. Disable Battery Optimization
- Go to **Settings → Apps → APill → Battery**
- Set to **Unrestricted** or **No restrictions**

### 2. Allow Background Activity
- **Settings → Apps → APill → Mobile data & Wi-Fi**
- Enable **Background data**

### 3. Autostart Permission (varies by manufacturer)
- **Xiaomi/MIUI**: Security → Autostart → Enable for APill
- **Huawei**: App Launch → Enable for APill
- **Samsung**: Device care → Battery → App power management → Add to Never sleeping apps
- **OnePlus**: Battery → Battery optimization → Don't optimize APill

### 4. Notification Permissions
- Make sure notifications are enabled for the app
- **Settings → Apps → APill → Notifications** → Enable

## Data Storage

All medication data is stored locally in `pills_data.json` in the app directory. This includes:
- Medication schedules
- Category names
- Completion tracking
- Start dates and alarm states

## Development

The app consists of:
- `main.py` - Main application with UI and logic
- `pills_data.json` - Data storage file

### Key Components
- **PillManager** - Handles data persistence and CRUD operations
- **Alarm Loop** - Background task checking for due alarms
- **Dashboard View** - Main screen with active/disabled pills
- **Timeline View** - Full day schedule visualization
- **Categories View** - Manage category names

## Troubleshooting

**Alarms not triggering?**
- Check battery optimization settings (see above)
- Verify the app is not being killed by system task manager
- Make sure notifications are enabled

**Can't scroll in Categories screen?**
- This has been fixed in the latest version
- Update to the newest code

**Pills auto-disabling?**
- Pills automatically disable when all doses are completed
- Toggle them back on to restart with today's date

## License

Apache License 2.0 - See the [LICENSE](LICENSE) file for details.

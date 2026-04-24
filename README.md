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

#### One-time setup

The build requires Android SDK `platforms;android-35`. The bundled `sdkmanager` needs `--no_https` to reach Google's servers. Run this once:

```bash
yes | ~/Library/Android/sdk/cmdline-tools/latest/bin/sdkmanager --no_https "platforms;android-35"
```

Python 3.11+ on macOS may have SSL issues downloading the Flet build template from GitHub. Download it manually once with curl:

```bash
curl -L -o /tmp/flet-build-template.zip \
  "https://github.com/flet-dev/flet/releases/download/v0.84.0/flet-build-template.zip"
```

#### Build the APK

```bash
flet build apk --yes --template /tmp/flet-build-template.zip
```

The APK will be generated at `build/apk/APill.apk`.

#### Install on Device via ADB

1. Enable **USB debugging** in Developer Options on your phone
2. Connect the phone via USB and accept the trust prompt on the phone
3. Verify the device is detected:

```bash
adb devices
```

3. Install:

```bash
adb install build/apk/APill.apk
```

To reinstall after a new build (without uninstalling first):

```bash
adb install -r build/apk/APill.apk
```

### iOS (IPA)

Building for iOS requires a Mac with Xcode installed.

```bash
flet build ipa
```

The IPA will be generated at `build/ipa/`. You'll need to sign it with your Apple Developer account to install on a physical device.

## ⚠️ Important Android Configuration

Since the alarm checker runs in the background, Android may suspend the app. To ensure alarms work reliably:

### 1. Disable Battery Optimization
- Go to **Settings → Apps → QwenPill → Battery**
- Set to **Unrestricted** or **No restrictions**

### 2. Allow Background Activity
- **Settings → Apps → QwenPill → Mobile data & Wi-Fi**
- Enable **Background data**

### 3. Autostart Permission (varies by manufacturer)
- **Xiaomi/MIUI**: Security → Autostart → Enable for QwenPill
- **Huawei**: App Launch → Enable for QwenPill
- **Samsung**: Device care → Battery → App power management → Add to Never sleeping apps
- **OnePlus**: Battery → Battery optimization → Don't optimize QwenPill

### 4. Notification Permissions
- Make sure notifications are enabled for the app
- **Settings → Apps → QwenPill → Notifications** → Enable

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

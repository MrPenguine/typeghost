# TypeGhost Android Remote Sender

This folder contains the Python/Kivy mobile app that connects over LAN/Wi-Fi to TypeGhost on your PC.

---

## 1. Quick Local Testing on PC (Phone Preview)

You can run and test the mobile app directly on your computer before packaging to Android:

```bash
cd android_sender
pip install kivy
python main.py
```

It opens in a phone-sized `380x680` preview window and auto-discovers TypeGhost running in **Receiver** mode.

---

## 2. Testing with your Android Phone directly over Wi-Fi

### Method A: Run with Pydroid 3 (Instant, No build needed)
1. Install **Pydroid 3** (or QPython) from the Google Play Store on your phone.
2. In Pydroid 3, go to **Pip** and install `kivy`.
3. Copy `main.py` to your phone and press **Run (Play button)**.
4. As long as your phone and PC are on the same Wi-Fi network, it will auto-discover the PC and connect!

---

### Method B: Build Standalone `.apk` with Buildozer
To compile into a standalone `.apk` installable on any Android device:

```bash
pip install buildozer
buildozer init
buildozer -v android debug
```
The output `.apk` will be in `bin/TypeGhostRemote-0.1-arm64-v8a_armeabi-v7a-debug.apk`.

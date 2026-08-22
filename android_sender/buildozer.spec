[app]
title = TypeGhost Remote
package.name = typeghostremote
package.domain = org.typeghost
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ico
version = 1.0.0
requirements = python3,kivy

orientation = portrait
fullscreen = 0

# Android permissions needed for LAN/Wi-Fi auto-discovery
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_MULTICAST_STATE

android.api = 34
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1

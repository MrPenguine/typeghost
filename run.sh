#!/usr/bin/env bash
# Runner script for TypeGhost on macOS / Linux
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Ensure virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment in .venv..."
    python3 -m venv .venv
    echo "Installing required dependencies..."
    .venv/bin/pip install -r requirements.txt
fi

# Pre-check macOS Accessibility permissions
if [[ "$OSTYPE" == "darwin"* ]]; then
    .venv/bin/python3 -c "
import platform
if platform.system() == 'Darwin':
    try:
        import ApplicationServices
        if not ApplicationServices.AXIsProcessTrusted():
            print('\n' + '='*65)
            print('⚠️  macOS PERMISSION NOTICE')
            print('='*65)
            print('macOS requires Accessibility permission to send keystrokes to')
            print('other applications.')
            print('\nPrompting macOS permission dialog now...')
            ApplicationServices.AXIsProcessTrustedWithOptions({ApplicationServices.kAXTrustedCheckOptionPrompt: True})
            print('If keystrokes do not appear in your target app:')
            print('  1. Open System Settings -> Privacy & Security -> Accessibility')
            print('  2. Enable your Terminal (e.g. Terminal, iTerm, or IDE)')
            print('  3. Restart your Terminal and re-run ./run.sh')
            print('='*65 + '\n')
    except Exception:
        pass
"
fi

# Launch TypeGhost
echo "Launching TypeGhost..."
exec .venv/bin/python3 typeghost.py "$@"

#!/usr/bin/env bash
# Build dist/focus-agent_<version>.deb from this repo.  Usage: packaging/build-deb.sh [version]
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-0.1.0}"
P="dist/focus-agent_${VERSION}"
rm -rf "$P"; mkdir -p "$P"/{DEBIAN,usr/bin,usr/lib/systemd/user,usr/lib/focus-agent,etc/focus-agent}
install -m 755 packaging/focus-agent "$P/usr/bin/focus-agent"
install -m 644 packaging/focus-agent.service "$P/usr/lib/systemd/user/focus-agent.service"
cp -r core modes main.py requirements.txt "$P/usr/lib/focus-agent/"
find "$P" -name __pycache__ -prune -exec rm -rf {} +
install -m 644 config.json "$P/etc/focus-agent/config.json"
echo /etc/focus-agent/config.json > "$P/DEBIAN/conffiles"
cat > "$P/DEBIAN/control" <<EOC
Package: focus-agent
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.9), python3-venv, python3-psutil
Recommends: google-chrome-stable
Maintainer: Sadhana Sapkota <sadhana.develops@gmail.com>
Description: Scheduled study-lockdown focus agent
 Runs scheduled study modes in an allow-listed browser and kills
 distracting processes during active slots. Runs as a systemd user service.
EOC
cat > "$P/DEBIAN/postinst" <<'EOC'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
  python3 -m venv --system-site-packages /usr/lib/focus-agent/venv
  /usr/lib/focus-agent/venv/bin/pip install --quiet "playwright==1.44.0"
fi
exit 0
EOC
cat > "$P/DEBIAN/postrm" <<'EOC'
#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = purge ]; then rm -rf /usr/lib/focus-agent/venv; fi
exit 0
EOC
chmod 755 "$P/DEBIAN/postinst" "$P/DEBIAN/postrm"
find "$P" -type d -exec chmod 755 {} +
dpkg-deb --root-owner-group --build "$P"

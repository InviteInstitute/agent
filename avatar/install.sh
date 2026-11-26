#!/usr/bin/env bash
# Install a Unity WebGL build of the tutor, whatever Build Settings named it, where the avatar
# page loads it (avatar/build/), and swap it in whole so the live page never sees half a build:
#
#   avatar/install.sh ~/Builds/WebGL
#
# Takes uncompressed builds, and compressed ones with Decompression Fallback on (.unityweb),
# which plain nginx serves as they are.
set -euo pipefail

SRC=${1:?usage: avatar/install.sh <unity-webgl-build-dir>}
NAME=avatar
DEST="$(cd "$(dirname "$0")" && pwd)/build"

loaders=("$SRC"/Build/*.loader.js)
[ -f "${loaders[0]}" ] || { echo "No Build/*.loader.js in $SRC" >&2; exit 1; }
[ "${#loaders[@]}" -eq 1 ] || { echo "More than one loader in $SRC/Build" >&2; exit 1; }
base=$(basename "${loaders[0]}" .loader.js)

rm -rf "$DEST.new"
mkdir -p "$DEST.new/Build"
cp "${loaders[0]}" "$DEST.new/Build/$NAME.loader.js"
for part in data framework.js wasm; do
  if [ -f "$SRC/Build/$base.$part" ]; then
    cp "$SRC/Build/$base.$part" "$DEST.new/Build/$NAME.$part"
  elif [ -f "$SRC/Build/$base.$part.unityweb" ]; then
    cp "$SRC/Build/$base.$part.unityweb" "$DEST.new/Build/$NAME.$part"
  else
    echo "Missing $base.$part in $SRC/Build. A .br or .gz build needs Decompression Fallback" \
      "on (Player Settings > Publishing Settings)." >&2
    rm -rf "$DEST.new"
    exit 1
  fi
done
if [ -d "$SRC/StreamingAssets" ]; then
  cp -r "$SRC/StreamingAssets" "$DEST.new/StreamingAssets"
fi
# Every build file is loaded as ?v=<version>, so a new build has URLs no cache has seen.
version=$(cat "$DEST.new"/Build/* | sha256sum | cut -c1-12)
printf '{"version": "%s", "source": "%s"}\n' "$version" "$base" > "$DEST.new/build.json"
chmod -R a+rX "$DEST.new"

rm -rf "$DEST.old"
[ -d "$DEST" ] && mv "$DEST" "$DEST.old"
mv "$DEST.new" "$DEST"
rm -rf "$DEST.old"
echo "Installed $base (version $version) into $DEST"

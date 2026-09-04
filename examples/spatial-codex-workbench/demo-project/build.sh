#!/data/data/com.termux/files/usr/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VERSION_FILE="$ROOT_DIR/version.properties"
MANIFEST_TEMPLATE="$ROOT_DIR/AndroidManifest.xml.template"
SOURCE_FILE="$ROOT_DIR/src/io/github/mesmerprism/questtermuxlab/codexdemo/MainActivity.java"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/build/manual}"
ANDROID_JAR="${ANDROID_JAR:-$HOME/quest-lab/android-sdk/platforms/android-33/android.jar}"
KEYSTORE_PATH="${KEYSTORE_PATH:-$HOME/.local/share/spatial-codex-workbench/debug.keystore}"
MIN_SDK="${MIN_SDK:-29}"
TARGET_SDK="${TARGET_SDK:-33}"
APP_ID="io.github.mesmerprism.questtermuxlab.codexdemo"
ACTIVITY=".MainActivity"

if [ -e "$OUT_DIR" ]; then
  printf 'OUT_DIR already exists; choose a fresh build directory: %s\n' "$OUT_DIR" >&2
  exit 2
fi

for input in "$VERSION_FILE" "$MANIFEST_TEMPLATE" "$SOURCE_FILE" "$ANDROID_JAR"; do
  if [ ! -f "$input" ]; then
    printf 'missing required build input: %s\n' "$input" >&2
    exit 2
  fi
done

for tool in aapt2 javac d8 jar apksigner keytool sed sha256sum tr; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'missing required tool: %s\n' "$tool" >&2
    exit 2
  fi
done

# Android asset packaging preserves the checkout's line endings. Normalize the
# parsed values so a CRLF checkout remains buildable in Termux.
VERSION_CODE="$(sed -n 's/^VERSION_CODE=//p' "$VERSION_FILE" | tr -d '\r')"
VERSION_NAME="$(sed -n 's/^VERSION_NAME=//p' "$VERSION_FILE" | tr -d '\r')"

case "$VERSION_CODE" in
  ''|*[!0-9]*|0) printf 'VERSION_CODE must be a positive integer\n' >&2; exit 2 ;;
esac
case "$VERSION_NAME" in
  ''|*[!0-9A-Za-z.+-]*) printf 'VERSION_NAME contains unsupported characters\n' >&2; exit 2 ;;
esac

MANIFEST="$OUT_DIR/AndroidManifest.xml"
GEN_DIR="$OUT_DIR/gen"
CLASSES_DIR="$OUT_DIR/classes"
DEX_DIR="$OUT_DIR/dex"
UNSIGNED_APK="$OUT_DIR/demo-unsigned.apk"
DEXED_APK="$OUT_DIR/demo-dexed.apk"
ALIGNED_APK="$OUT_DIR/demo-aligned.apk"
SIGNED_APK="$OUT_DIR/spatial-codex-demo-v$VERSION_NAME.apk"

mkdir -p "$GEN_DIR" "$CLASSES_DIR" "$DEX_DIR" "$(dirname -- "$KEYSTORE_PATH")"
sed \
  -e "s/@VERSION_CODE@/$VERSION_CODE/g" \
  -e "s/@VERSION_NAME@/$VERSION_NAME/g" \
  "$MANIFEST_TEMPLATE" > "$MANIFEST"

aapt2 link \
  --manifest "$MANIFEST" \
  -I "$ANDROID_JAR" \
  --java "$GEN_DIR" \
  --min-sdk-version "$MIN_SDK" \
  --target-sdk-version "$TARGET_SDK" \
  -o "$UNSIGNED_APK"

javac \
  --release 8 \
  -encoding UTF-8 \
  -classpath "$ANDROID_JAR:$GEN_DIR" \
  -d "$CLASSES_DIR" \
  "$SOURCE_FILE" \
  $(find "$GEN_DIR" -name '*.java' -print)

d8 \
  --min-api "$MIN_SDK" \
  --output "$DEX_DIR" \
  $(find "$CLASSES_DIR" -name '*.class' -print)

cp "$UNSIGNED_APK" "$DEXED_APK"
jar uf "$DEXED_APK" -C "$DEX_DIR" classes.dex
if command -v zipalign >/dev/null 2>&1; then
  zipalign -f 4 "$DEXED_APK" "$ALIGNED_APK"
else
  # Termux's public Android build-tool packages do not currently ship
  # zipalign. Keep the optional host-style optimization separate from the
  # correctness gates below: apksigner verification and live package-manager
  # installation remain mandatory.
  cp "$DEXED_APK" "$ALIGNED_APK"
fi

if [ ! -f "$KEYSTORE_PATH" ]; then
  printf 'build_step=generate_signing_key\n' >&2
  keytool \
    -genkeypair \
    -keystore "$KEYSTORE_PATH" \
    -storepass android \
    -keypass android \
    -alias androiddebugkey \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname 'CN=Spatial Codex Workbench,O=Quest Termux Lab,C=US'
fi

printf 'build_step=sign_apk\n' >&2
apksigner sign \
  --ks "$KEYSTORE_PATH" \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$SIGNED_APK" \
  "$ALIGNED_APK"
printf 'build_step=verify_signature\n' >&2
apksigner verify --verbose --print-certs "$SIGNED_APK" > "$OUT_DIR/signature.txt"

APK_SHA256="$(sha256sum "$SIGNED_APK" | sed 's/[[:space:]].*$//')"
APK_BYTES="$(wc -c < "$SIGNED_APK" | tr -d '[:space:]')"
SIGNING_SHA256="$(sed -n 's/^.*certificate SHA-256 digest:[[:space:]]*//p' "$OUT_DIR/signature.txt" | sed -n '1p' | tr -d '[:space:]' | tr 'A-F' 'a-f')"
case "$SIGNING_SHA256" in
  *[!0-9a-f]*|'') printf 'build_step=read_signature_digest failed: unable to read signing certificate SHA-256\n' >&2; exit 2 ;;
esac
cat > "$OUT_DIR/artifact-metadata.json" <<EOF
{
  "schema": "quest-termux-lab.spatial-codex-workbench-artifact.v1",
  "package": "$APP_ID",
  "activity": "$ACTIVITY",
  "version_code": $VERSION_CODE,
  "version_name": "$VERSION_NAME",
  "apk_name": "$(basename -- "$SIGNED_APK")",
  "apk_sha256": "$APK_SHA256",
  "apk_bytes": $APK_BYTES,
  "signing_certificate_sha256": "$SIGNING_SHA256",
  "signing": "debug-external"
}
EOF

printf '%s\n' "$SIGNED_APK"

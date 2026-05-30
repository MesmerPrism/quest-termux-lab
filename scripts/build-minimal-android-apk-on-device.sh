#!/data/data/com.termux/files/usr/bin/sh
set -eu

# Build a tiny Android Activity APK from a Termux shell using source-only
# inputs. The output directory is local build output and must not be committed.

APP_ID="${APP_ID:-org.questtermuxlab.ondevice.smoke}"
APP_LABEL="${APP_LABEL:-Quest Termux Lab Smoke}"
PANEL_TEXT="${PANEL_TEXT:-Quest Termux Lab on-device APK}"
MIN_SDK="${MIN_SDK:-29}"
TARGET_SDK="${TARGET_SDK:-33}"
ANDROID_JAR="${ANDROID_JAR:-$HOME/quest-lab/android-sdk/platforms/android-33/android.jar}"
OUT_DIR="${OUT_DIR:-$PWD/build/on-device-smoke-apk}"
INSTALL="${INSTALL:-0}"
LAUNCH="${LAUNCH:-0}"
ADB_TARGET="${ADB_TARGET:-127.0.0.1:5555}"

case "$APP_ID" in
  *[!abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._]*|.*|*..*|*.)
    echo "unsupported APP_ID=$APP_ID" >&2
    exit 2
    ;;
esac

if [ ! -f "$ANDROID_JAR" ]; then
  echo "ANDROID_JAR is required and must point to an Android SDK platform android.jar" >&2
  echo "Do not commit android.jar to this repository." >&2
  exit 2
fi

for tool in aapt2 javac d8 jar zipalign apksigner keytool; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "missing required tool: $tool" >&2
    exit 2
  fi
done

pkg_path="$(printf '%s' "$APP_ID" | tr . /)"
src_dir="$OUT_DIR/src/$pkg_path"
gen_dir="$OUT_DIR/gen"
classes_dir="$OUT_DIR/classes"
dex_dir="$OUT_DIR/dex"
mkdir -p "$src_dir" "$gen_dir" "$classes_dir" "$dex_dir"

manifest="$OUT_DIR/AndroidManifest.xml"
cat > "$manifest" <<EOF
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="$APP_ID">
    <application android:theme="@android:style/Theme.Material.Light.NoActionBar" android:label="$APP_LABEL">
        <activity android:name=".MainActivity" android:exported="true" android:screenOrientation="landscape">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
EOF

java_file="$src_dir/MainActivity.java"
cat > "$java_file" <<EOF
package $APP_ID;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("$PANEL_TEXT");
        view.setTextColor(Color.rgb(24, 24, 24));
        view.setTextSize(28.0f);
        view.setGravity(Gravity.CENTER);
        view.setBackgroundColor(Color.WHITE);
        setContentView(view);
    }
}
EOF

unsigned_apk="$OUT_DIR/smoke-unsigned.apk"
dexed_apk="$OUT_DIR/smoke-dexed.apk"
aligned_apk="$OUT_DIR/smoke-aligned.apk"
signed_apk="$OUT_DIR/smoke-debug.apk"
keystore="$OUT_DIR/debug.keystore"

rm -f "$unsigned_apk" "$dexed_apk" "$aligned_apk" "$signed_apk"
find "$classes_dir" -type f -delete
find "$dex_dir" -type f -delete

aapt2 link \
  --manifest "$manifest" \
  -I "$ANDROID_JAR" \
  --java "$gen_dir" \
  --min-sdk-version "$MIN_SDK" \
  --target-sdk-version "$TARGET_SDK" \
  -o "$unsigned_apk"

javac \
  --release 8 \
  -encoding UTF-8 \
  -classpath "$ANDROID_JAR:$gen_dir" \
  -d "$classes_dir" \
  "$java_file" \
  $(find "$gen_dir" -name '*.java' -print)

d8 \
  --min-api "$MIN_SDK" \
  --output "$dex_dir" \
  $(find "$classes_dir" -name '*.class' -print)

cp "$unsigned_apk" "$dexed_apk"
jar uf "$dexed_apk" -C "$dex_dir" classes.dex
zipalign -f 4 "$dexed_apk" "$aligned_apk"

if [ ! -f "$keystore" ]; then
  keytool \
    -genkeypair \
    -keystore "$keystore" \
    -storepass android \
    -keypass android \
    -alias androiddebugkey \
    -keyalg RSA \
    -keysize 2048 \
    -validity 10000 \
    -dname 'CN=Android Debug,O=Quest Termux Lab,C=US'
fi

apksigner sign \
  --ks "$keystore" \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$signed_apk" \
  "$aligned_apk"

apksigner verify --verbose "$signed_apk"

if [ "$INSTALL" = "1" ] || [ "$LAUNCH" = "1" ]; then
  adb connect "$ADB_TARGET" >/dev/null 2>&1 || true
fi

if [ "$INSTALL" = "1" ]; then
  adb -s "$ADB_TARGET" install -r "$signed_apk"
fi

if [ "$LAUNCH" = "1" ]; then
  adb -s "$ADB_TARGET" shell am start -W -n "$APP_ID/.MainActivity"
fi

printf '%s\n' "$signed_apk"

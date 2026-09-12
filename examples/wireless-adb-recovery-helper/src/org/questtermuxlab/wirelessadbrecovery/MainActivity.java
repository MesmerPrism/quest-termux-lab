package org.questtermuxlab.wirelessadbrecovery;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.text.InputFilter;
import android.text.InputType;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class MainActivity extends Activity {
    public static final String ACTION_RUN_AP_FREE_PULSE =
            "org.questtermuxlab.wirelessadbrecovery.action.RUN_AP_FREE_PULSE";
    public static final String ACTION_STOP_AP_FREE_PULSE =
            "org.questtermuxlab.wirelessadbrecovery.action.STOP_AP_FREE_PULSE";
    public static final String ACTION_RUN_POSITIVE_CONTROL =
            "org.questtermuxlab.wirelessadbrecovery.action.RUN_POSITIVE_CONTROL";
    public static final String ACTION_START_LOCAL_ONLY_HOTSPOT =
            "org.questtermuxlab.wirelessadbrecovery.action.START_LOCAL_ONLY_HOTSPOT";
    public static final String ACTION_STOP_SELF_HOSTED_TOPOLOGY =
            "org.questtermuxlab.wirelessadbrecovery.action.STOP_SELF_HOSTED_TOPOLOGY";
    private static final int REQUEST_RUNTIME_PERMISSIONS = 1001;
    private static final String RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND";

    private TextView status;
    private EditText pairingCode;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildLayout());
        handleLaunchAction(getIntent());
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshStatus();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleLaunchAction(intent);
        refreshStatus();
    }

    private View buildLayout() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        int pad = dp(18);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("Wireless ADB Recovery");
        title.setTextSize(24);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, fullWidth());

        TextView explanation = new TextView(this);
        explanation.setText(
                "Restores TLS Wireless Debugging through Termux. Standard Android devices may "
                        + "pair by code; Horizon OS may instead use Meta's visible approval prompt.");
        explanation.setTextSize(15);
        explanation.setPadding(0, dp(10), 0, dp(10));
        root.addView(explanation, fullWidth());

        status = new TextView(this);
        status.setTextSize(14);
        status.setPadding(0, dp(8), 0, dp(14));
        root.addView(status, fullWidth());

        pairingCode = new EditText(this);
        pairingCode.setHint("6-digit system pairing code");
        pairingCode.setSingleLine(true);
        pairingCode.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        pairingCode.setFilters(new InputFilter[]{new InputFilter.LengthFilter(6)});
        root.addView(pairingCode, fullWidth());

        root.addView(button("Open Wireless Debugging Settings", v -> openWirelessDebuggingSettings()), fullWidth());
        root.addView(button("Pair Termux with Displayed Code", v -> pairTermux()), fullWidth());

        root.addView(button("Enable Boot Recovery Attempt + Restore", v -> enableAndRestore()), fullWidth());
        root.addView(button("Restore Now", v -> restoreNow()), fullWidth());
        root.addView(button("Run 15s AP-Free Wireless Debugging Pulse", v -> runApFreePulse()), fullWidth());
        root.addView(button("Stop AP-Free Wireless Debugging Pulse", v -> stopApFreePulse()), fullWidth());
        root.addView(button("Start Peerless Wi-Fi Direct Probe", v -> startTopologyProbe(
                TopologyProbeService.ACTION_START_WIFI_DIRECT)), fullWidth());
        root.addView(button("Start Local-Only Hotspot Probe", v -> startTopologyProbe(
                TopologyProbeService.ACTION_START_LOCAL_ONLY_HOTSPOT)), fullWidth());
        root.addView(button("Stop Self-Hosted Probe", v -> stopTopologyProbe()), fullWidth());
        root.addView(button("Disable Boot Recovery Attempt", v -> disableAutomaticRecovery()), fullWidth());
        root.addView(button("Disable Wireless Debugging", v -> disableWirelessDebugging()), fullWidth());
        scroll.addView(root);
        return scroll;
    }

    private Button button(String label, View.OnClickListener listener) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setOnClickListener(listener);
        return button;
    }

    private LinearLayout.LayoutParams fullWidth() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, dp(4), 0, dp(4));
        return params;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void enableAndRestore() {
        if (!hasRequiredRuntimePermissions()) {
            requestRuntimePermissions();
            return;
        }
        RecoveryService.start(this, RecoveryService.ACTION_ARM_AND_RESTORE);
        status.setText("Recovery requested. Keep the notification visible while Termux reconnects.");
    }

    private void restoreNow() {
        if (!hasRequiredRuntimePermissions()) {
            requestRuntimePermissions();
            return;
        }
        RecoveryService.start(this, RecoveryService.ACTION_RESTORE_NOW);
        status.setText("One-time recovery requested.");
    }

    private void runApFreePulse() {
        if (!hasRequiredRuntimePermissions()) {
            requestRuntimePermissions();
            return;
        }
        RecoveryService.start(this, RecoveryService.ACTION_AP_FREE_PULSE);
        status.setText("Bounded Wireless Debugging pulse requested. Protected consent remains manual.");
    }

    private void stopApFreePulse() {
        RecoveryService.start(this, RecoveryService.ACTION_STOP_AP_FREE_PULSE);
        status.setText("Pulse stop requested; its prior Wireless Debugging setting will be restored.");
    }

    private void handleLaunchAction(Intent intent) {
        if (intent == null) {
            return;
        }
        if (ACTION_RUN_AP_FREE_PULSE.equals(intent.getAction())) {
            runApFreePulse();
        } else if (ACTION_STOP_AP_FREE_PULSE.equals(intent.getAction())) {
            stopApFreePulse();
        } else if (ACTION_RUN_POSITIVE_CONTROL.equals(intent.getAction())) {
            RecoveryService.start(this, RecoveryService.ACTION_POSITIVE_CONTROL);
        } else if (ACTION_START_LOCAL_ONLY_HOTSPOT.equals(intent.getAction())) {
            startTopologyProbe(TopologyProbeService.ACTION_START_LOCAL_ONLY_HOTSPOT);
        } else if (ACTION_STOP_SELF_HOSTED_TOPOLOGY.equals(intent.getAction())) {
            stopTopologyProbe();
        }
    }

    private void startTopologyProbe(String action) {
        if (!hasTopologyRuntimePermissions()) {
            requestRuntimePermissions();
            return;
        }
        TopologyProbeService.start(this, action);
        status.setText("Self-hosted topology probe requested. It will stop automatically after four minutes.");
    }

    private void stopTopologyProbe() {
        TopologyProbeService.start(this, TopologyProbeService.ACTION_STOP);
        status.setText("Self-hosted topology cleanup requested.");
    }

    private void openWirelessDebuggingSettings() {
        try {
            startActivity(new Intent("android.settings.WIRELESS_DEBUGGING_SETTINGS"));
        } catch (ActivityNotFoundException unavailable) {
            status.setText(
                    "This Horizon OS build does not expose Android's pairing-code settings. "
                            + "Use Meta's visible debugging approval when requested.");
        }
    }

    private void pairTermux() {
        if (!hasRequiredRuntimePermissions()) {
            requestRuntimePermissions();
            return;
        }
        String code = pairingCode.getText().toString().trim();
        if (!code.matches("\\d{6}")) {
            pairingCode.setError("Enter the six-digit code from the system pairing dialog");
            return;
        }
        RecoveryService.startPairing(this, code);
        pairingCode.setText("");
        status.setText("Pairing requested. Keep the system pairing-code dialog open until the result arrives.");
    }

    private void disableAutomaticRecovery() {
        getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .edit()
                .putBoolean(RecoveryService.KEY_AUTO_RESTORE, false)
                .putString(RecoveryService.KEY_LAST_STATE, "automatic_recovery_disabled")
                .apply();
        refreshStatus();
    }

    private void disableWirelessDebugging() {
        if (checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) != PackageManager.PERMISSION_GRANTED) {
            refreshStatus();
            return;
        }
        RecoveryService.start(this, RecoveryService.ACTION_DISABLE_WIRELESS_DEBUGGING);
        status.setText("Disable request sent. This can disconnect the current Wi-Fi ADB session.");
    }

    private boolean hasRequiredRuntimePermissions() {
        return checkSelfPermission(RUN_COMMAND_PERMISSION) == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasTopologyRuntimePermissions() {
        return Build.VERSION.SDK_INT < 33
                || checkSelfPermission(Manifest.permission.NEARBY_WIFI_DEVICES)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void requestRuntimePermissions() {
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(
                    new String[]{
                            RUN_COMMAND_PERMISSION,
                            Manifest.permission.POST_NOTIFICATIONS,
                            Manifest.permission.NEARBY_WIFI_DEVICES
                    },
                    REQUEST_RUNTIME_PERMISSIONS);
        } else {
            requestPermissions(new String[]{RUN_COMMAND_PERMISSION}, REQUEST_RUNTIME_PERMISSIONS);
        }
    }

    private void refreshStatus() {
        boolean autoRestore = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getBoolean(RecoveryService.KEY_AUTO_RESTORE, false);
        String lastState = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getString(RecoveryService.KEY_LAST_STATE, "not_run");
        String shellUid = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getString("last_shell_uid", "not_proven");
        String discoveryMode = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getString("last_discovery_mode", "not_proven");
        boolean secureSettings = checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS)
                == PackageManager.PERMISSION_GRANTED;
        boolean runCommand = checkSelfPermission(RUN_COMMAND_PERMISSION) == PackageManager.PERMISSION_GRANTED;
        int wireless = Settings.Global.getInt(getContentResolver(), "adb_wifi_enabled", 0);
        boolean topologyActive = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getBoolean(TopologyProbeService.KEY_ACTIVE, false);
        String topologyMode = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getString(TopologyProbeService.KEY_MODE, "none");
        String topologyState = getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getString(TopologyProbeService.KEY_STATE, "not_run");
        String topologyInterfaces = topologyActive
                ? getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                        .getString(TopologyProbeService.KEY_INTERFACES, "none")
                : "none";
        status.setText(
                "Boot recovery attempt: " + (autoRestore ? "enabled" : "disabled")
                        + "\nWireless Debugging setting: " + wireless
                        + "\nWRITE_SECURE_SETTINGS: " + (secureSettings ? "granted" : "missing")
                        + "\nTermux RUN_COMMAND: " + (runCommand ? "granted" : "missing")
                        + "\nLast helper state: " + lastState
                        + "\nLast proven shell UID: " + shellUid
                        + "\nLast discovery mode: " + discoveryMode
                        + "\nSelf-hosted probe: " + (topologyActive ? "active" : "inactive")
                        + "\nProbe mode/state: " + topologyMode + " / " + topologyState
                        + "\nLocal interfaces: " + topologyInterfaces);
    }
}

package org.questtermuxlab.wirelessadbrecovery;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.AssetManager;
import android.net.nsd.NsdManager;
import android.net.nsd.NsdServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;
import android.provider.Settings;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public final class RecoveryService extends Service {
    public static final String ACTION_ARM_AND_RESTORE = "org.questtermuxlab.wirelessadbrecovery.action.ARM_AND_RESTORE";
    public static final String ACTION_RESTORE_NOW = "org.questtermuxlab.wirelessadbrecovery.action.RESTORE_NOW";
    public static final String ACTION_RESTORE_ON_BOOT = "org.questtermuxlab.wirelessadbrecovery.action.RESTORE_ON_BOOT";
    public static final String ACTION_PAIR_TERMUX = "org.questtermuxlab.wirelessadbrecovery.action.PAIR_TERMUX";
    public static final String ACTION_DISABLE_WIRELESS_DEBUGGING = "org.questtermuxlab.wirelessadbrecovery.action.DISABLE_WIRELESS";
    public static final String ACTION_AP_FREE_PULSE = "org.questtermuxlab.wirelessadbrecovery.action.AP_FREE_PULSE";
    public static final String ACTION_STOP_AP_FREE_PULSE = "org.questtermuxlab.wirelessadbrecovery.action.STOP_AP_FREE_PULSE";
    public static final String ACTION_POSITIVE_CONTROL = "org.questtermuxlab.wirelessadbrecovery.action.POSITIVE_CONTROL";
    public static final String EXTRA_PAIRING_CODE = "pairing_code";
    public static final String PREFERENCES = "wireless_adb_recovery";
    public static final String KEY_AUTO_RESTORE = "auto_restore_enabled";
    public static final String KEY_LAST_STATE = "last_state";

    private static final String CHANNEL_ID = "wireless_adb_recovery";
    private static final int NOTIFICATION_ID = 42017;
    private static final String RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND";
    private static final String TLS_CONNECT_SERVICE_TYPE = "_adb-tls-connect._tcp.";
    private static final String TLS_PAIRING_SERVICE_TYPE = "_adb-tls-pairing._tcp.";
    private static final long TLS_DISCOVERY_TIMEOUT_MS = 120_000L;
    private static final long BOOT_TRUST_STORE_MIN_UPTIME_MS = 90_000L;
    private static final int MANUAL_ADB_WAIT_SECONDS = 45;
    private static final int BOOT_ADB_WAIT_SECONDS = 240;
    private static final long AP_FREE_PULSE_DURATION_MS = 15_000L;
    private static final int AP_FREE_PULSE_MAX_WRITES = 600;
    private static final long AP_FREE_PULSE_INTERVAL_MS = 25L;
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String TERMUX_RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService";
    private static final String TERMUX_PREFIX = "/data/data/com.termux/files/usr";
    private static final String TERMUX_HOME = "/data/data/com.termux/files/home";
    private static final String RECOVERY_DIR = TERMUX_HOME + "/quest-lab/wireless-adb-recovery";
    private static final String RECOVERY_SCRIPT = RECOVERY_DIR + "/wireless_adb_recovery.py";
    private static final String EXPERIMENT_DIR = TERMUX_HOME + "/quest-lab/wireless-adb-ap-free-experiment";
    private static final String EXPERIMENT_SCRIPT = EXPERIMENT_DIR + "/wireless_adb_recovery.py";
    private static final String EXTRA_RUN_COMMAND_PATH = "com.termux.RUN_COMMAND_PATH";
    private static final String EXTRA_RUN_COMMAND_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS";
    private static final String EXTRA_RUN_COMMAND_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR";
    private static final String EXTRA_RUN_COMMAND_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND";
    private static final String EXTRA_RUN_COMMAND_STDIN = "com.termux.RUN_COMMAND_STDIN";
    private static final String EXTRA_RUN_COMMAND_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT";
    private static final AtomicInteger EXECUTION_ID = new AtomicInteger(2000);

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private volatile boolean pulseCancelRequested;

    public static void start(Context context, String action) {
        Intent intent = new Intent(context, RecoveryService.class).setAction(action);
        if (Build.VERSION.SDK_INT >= 26) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    public static void startPairing(Context context, String pairingCode) {
        Intent intent = new Intent(context, RecoveryService.class)
                .setAction(ACTION_PAIR_TERMUX)
                .putExtra(EXTRA_PAIRING_CODE, pairingCode);
        if (Build.VERSION.SDK_INT >= 26) {
            context.startForegroundService(intent);
        } else {
            context.startService(intent);
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_RESTORE_NOW : intent.getAction();
        startForeground(NOTIFICATION_ID, notification("Preparing recovery"));
        if (ACTION_STOP_AP_FREE_PULSE.equals(action)) {
            pulseCancelRequested = true;
            recordState("ap_free_pulse_stop_requested");
            updateNotification("Stopping AP-free pulse");
            executor.execute(() -> {
                stopForeground(STOP_FOREGROUND_REMOVE);
                stopSelf(startId);
            });
            return START_NOT_STICKY;
        }
        String pairingCode = intent == null ? null : intent.getStringExtra(EXTRA_PAIRING_CODE);
        executor.execute(() -> handleAction(action, pairingCode, startId));
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        pulseCancelRequested = true;
        executor.shutdownNow();
        super.onDestroy();
    }

    private void handleAction(String action, String pairingCode, int startId) {
        try {
            if (ACTION_DISABLE_WIRELESS_DEBUGGING.equals(action)) {
                disableWirelessDebugging();
                return;
            }
            if (ACTION_PAIR_TERMUX.equals(action)) {
                pairTermux(pairingCode);
                return;
            }
            if (ACTION_AP_FREE_PULSE.equals(action)) {
                runApFreePulse();
                return;
            }
            if (ACTION_POSITIVE_CONTROL.equals(action)) {
                runPositiveControl();
                return;
            }
            boolean boot = ACTION_RESTORE_ON_BOOT.equals(action);
            boolean autoRestore = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                    .getBoolean(KEY_AUTO_RESTORE, false);
            if (boot && !autoRestore) {
                recordState("boot_skipped_auto_recovery_disabled");
                return;
            }
            if (ACTION_ARM_AND_RESTORE.equals(action)) {
                getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                        .edit()
                        .putBoolean(KEY_AUTO_RESTORE, true)
                        .apply();
            }
            if (boot && !awaitBootTrustStore()) {
                return;
            }
            restoreWirelessDebugging(
                    boot ? BOOT_ADB_WAIT_SECONDS : MANUAL_ADB_WAIT_SECONDS,
                    !boot);
        } finally {
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf(startId);
        }
    }

    private boolean awaitBootTrustStore() {
        long remaining = BOOT_TRUST_STORE_MIN_UPTIME_MS - SystemClock.elapsedRealtime();
        if (remaining <= 0L) {
            return true;
        }
        recordState("waiting_for_adb_trust_store");
        updateNotification("Waiting for the saved ADB trust store");
        try {
            Thread.sleep(remaining);
            return true;
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            recordState("boot_trust_wait_interrupted");
            return false;
        }
    }

    private void restoreWirelessDebugging(int adbWaitSeconds, boolean allowSettingsEnable) {
        if (checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) != PackageManager.PERMISSION_GRANTED) {
            recordState("blocked_missing_write_secure_settings");
            updateNotification("Missing WRITE_SECURE_SETTINGS grant");
            return;
        }
        if (checkSelfPermission(RUN_COMMAND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            recordState("blocked_missing_termux_run_command");
            updateNotification("Missing Termux RUN_COMMAND permission");
            return;
        }
        recordState("checking_wireless_debugging");
        updateNotification("Checking TLS Wireless Debugging");
        int adbEnabled = Settings.Global.getInt(
                getContentResolver(),
                Settings.Global.ADB_ENABLED,
                0);
        int adbWifiEnabled = Settings.Global.getInt(
                getContentResolver(),
                "adb_wifi_enabled",
                0);
        if (!allowSettingsEnable && (adbEnabled != 1 || adbWifiEnabled != 1)) {
            recordState("boot_blocked_wireless_debugging_not_enabled");
            updateNotification("Wireless Debugging requires an attended restore");
            return;
        }
        if (allowSettingsEnable && (adbEnabled != 1 || adbWifiEnabled != 1)) {
            recordState("enabling_wireless_debugging");
            updateNotification("Enabling TLS Wireless Debugging");
        }
        if (adbEnabled != 1) {
            Settings.Global.putInt(getContentResolver(), Settings.Global.ADB_ENABLED, 1);
        }
        if (adbWifiEnabled != 1) {
            Settings.Global.putInt(getContentResolver(), "adb_wifi_enabled", 1);
        }
        if (allowSettingsEnable && Settings.Global.getLong(
                getContentResolver(),
                "adb_allowed_connection_time",
                -1L) != 0L) {
            Settings.Global.putLong(getContentResolver(), "adb_allowed_connection_time", 0L);
        }

        try {
            Thread.sleep(1500L);
            boolean selfHostedProbe = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                    .getBoolean(TopologyProbeService.KEY_ACTIVE, false);
            String topologyMode = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                    .getString(TopologyProbeService.KEY_MODE, "none");
            String candidateHosts = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                    .getString(TopologyProbeService.KEY_HOSTS, "127.0.0.1");
            int tlsPort = discoverServicePort(
                    TLS_CONNECT_SERVICE_TYPE,
                    "discovering_tls_service",
                    "Discovering TLS Wireless Debugging service",
                    selfHostedProbe ? 10_000L : TLS_DISCOVERY_TIMEOUT_MS);
            if (tlsPort <= 0 && !selfHostedProbe) {
                recordState("tls_nsd_service_not_found");
                updateNotification("TLS Wireless Debugging service was not found");
                return;
            }
            dispatchTermuxRecovery(tlsPort, adbWaitSeconds, candidateHosts, topologyMode);
            recordState(selfHostedProbe
                    ? "termux_self_hosted_probe_dispatched"
                    : "termux_tls_recovery_dispatched");
            updateNotification("Termux is connecting to the TLS service");
            Thread.sleep(4000L);
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            recordState("recovery_interrupted");
        } catch (IOException | RuntimeException failure) {
            recordState("termux_dispatch_failed_" + failure.getClass().getSimpleName());
            updateNotification("Termux recovery dispatch failed");
        }
    }

    private void pairTermux(String pairingCode) {
        if (checkSelfPermission(RUN_COMMAND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            recordState("pairing_blocked_missing_termux_run_command");
            return;
        }
        if (pairingCode == null || !pairingCode.matches("\\d{6}")) {
            recordState("pairing_blocked_invalid_code");
            return;
        }
        try {
            int pairingPort = discoverServicePort(
                    TLS_PAIRING_SERVICE_TYPE,
                    "discovering_tls_pairing_service",
                    "Discovering the operator-opened pairing service",
                    TLS_DISCOVERY_TIMEOUT_MS);
            if (pairingPort <= 0) {
                recordState("tls_pairing_service_not_found");
                updateNotification("Open the system pairing-code dialog and retry");
                return;
            }
            dispatchTermuxPairing(pairingPort, pairingCode);
            recordState("termux_pairing_dispatched");
            updateNotification("Termux pairing result pending");
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            recordState("pairing_interrupted");
        }
    }

    private void disableWirelessDebugging() {
        getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_AUTO_RESTORE, false)
                .apply();
        if (checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) != PackageManager.PERMISSION_GRANTED) {
            recordState("disable_blocked_missing_write_secure_settings");
            return;
        }
        Settings.Global.putInt(getContentResolver(), "adb_wifi_enabled", 0);
        recordState("wireless_debugging_disabled");
        updateNotification("Wireless Debugging disabled");
    }

    private void runApFreePulse() {
        if (checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) != PackageManager.PERMISSION_GRANTED) {
            recordState("ap_free_pulse_blocked_missing_write_secure_settings");
            return;
        }
        if (checkSelfPermission(RUN_COMMAND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            recordState("ap_free_pulse_blocked_missing_termux_run_command");
            return;
        }

        final int priorAdbWifiEnabled = Settings.Global.getInt(
                getContentResolver(), "adb_wifi_enabled", 0);
        pulseCancelRequested = false;
        boolean selfHostedProbe = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                .getBoolean(TopologyProbeService.KEY_ACTIVE, false);
        String topologyMode = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                .getString(TopologyProbeService.KEY_MODE, "none");
        String candidateHosts = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                .getString(TopologyProbeService.KEY_HOSTS, "127.0.0.1");
        try {
            dispatchTermuxExperimentalRecovery(-1, 30, candidateHosts, topologyMode);
        } catch (IOException failure) {
            recordState("ap_free_pulse_termux_dispatch_failed_" + failure.getClass().getSimpleName());
            return;
        }

        recordState(selfHostedProbe
                ? "ap_free_pulse_running_self_hosted"
                : "ap_free_pulse_running_no_topology");
        updateNotification("Running bounded AP-free Wireless Debugging pulse");
        long started = SystemClock.elapsedRealtime();
        long deadline = started + AP_FREE_PULSE_DURATION_MS;
        int writes = 0;
        try {
            while (writes < AP_FREE_PULSE_MAX_WRITES
                    && SystemClock.elapsedRealtime() < deadline
                    && !pulseCancelRequested
                    && !Thread.currentThread().isInterrupted()) {
                Settings.Global.putInt(getContentResolver(), "adb_wifi_enabled", 1);
                writes++;
                Thread.sleep(AP_FREE_PULSE_INTERVAL_MS);
            }
            if (!pulseCancelRequested) {
                Thread.sleep(5_000L);
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            pulseCancelRequested = true;
        } finally {
            Settings.Global.putInt(
                    getContentResolver(), "adb_wifi_enabled", priorAdbWifiEnabled);
        }
        getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                .edit()
                .putInt("ap_free_pulse_write_count", writes)
                .putLong("ap_free_pulse_duration_ms", SystemClock.elapsedRealtime() - started)
                .putInt("ap_free_pulse_restored_setting", priorAdbWifiEnabled)
                .apply();
        recordState(pulseCancelRequested ? "ap_free_pulse_cancelled" : "ap_free_pulse_complete_restored");
        updateNotification(pulseCancelRequested
                ? "AP-free pulse cancelled and prior setting restored"
                : "AP-free pulse complete and prior setting restored");
    }

    private void runPositiveControl() {
        if (checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) != PackageManager.PERMISSION_GRANTED) {
            recordState("positive_control_blocked_missing_write_secure_settings");
            return;
        }
        if (checkSelfPermission(RUN_COMMAND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            recordState("positive_control_blocked_missing_termux_run_command");
            return;
        }
        if (Settings.Global.getInt(
                getContentResolver(), Settings.Global.ADB_ENABLED, 0) != 1) {
            recordState("positive_control_blocked_usb_adb_disabled");
            return;
        }
        Settings.Global.putInt(getContentResolver(), "adb_wifi_enabled", 1);
        recordState("positive_control_enabling_wireless_debugging");
        updateNotification("Waiting for attended Wireless Debugging approval");
        try {
            int tlsPort = discoverServicePort(
                    TLS_CONNECT_SERVICE_TYPE,
                    "positive_control_discovering_tls",
                    "Discovering positive-control TLS service",
                    TLS_DISCOVERY_TIMEOUT_MS);
            dispatchTermuxExperimentalRecovery(
                    tlsPort > 0 ? tlsPort : -1,
                    MANUAL_ADB_WAIT_SECONDS,
                    "127.0.0.1",
                    "infrastructure_positive_control");
            recordState("positive_control_termux_dispatched");
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            recordState("positive_control_interrupted");
        } catch (IOException failure) {
            recordState("positive_control_termux_dispatch_failed_" + failure.getClass().getSimpleName());
        }
    }

    private void dispatchTermuxExperimentalRecovery(
            int tlsPort,
            int adbWaitSeconds,
            String candidateHosts,
            String topologyMode) throws IOException {
        String script = readAsset("wireless_adb_recovery.py");
        String command = "mkdir -p \"" + EXPERIMENT_DIR + "\""
                + " && cat > \"" + EXPERIMENT_SCRIPT + "\""
                + " && chmod 700 \"" + EXPERIMENT_SCRIPT + "\""
                + " && exec \"" + TERMUX_PREFIX + "/bin/python\" \"" + EXPERIMENT_SCRIPT + "\""
                + (tlsPort > 0 ? " --tls-port " + tlsPort + " --port-source android_nsd" : "")
                + " --wait-seconds " + adbWaitSeconds
                + " --status \"" + EXPERIMENT_DIR + "/status.json\""
                + " --topology-mode \"" + safeToken(topologyMode, "none") + "\""
                + candidateHostArguments(candidateHosts)
                + " --no-start-fleet-agent"
                + " --safe-bootstrap-diagnostics";
        dispatchTermuxCommand(command, script, "ap_free_experiment", TERMUX_HOME);
    }

    private int discoverServicePort(
            String requestedServiceType,
            String discoveryState,
            String notificationText,
            long timeoutMs) throws InterruptedException {
        NsdManager nsdManager = getSystemService(NsdManager.class);
        CountDownLatch resolved = new CountDownLatch(1);
        AtomicInteger port = new AtomicInteger(-1);
        AtomicBoolean resolving = new AtomicBoolean(false);
        NsdManager.DiscoveryListener listener = new NsdManager.DiscoveryListener() {
            @Override
            public void onDiscoveryStarted(String serviceType) {
                recordState(discoveryState);
                updateNotification(notificationText);
            }

            @Override
            public void onServiceFound(NsdServiceInfo serviceInfo) {
                String type = serviceInfo.getServiceType();
                String normalizedRequestedType = requestedServiceType.endsWith(".")
                        ? requestedServiceType.substring(0, requestedServiceType.length() - 1)
                        : requestedServiceType;
                if (type == null || !type.startsWith(normalizedRequestedType) || !resolving.compareAndSet(false, true)) {
                    return;
                }
                nsdManager.resolveService(serviceInfo, new NsdManager.ResolveListener() {
                    @Override
                    public void onResolveFailed(NsdServiceInfo failedService, int errorCode) {
                        resolving.set(false);
                    }

                    @Override
                    public void onServiceResolved(NsdServiceInfo resolvedService) {
                        int resolvedPort = resolvedService.getPort();
                        if (resolvedPort >= 1 && resolvedPort <= 65535) {
                            port.set(resolvedPort);
                            resolved.countDown();
                        } else {
                            resolving.set(false);
                        }
                    }
                });
            }

            @Override
            public void onServiceLost(NsdServiceInfo serviceInfo) {
            }

            @Override
            public void onDiscoveryStopped(String serviceType) {
            }

            @Override
            public void onStartDiscoveryFailed(String serviceType, int errorCode) {
                resolved.countDown();
            }

            @Override
            public void onStopDiscoveryFailed(String serviceType, int errorCode) {
            }
        };
        try {
            nsdManager.discoverServices(requestedServiceType, NsdManager.PROTOCOL_DNS_SD, listener);
            resolved.await(timeoutMs, TimeUnit.MILLISECONDS);
            return port.get();
        } finally {
            try {
                nsdManager.stopServiceDiscovery(listener);
            } catch (IllegalArgumentException ignored) {
                // Discovery may have failed before Android registered the listener.
            }
        }
    }

    private void dispatchTermuxRecovery(
            int tlsPort,
            int adbWaitSeconds,
            String candidateHosts,
            String topologyMode) throws IOException {
        String script = readAsset("wireless_adb_recovery.py");
        String command = "mkdir -p \"" + RECOVERY_DIR + "\""
                + " && cat > \"" + RECOVERY_SCRIPT + "\""
                + " && chmod 700 \"" + RECOVERY_SCRIPT + "\""
                + " && exec \"" + TERMUX_PREFIX + "/bin/python\" \"" + RECOVERY_SCRIPT + "\""
                + (tlsPort > 0 ? " --tls-port " + tlsPort + " --port-source android_nsd" : "")
                + " --wait-seconds " + adbWaitSeconds
                + " --status \"" + RECOVERY_DIR + "/status.json\""
                + " --topology-mode \"" + safeToken(topologyMode, "none") + "\""
                + candidateHostArguments(candidateHosts)
                + " --hold-fleet-agent";
        dispatchTermuxCommand(command, script, "recover");
    }

    private String candidateHostArguments(String rawHosts) {
        StringBuilder arguments = new StringBuilder();
        String hosts = rawHosts == null ? "" : rawHosts;
        for (String rawHost : hosts.split(",")) {
            String host = rawHost.trim();
            if (host.matches("(?:\\d{1,3}\\.){3}\\d{1,3}")) {
                arguments.append(" --candidate-host \"").append(host).append("\"");
            }
        }
        if (arguments.length() == 0) {
            arguments.append(" --candidate-host 127.0.0.1");
        }
        return arguments.toString();
    }

    private String safeToken(String value, String fallback) {
        if (value == null || !value.matches("[a-z0-9_]{1,64}")) {
            return fallback;
        }
        return value;
    }

    private void dispatchTermuxPairing(int pairingPort, String pairingCode) {
        String command = "export TMPDIR=\"" + TERMUX_PREFIX + "/tmp\""
                + " && mkdir -p \"$TMPDIR\""
                + " && exec \"" + TERMUX_PREFIX + "/bin/adb\" pair 127.0.0.1:" + pairingPort;
        dispatchTermuxCommand(command, pairingCode + "\n", "pair");
    }

    private void dispatchTermuxCommand(String command, String stdin, String operation) {
        dispatchTermuxCommand(command, stdin, operation, RECOVERY_DIR);
    }

    private void dispatchTermuxCommand(
            String command, String stdin, String operation, String workingDirectory) {
        Intent termux = new Intent("com.termux.RUN_COMMAND");
        termux.setComponent(new ComponentName(TERMUX_PACKAGE, TERMUX_RUN_COMMAND_SERVICE));
        termux.putExtra(EXTRA_RUN_COMMAND_PATH, TERMUX_PREFIX + "/bin/sh");
        termux.putExtra(EXTRA_RUN_COMMAND_ARGUMENTS, new String[]{"-lc", command});
        termux.putExtra(EXTRA_RUN_COMMAND_WORKDIR, workingDirectory);
        termux.putExtra(EXTRA_RUN_COMMAND_BACKGROUND, true);
        termux.putExtra(EXTRA_RUN_COMMAND_STDIN, stdin);
        Intent resultIntent = new Intent(this, RecoveryResultService.class);
        resultIntent.putExtra("execution_id", EXECUTION_ID.incrementAndGet());
        resultIntent.putExtra("operation", operation);
        PendingIntent resultPendingIntent = PendingIntent.getService(
                this,
                EXECUTION_ID.get(),
                resultIntent,
                PendingIntent.FLAG_ONE_SHOT | PendingIntent.FLAG_MUTABLE);
        termux.putExtra(EXTRA_RUN_COMMAND_PENDING_INTENT, resultPendingIntent);
        if (Build.VERSION.SDK_INT >= 26) {
            startForegroundService(termux);
        } else {
            startService(termux);
        }
    }

    private String readAsset(String name) throws IOException {
        AssetManager assets = getAssets();
        try (InputStream input = assets.open(name); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) >= 0) {
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private void recordState(String state) {
        getSharedPreferences(PREFERENCES, MODE_PRIVATE)
                .edit()
                .putString(KEY_LAST_STATE, state)
                .putLong("last_state_at_unix_ms", System.currentTimeMillis())
                .apply();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Wireless ADB recovery",
                    NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Visible status while the opt-in TLS Wireless Debugging recovery runs.");
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        }
    }

    private Notification notification(String text) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                0,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setContentTitle("Wireless ADB Recovery")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setOngoing(true)
                .setContentIntent(contentIntent)
                .build();
    }

    private void updateNotification(String text) {
        getSystemService(NotificationManager.class).notify(NOTIFICATION_ID, notification(text));
    }
}

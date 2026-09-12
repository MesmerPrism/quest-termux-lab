package org.questtermuxlab.wirelessadbrecovery;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.net.wifi.p2p.WifiP2pGroup;
import android.net.wifi.p2p.WifiP2pInfo;
import android.net.wifi.p2p.WifiP2pManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

public final class TopologyProbeService extends Service {
    public static final String ACTION_START_WIFI_DIRECT =
            "org.questtermuxlab.wirelessadbrecovery.action.START_WIFI_DIRECT_PROBE";
    public static final String ACTION_START_LOCAL_ONLY_HOTSPOT =
            "org.questtermuxlab.wirelessadbrecovery.action.START_LOCAL_ONLY_HOTSPOT_PROBE";
    public static final String ACTION_STOP =
            "org.questtermuxlab.wirelessadbrecovery.action.STOP_TOPOLOGY_PROBE";
    public static final String KEY_ACTIVE = "self_hosted_topology_active";
    public static final String KEY_MODE = "self_hosted_topology_mode";
    public static final String KEY_STATE = "self_hosted_topology_state";
    public static final String KEY_HOSTS = "self_hosted_topology_hosts";
    public static final String KEY_INTERFACES = "self_hosted_topology_interfaces";
    public static final String KEY_STARTED_AT = "self_hosted_topology_started_at_unix_ms";
    public static final String MODE_WIFI_DIRECT = "wifi_direct_group_owner";
    public static final String MODE_LOCAL_ONLY_HOTSPOT = "local_only_hotspot_owner";

    private static final String CHANNEL_ID = "self_hosted_adb_probe";
    private static final int NOTIFICATION_ID = 42018;
    private static final long MAX_HOLD_MS = 240_000L;
    private static final int ADDRESS_POLL_LIMIT = 40;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private WifiP2pManager p2pManager;
    private WifiP2pManager.Channel p2pChannel;
    private WifiManager.LocalOnlyHotspotReservation hotspotReservation;
    private boolean cleanupStarted;
    private int activeStartId;

    public static void start(Context context, String action) {
        Intent intent = new Intent(context, TopologyProbeService.class).setAction(action);
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
        activeStartId = startId;
        String action = intent == null ? ACTION_STOP : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            startForeground(NOTIFICATION_ID, notification("Stopping self-hosted topology probe"));
            cleanupAndStop("operator_stop");
            return START_NOT_STICKY;
        }
        if (isActive()) {
            startForeground(NOTIFICATION_ID, notification("A topology probe is already active"));
            recordState(currentMode(), "blocked_probe_already_active", true);
            return START_NOT_STICKY;
        }
        cleanupStarted = false;
        if (ACTION_START_WIFI_DIRECT.equals(action)) {
            startForeground(NOTIFICATION_ID, notification("Creating peerless Wi-Fi Direct group"));
            startWifiDirectGroupOwner();
        } else if (ACTION_START_LOCAL_ONLY_HOTSPOT.equals(action)) {
            startForeground(NOTIFICATION_ID, notification("Starting local-only hotspot"));
            startLocalOnlyHotspot();
        } else {
            startForeground(NOTIFICATION_ID, notification("Unknown topology probe request"));
            recordState("none", "blocked_unknown_action", false);
            stopSelf(startId);
        }
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        closeHotspotReservation();
        if (p2pManager != null && p2pChannel != null) {
            try {
                p2pManager.removeGroup(p2pChannel, null);
            } catch (RuntimeException ignored) {
            }
        }
        getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_ACTIVE, false)
                .apply();
        super.onDestroy();
    }

    private void startWifiDirectGroupOwner() {
        recordState(MODE_WIFI_DIRECT, "starting", true);
        p2pManager = (WifiP2pManager) getSystemService(Context.WIFI_P2P_SERVICE);
        if (p2pManager == null) {
            fail(MODE_WIFI_DIRECT, "wifi_p2p_manager_unavailable");
            return;
        }
        p2pChannel = p2pManager.initialize(this, getMainLooper(), () ->
                fail(MODE_WIFI_DIRECT, "wifi_p2p_channel_disconnected"));
        if (p2pChannel == null) {
            fail(MODE_WIFI_DIRECT, "wifi_p2p_channel_unavailable");
            return;
        }
        WifiP2pManager.ActionListener create = new WifiP2pManager.ActionListener() {
            @Override
            public void onSuccess() {
                recordState(MODE_WIFI_DIRECT, "group_creation_accepted", true);
                updateNotification("Peerless Wi-Fi Direct group active");
                pollWifiDirectState(0);
                scheduleBoundedStop();
            }

            @Override
            public void onFailure(int reason) {
                fail(MODE_WIFI_DIRECT, "group_creation_failed_" + reason);
            }
        };
        try {
            p2pManager.removeGroup(p2pChannel, new WifiP2pManager.ActionListener() {
                @Override
                public void onSuccess() {
                    createWifiDirectGroup(create);
                }

                @Override
                public void onFailure(int reason) {
                    createWifiDirectGroup(create);
                }
            });
        } catch (SecurityException denied) {
            fail(MODE_WIFI_DIRECT, "remove_group_security_exception");
        }
    }

    private void createWifiDirectGroup(WifiP2pManager.ActionListener listener) {
        try {
            p2pManager.createGroup(p2pChannel, listener);
        } catch (SecurityException denied) {
            fail(MODE_WIFI_DIRECT, "create_group_security_exception");
        }
    }

    private void pollWifiDirectState(int attempt) {
        if (cleanupStarted || p2pManager == null || p2pChannel == null) {
            return;
        }
        try {
            p2pManager.requestConnectionInfo(p2pChannel, (WifiP2pInfo info) -> {
                if (info != null && info.groupFormed && info.isGroupOwner) {
                    recordState(MODE_WIFI_DIRECT, "group_owner_ready", true);
                } else {
                    refreshLocalAddresses();
                }
            });
            p2pManager.requestGroupInfo(p2pChannel, (WifiP2pGroup group) -> {
                if (group != null && group.isGroupOwner()) {
                    recordState(MODE_WIFI_DIRECT, "group_owner_ready", true);
                }
            });
        } catch (SecurityException denied) {
            fail(MODE_WIFI_DIRECT, "request_group_security_exception");
            return;
        }
        if (attempt < ADDRESS_POLL_LIMIT) {
            handler.postDelayed(() -> pollWifiDirectState(attempt + 1), 500L);
        }
    }

    private void startLocalOnlyHotspot() {
        recordState(MODE_LOCAL_ONLY_HOTSPOT, "starting", true);
        WifiManager wifiManager = getSystemService(WifiManager.class);
        if (wifiManager == null) {
            fail(MODE_LOCAL_ONLY_HOTSPOT, "wifi_manager_unavailable");
            return;
        }
        try {
            wifiManager.startLocalOnlyHotspot(new WifiManager.LocalOnlyHotspotCallback() {
                @Override
                public void onStarted(WifiManager.LocalOnlyHotspotReservation reservation) {
                    hotspotReservation = reservation;
                    recordState(MODE_LOCAL_ONLY_HOTSPOT, "hotspot_ready", true);
                    updateNotification("Local-only hotspot active");
                    pollLocalAddresses(0);
                    scheduleBoundedStop();
                }

                @Override
                public void onStopped() {
                    if (!cleanupStarted) {
                        fail(MODE_LOCAL_ONLY_HOTSPOT, "hotspot_stopped_by_platform");
                    }
                }

                @Override
                public void onFailed(int reason) {
                    fail(MODE_LOCAL_ONLY_HOTSPOT, "hotspot_failed_" + reason);
                }
            }, handler);
        } catch (SecurityException denied) {
            fail(MODE_LOCAL_ONLY_HOTSPOT, "hotspot_security_exception");
        }
    }

    private void pollLocalAddresses(int attempt) {
        if (cleanupStarted) {
            return;
        }
        refreshLocalAddresses();
        if (attempt < ADDRESS_POLL_LIMIT) {
            handler.postDelayed(() -> pollLocalAddresses(attempt + 1), 500L);
        }
    }

    private void scheduleBoundedStop() {
        handler.postDelayed(() -> cleanupAndStop("bounded_timeout"), MAX_HOLD_MS);
    }

    private void fail(String mode, String state) {
        recordState(mode, state, false);
        updateNotification("Topology probe failed: " + state);
        handler.postDelayed(() -> cleanupAndStop(state), 1000L);
    }

    private void cleanupAndStop(String reason) {
        if (cleanupStarted) {
            return;
        }
        cleanupStarted = true;
        handler.removeCallbacksAndMessages(null);
        closeHotspotReservation();
        if (p2pManager != null && p2pChannel != null) {
            try {
                p2pManager.removeGroup(p2pChannel, new WifiP2pManager.ActionListener() {
                    @Override
                    public void onSuccess() {
                        finishCleanup(reason + "_group_removed");
                    }

                    @Override
                    public void onFailure(int failureReason) {
                        finishCleanup(reason + "_remove_group_failed_" + failureReason);
                    }
                });
                return;
            } catch (RuntimeException ignored) {
            }
        }
        finishCleanup(reason);
    }

    private void finishCleanup(String state) {
        recordState(currentMode(), "stopped_" + state, false);
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf(activeStartId);
    }

    private void closeHotspotReservation() {
        if (hotspotReservation != null) {
            try {
                hotspotReservation.close();
            } catch (RuntimeException ignored) {
            }
            hotspotReservation = null;
        }
    }

    private void recordState(String mode, String state, boolean active) {
        AddressSnapshot addresses = collectLocalAddresses();
        getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_ACTIVE, active)
                .putString(KEY_MODE, mode)
                .putString(KEY_STATE, state)
                .putString(KEY_HOSTS, active ? addresses.hosts : "")
                .putString(KEY_INTERFACES, active ? addresses.interfaces : "none")
                .putLong(KEY_STARTED_AT, active ? System.currentTimeMillis() : 0L)
                .apply();
    }

    private void refreshLocalAddresses() {
        AddressSnapshot addresses = collectLocalAddresses();
        getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .edit()
                .putString(KEY_HOSTS, addresses.hosts)
                .putString(KEY_INTERFACES, addresses.interfaces)
                .apply();
    }

    private boolean isActive() {
        return getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getBoolean(KEY_ACTIVE, false);
    }

    private String currentMode() {
        return getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .getString(KEY_MODE, "none");
    }

    private AddressSnapshot collectLocalAddresses() {
        Set<String> hosts = new LinkedHashSet<>();
        List<String> interfaces = new ArrayList<>();
        hosts.add("127.0.0.1");
        try {
            Enumeration<NetworkInterface> all = NetworkInterface.getNetworkInterfaces();
            while (all != null && all.hasMoreElements()) {
                NetworkInterface networkInterface = all.nextElement();
                Enumeration<InetAddress> addresses = networkInterface.getInetAddresses();
                while (addresses.hasMoreElements()) {
                    InetAddress address = addresses.nextElement();
                    if (!(address instanceof Inet4Address) || address.isLinkLocalAddress()) {
                        continue;
                    }
                    String host = address.getHostAddress();
                    if (address.isLoopbackAddress() || address.isSiteLocalAddress()) {
                        hosts.add(host);
                        interfaces.add(networkInterface.getName() + "=" + host);
                    }
                }
            }
        } catch (Exception ignored) {
        }
        List<String> sortedHosts = new ArrayList<>(hosts);
        Collections.sort(sortedHosts);
        Collections.sort(interfaces);
        return new AddressSnapshot(join(sortedHosts), join(interfaces));
    }

    private static String join(List<String> values) {
        StringBuilder result = new StringBuilder();
        for (String value : values) {
            if (result.length() > 0) {
                result.append(',');
            }
            result.append(value);
        }
        return result.toString();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "Self-hosted Wireless ADB probe",
                    NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Visible status while a bounded Wi-Fi Direct or local-hotspot probe runs.");
            getSystemService(NotificationManager.class).createNotificationChannel(channel);
        }
    }

    private Notification notification(String text) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent contentIntent = PendingIntent.getActivity(
                this,
                1,
                open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, CHANNEL_ID)
                : new Notification.Builder(this);
        return builder
                .setContentTitle("Self-hosted Wireless ADB probe")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setOngoing(true)
                .setContentIntent(contentIntent)
                .build();
    }

    private void updateNotification(String text) {
        getSystemService(NotificationManager.class).notify(NOTIFICATION_ID, notification(text));
    }

    private static final class AddressSnapshot {
        final String hosts;
        final String interfaces;

        AddressSnapshot(String hosts, String interfaces) {
            this.hosts = hosts;
            this.interfaces = interfaces;
        }
    }
}

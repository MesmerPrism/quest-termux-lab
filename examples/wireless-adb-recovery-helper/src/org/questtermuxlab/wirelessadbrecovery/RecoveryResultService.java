package org.questtermuxlab.wirelessadbrecovery;

import android.app.IntentService;
import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import java.nio.charset.StandardCharsets;
import org.json.JSONException;
import org.json.JSONObject;

public final class RecoveryResultService extends IntentService {
    private static final String TAG = "WirelessAdbRecovery";
    private static final int MAX_EXPERIMENT_RESULT_BYTES = 16 * 1024;

    public RecoveryResultService() {
        super("WirelessAdbRecoveryResult");
    }

    @Override
    protected void onHandleIntent(Intent intent) {
        Bundle result = intent == null ? null : intent.getBundleExtra("result");
        String operation = intent == null ? "recover" : intent.getStringExtra("operation");
        if (result == null) {
            record("termux_result_missing", null, null, -1);
            return;
        }
        String stdout = result.getString("stdout", "");
        String stderr = result.getString("stderr", "");
        int exitCode = result.getInt("exitCode", -1);
        int err = result.getInt("err", -1);
        String errmsg = result.getString("errmsg", "");
        if ("pair".equals(operation)) {
            boolean paired = exitCode == 0 && stdout.toLowerCase().contains("successfully paired");
            record(paired ? "termux_pairing_succeeded" : "termux_pairing_failed", null, "tls_pairing_nsd", exitCode);
            return;
        }
        String payloadText = lastNonEmptyLine(stdout);
        boolean apFreeExperiment = "ap_free_experiment".equals(operation);
        try {
            JSONObject payload = new JSONObject(payloadText);
            JSONObject localAdb = payload.optJSONObject("local_adb");
            boolean available = localAdb != null && localAdb.optBoolean("available", false);
            String shellUid = localAdb == null ? null : localAdb.optString("shell_uid", null);
            String discoveryMode = payload.optString("discovery_mode", null);
            String reason = localAdb == null ? "missing_local_adb_result" : localAdb.optString("reason", null);
            boolean modernTlsDiscovery = "tls_mdns".equals(discoveryMode) || "tls_nsd".equals(discoveryMode);
            boolean acceptedExperimentalDiscovery = apFreeExperiment
                    && "tls_property".equals(discoveryMode);
            if (apFreeExperiment && !recordExperimentalRaw(payloadText)) {
                record("ap_free_result_rejected_oversize", shellUid, discoveryMode, exitCode);
            } else if (exitCode == 0
                    && available
                    && "2000".equals(shellUid)
                    && (modernTlsDiscovery || acceptedExperimentalDiscovery)) {
                record(apFreeExperiment ? "ap_free_tls_shell_available" : "tls_shell_available",
                        shellUid, discoveryMode, exitCode);
            } else {
                record((apFreeExperiment ? "ap_free_tls_recovery_failed_" : "tls_recovery_failed_")
                                + safeReason(reason),
                        shellUid, discoveryMode, exitCode);
            }
        } catch (JSONException failure) {
            Log.w(
                    TAG,
                    "Invalid Termux result JSON exitCode=" + exitCode
                            + " err=" + err
                            + " errmsg=" + tail(errmsg)
                            + " stdout=" + tail(stdout)
                            + " stderr=" + tail(stderr));
            if (apFreeExperiment) {
                recordExperimentalRaw(payloadText);
            }
            record((apFreeExperiment ? "ap_free_" : "")
                    + "termux_result_invalid_json_exit_" + exitCode + "_err_" + err,
                    null, null, exitCode);
        }
    }

    private boolean recordExperimentalRaw(String payloadText) {
        if (payloadText.getBytes(StandardCharsets.UTF_8).length > MAX_EXPERIMENT_RESULT_BYTES) {
            return false;
        }
        return getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE)
                .edit()
                .putString("last_ap_free_result_json", payloadText)
                .putLong("last_ap_free_result_at_unix_ms", System.currentTimeMillis())
                .commit();
    }

    private void record(String state, String shellUid, String discoveryMode, int exitCode) {
        android.content.SharedPreferences preferences =
                getSharedPreferences(RecoveryService.PREFERENCES, MODE_PRIVATE);
        long priorRevision = preferences.getLong(
                LoopbackAdbProofProvider.KEY_EVIDENCE_REVISION,
                0L);
        long nextRevision = priorRevision == Long.MAX_VALUE
                ? 1L
                : priorRevision + 1L;
        long observedAtMs = System.currentTimeMillis();
        long freshUntilMs = Math.addExact(
                observedAtMs,
                LoopbackAdbProofProvider.MAX_PROOF_LIFETIME_MS);
        boolean available = "tls_shell_available".equals(state)
                && "2000".equals(shellUid)
                && ("tls_nsd".equals(discoveryMode)
                        || "tls_mdns".equals(discoveryMode));
        String digest = available
                ? LoopbackAdbProofProvider.computeOwnerEvidenceSha256(
                        nextRevision,
                        observedAtMs,
                        freshUntilMs,
                        discoveryMode)
                : "";
        preferences.edit()
                .putString(RecoveryService.KEY_LAST_STATE, state)
                .putString("last_shell_uid", shellUid == null ? "not_proven" : shellUid)
                .putString("last_discovery_mode", discoveryMode == null ? "not_proven" : discoveryMode)
                .putInt("last_result_exit_code", exitCode)
                .putLong("last_result_at_unix_ms", observedAtMs)
                .putLong(
                        LoopbackAdbProofProvider.KEY_EVIDENCE_REVISION,
                        nextRevision)
                .putString(
                        LoopbackAdbProofProvider.KEY_OWNER_EVIDENCE_SHA256,
                        digest)
                .commit();
    }

    private String lastNonEmptyLine(String text) {
        String[] lines = text.split("\\R");
        for (int index = lines.length - 1; index >= 0; index--) {
            String value = lines[index].trim();
            if (!value.isEmpty()) {
                return value;
            }
        }
        return "";
    }

    private String safeReason(String value) {
        if (value == null || value.isEmpty()) {
            return "unknown";
        }
        return value.replaceAll("[^A-Za-z0-9_.-]", "_");
    }

    private String tail(String value) {
        String normalized = value == null ? "" : value.replaceAll("[\\r\\n]+", " ").trim();
        return normalized.length() <= 1000 ? normalized : normalized.substring(normalized.length() - 1000);
    }
}

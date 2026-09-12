package org.questtermuxlab.wirelessadbrecovery;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;

import java.io.FileNotFoundException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Arrays;

/**
 * Query-only, same-signer projection of the latest short-lived Termux
 * loopback ADB shell proof.
 *
 * The provider exposes no target, host, port, serial, stdout, filesystem
 * path, pairing material, command, or Fleet operation identity.
 */
public final class LoopbackAdbProofProvider extends ContentProvider {
    static final String AUTHORITY =
            "org.questtermuxlab.wirelessadbrecovery.loopbackproof";
    static final String PATH = "v1/loopback-adb-proof";
    static final String SCHEMA = "rusty.quest.loopback_adb_proof.v1";
    static final long MAX_PROOF_LIFETIME_MS = 60_000L;
    static final String KEY_EVIDENCE_REVISION = "loopback_proof_evidence_revision";
    static final String KEY_OWNER_EVIDENCE_SHA256 = "loopback_proof_owner_evidence_sha256";

    private static final String[] COLUMNS = {
            "schema",
            "evidence_revision",
            "observed_at_ms",
            "fresh_until_ms",
            "state",
            "route_mode",
            "discovery_mode",
            "listener_discovered",
            "shell_uid",
            "owner_evidence_sha256"
    };

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public Cursor query(
            Uri uri,
            String[] projection,
            String selection,
            String[] selectionArgs,
            String sortOrder) {
        requireExactQuery(uri, projection, selection, selectionArgs, sortOrder);
        MatrixCursor cursor = new MatrixCursor(COLUMNS, 1);
        SharedPreferences preferences = requireContext().getSharedPreferences(
                RecoveryService.PREFERENCES,
                android.content.Context.MODE_PRIVATE);
        long revision = preferences.getLong(KEY_EVIDENCE_REVISION, 0L);
        long observedAtMs = preferences.getLong("last_result_at_unix_ms", -1L);
        String state = preferences.getString(RecoveryService.KEY_LAST_STATE, "");
        String discoveryMode = preferences.getString("last_discovery_mode", "");
        String shellUid = preferences.getString("last_shell_uid", "");
        long freshUntilMs;
        try {
            freshUntilMs = Math.addExact(observedAtMs, MAX_PROOF_LIFETIME_MS);
        } catch (ArithmeticException failure) {
            return cursor;
        }
        long nowMs = System.currentTimeMillis();
        if (revision <= 0
                || observedAtMs < 0
                || freshUntilMs <= nowMs
                || !"tls_shell_available".equals(state)
                || !("tls_nsd".equals(discoveryMode)
                        || "tls_mdns".equals(discoveryMode))
                || !"2000".equals(shellUid)) {
            return cursor;
        }
        String digest = preferences.getString(KEY_OWNER_EVIDENCE_SHA256, "");
        String expected = computeOwnerEvidenceSha256(
                revision,
                observedAtMs,
                freshUntilMs,
                discoveryMode);
        if (!expected.equals(digest)) {
            return cursor;
        }
        cursor.addRow(new Object[] {
                SCHEMA,
                revision,
                observedAtMs,
                freshUntilMs,
                "available",
                "modern_tls",
                discoveryMode,
                1,
                "2000",
                digest
        });
        return cursor;
    }

    @Override
    public Cursor query(
            Uri uri,
            String[] projection,
            String selection,
            String[] selectionArgs,
            String sortOrder,
            CancellationSignal cancellationSignal) {
        if (cancellationSignal != null) {
            cancellationSignal.throwIfCanceled();
        }
        return query(uri, projection, selection, selectionArgs, sortOrder);
    }

    @Override
    public String getType(Uri uri) {
        requireExactUri(uri);
        return "vnd.android.cursor.item/vnd.rusty.quest.loopback-adb-proof";
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException("query_only");
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException("query_only");
    }

    @Override
    public int update(
            Uri uri,
            ContentValues values,
            String selection,
            String[] selectionArgs) {
        throw new UnsupportedOperationException("query_only");
    }

    @Override
    public android.os.Bundle call(
            String method,
            String arg,
            android.os.Bundle extras) {
        throw new UnsupportedOperationException("query_only");
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode)
            throws FileNotFoundException {
        throw new FileNotFoundException("query_only");
    }

    static String computeOwnerEvidenceSha256(
            long revision,
            long observedAtMs,
            long freshUntilMs,
            String discoveryMode) {
        String canonical = SCHEMA + "\n"
                + revision + "\n"
                + observedAtMs + "\n"
                + freshUntilMs + "\n"
                + "available\n"
                + "modern_tls\n"
                + discoveryMode + "\n"
                + "1\n"
                + "2000\n";
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(
                    canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexadecimal = new StringBuilder(64);
            for (byte value : digest) {
                hexadecimal.append(String.format("%02x", value & 0xff));
            }
            return hexadecimal.toString();
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException("SHA-256 unavailable", impossible);
        }
    }

    private void requireExactQuery(
            Uri uri,
            String[] projection,
            String selection,
            String[] selectionArgs,
            String sortOrder) {
        requireExactUri(uri);
        if (!Arrays.equals(COLUMNS, projection)
                || selection != null
                || selectionArgs != null
                || sortOrder != null) {
            throw new IllegalArgumentException("exact_projection_required");
        }
    }

    private void requireExactUri(Uri uri) {
        if (uri == null
                || !"content".equals(uri.getScheme())
                || !AUTHORITY.equals(uri.getAuthority())
                || !("/" + PATH).equals(uri.getPath())
                || uri.getQuery() != null
                || uri.getFragment() != null) {
            throw new IllegalArgumentException("unsupported_uri");
        }
    }
}

package org.questtermuxlab.wirelessadbrecovery;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent != null && Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            RecoveryService.start(context, RecoveryService.ACTION_RESTORE_ON_BOOT);
        }
    }
}

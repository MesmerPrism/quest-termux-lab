package org.questtermuxlab.agentlauncher;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private static final int REQUEST_RUN_COMMAND = 1001;
    private static final String RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND";
    private static final String TERMUX_PACKAGE = "com.termux";
    private static final String TERMUX_RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService";
    private static final String EXTRA_RUN_COMMAND_PATH = "com.termux.RUN_COMMAND_PATH";
    private static final String EXTRA_RUN_COMMAND_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS";
    private static final String EXTRA_RUN_COMMAND_WORKDIR = "com.termux.RUN_COMMAND_WORKDIR";
    private static final String EXTRA_RUN_COMMAND_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND";
    private static final String TERMUX_PREFIX = "/data/data/com.termux/files/usr";
    private static final String TERMUX_HOME = "/data/data/com.termux/files/home";
    private static final String AGENT_WORKDIR = TERMUX_HOME + "/quest-lab/fleet-agent-live";
    private static final String START_AGENT_SCRIPT =
            "export HOME=" + TERMUX_HOME + "; "
                    + "export PREFIX=" + TERMUX_PREFIX + "; "
                    + "export PATH=$PREFIX/bin:$PATH; "
                    + "export TMPDIR=$PREFIX/tmp; "
                    + "mkdir -p \"$TMPDIR\" \"" + AGENT_WORKDIR + "\"; "
                    + "cd \"" + AGENT_WORKDIR + "\" || exit 2; "
                    + "if [ -s agent-helper.pid ] && kill -0 \"$(cat agent-helper.pid)\" 2>/dev/null; then "
                    + "echo already-running; "
                    + "else "
                    + "nohup python termux_fleet_agent.py --config config.json > agent-helper.log 2>&1 & "
                    + "echo $! > agent-helper.pid; "
                    + "echo started; "
                    + "fi";

    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildLayout());
        maybeAutoStart(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        maybeAutoStart(intent);
    }

    private void maybeAutoStart(Intent intent) {
        if (intent != null && intent.getBooleanExtra("start_agent", false)) {
            startAgentWithPermissionCheck();
        }
    }

    private View buildLayout() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        int pad = dp(18);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("Termux Agent Launcher");
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        root.addView(title, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        status = new TextView(this);
        status.setText("Ready. Requires Termux RUN_COMMAND permission.");
        status.setTextSize(14);
        status.setPadding(0, dp(14), 0, dp(14));
        root.addView(status, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        Button start = new Button(this);
        start.setText("Start Termux Agent");
        start.setOnClickListener(v -> startAgentWithPermissionCheck());
        root.addView(start, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT));

        return root;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void startAgentWithPermissionCheck() {
        if (checkSelfPermission(RUN_COMMAND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{RUN_COMMAND_PERMISSION}, REQUEST_RUN_COMMAND);
            status.setText("Requested Termux RUN_COMMAND permission.");
            return;
        }
        startTermuxAgent();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_RUN_COMMAND
                && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startTermuxAgent();
        } else {
            status.setText("RUN_COMMAND permission was not granted.");
        }
    }

    private void startTermuxAgent() {
        Intent command = new Intent("com.termux.RUN_COMMAND");
        command.setComponent(new ComponentName(TERMUX_PACKAGE, TERMUX_RUN_COMMAND_SERVICE));
        command.putExtra(EXTRA_RUN_COMMAND_PATH, TERMUX_PREFIX + "/bin/sh");
        command.putExtra(EXTRA_RUN_COMMAND_ARGUMENTS, new String[]{"-lc", START_AGENT_SCRIPT});
        command.putExtra(EXTRA_RUN_COMMAND_WORKDIR, AGENT_WORKDIR);
        command.putExtra(EXTRA_RUN_COMMAND_BACKGROUND, true);
        try {
            ComponentName started = Build.VERSION.SDK_INT >= 26
                    ? startForegroundService(command)
                    : startService(command);
            status.setText(started == null
                    ? "Termux did not accept the command."
                    : "Start command sent to Termux.");
        } catch (RuntimeException ex) {
            status.setText("Failed to start Termux command: " + ex.getClass().getSimpleName()
                    + ": " + ex.getMessage());
        }
    }
}

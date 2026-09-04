package io.github.mesmerprism.questtermuxlab.codexdemo;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private static final String TITLE = "Built by Codex on Quest";
    private static final int BACKGROUND = Color.rgb(30, 36, 50);

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(48, 48, 48, 48);
        root.setBackgroundColor(BACKGROUND);

        TextView title = new TextView(this);
        title.setText(TITLE);
        title.setTextColor(Color.WHITE);
        title.setTextSize(34.0f);
        title.setGravity(Gravity.CENTER);

        TextView subtitle = new TextView(this);
        subtitle.setText("Source → Git → APK → Quest");
        subtitle.setTextColor(Color.rgb(174, 214, 255));
        subtitle.setTextSize(20.0f);
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setPadding(0, 24, 0, 0);

        root.addView(title);
        root.addView(subtitle);
        setContentView(root);
    }
}

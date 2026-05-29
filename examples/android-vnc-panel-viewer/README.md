# Android VNC Panel Viewer

This is a minimal Quest 2D panel viewer for the local VNC/MJPEG bridge in this
repository. It is intended for lab observation only: Termux and Termux:X11 still
own the Linux desktop, while this Android activity owns only a landscape
viewer surface.

The activity declares an explicit landscape 2D layout hint so Horizon OS can
present it as a wider panel than Termux:X11's normal phone-shaped activity. It
loads `http://127.0.0.1:18080/stream.mjpg` by default and keeps the image
contained instead of cropped. Early headset validation shows the viewer can
present a full 1280x720 desktop stream in a wide panel.

## Use

1. Start the Termux:X11 desktop and localhost VNC server.
2. Start the host MJPEG bridge from this repo.
3. Forward or reverse the bridge so the headset can reach it on device
   loopback:

```powershell
adb reverse tcp:18080 tcp:18080
```

4. Build and install the viewer APK with the public build helper.
5. Launch `Termux VNC Panel` from the headset.

The default URL can be overridden through an intent extra:

```powershell
adb shell am start -n org.questtermuxlab.vncpanel/.MainActivity `
  --es stream_base_url http://127.0.0.1:18080
```

Keep LAN exposure out of this default flow. The bridge should remain bound to
localhost unless a separate security review explicitly approves otherwise.

The viewer does not forward desktop keyboard or pointer input. Treat it as a
visual witness for the stream and keep direct stream endpoint captures as the
primary automated evidence.

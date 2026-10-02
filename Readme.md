# VRC-FISH! — VRChat Auto Fishing Bot

An auto-fishing bot for VRChat's fishing minigame. Uses an RF-DETR object
detector to locate the bar / fish / bite-mark on screen, then drives the
mouse with a PD controller to keep the fish inside the bar.

> ⚠️ **Disclaimer**: This is an automation tool (macro). Using it may violate
> VRChat's (or the relevant platform's) Terms of Service. Use at your own
> risk — the author is not responsible for any consequences (e.g. bans).

## For end users (no Python required)

1. Go to the [Releases](../../releases) page of this repo
2. Download the latest `.zip`, extract it anywhere
3. Open VRChat and get to the fishing spot
4. Run `VRC-FISH.exe`
5. Press **F8** to start/stop the bot (or click the START button)
6. Tune behavior anytime from the **⚙️ Settings** button — changes you save
   persist in a `settings.json` next to the `.exe`

**Requirements**: Windows 10/11. GPU inference runs through DirectML, which
works on NVIDIA, AMD, and Intel GPUs (falls back to CPU if none is available).

## For developers (run from source)

```bash
git clone https://github.com/Kantheephob/vrc-fish-bot.git
cd VRC-FISH
pip install -r requirements.txt
python src/main.py
```

Project layout:

```
VRC-FISH/
├── requirements.txt
├── build.bat            # one-click Windows build script
├── README.md
└── src/
    ├── main.py           # UI + entry point
    ├── fishing_bot.py    # state machine + PD controller
    ├── detector.py       # RF-DETR preprocess/postprocess
    ├── controller.py     # mouse control (Windows API)
    ├── game_capture.py   # captures the VRChat window
    ├── config.py         # default tunable values
    └── models/
        └── rfdetr-small.onnx
```

## Building the .exe yourself

On Windows, just double-click `build.bat`, or run it manually:

```bat
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --onefile --windowed --name VRC-FISH ^
  --add-data "src\models;models" ^
  --collect-all onnxruntime ^
  src\main.py
```

The result is `dist\VRC-FISH.exe`. Test it on a machine with no Python
installed to confirm everything (especially the onnxruntime-directml DLLs)
is bundled correctly.

> Don't commit `dist/`, `build/`, or the `.exe` itself into the git repo —
> upload it to a GitHub **Release** instead. Binary files bloat the repo and
> slow down every future clone.

## Settings

Everything tunable is exposed in the in-app Settings window — no code
editing required: confidence thresholds, timing values, PD gains (KP/KD),
smoothing (EMA alpha), hysteresis (anti-oscillation), and loop speed.
Click **"Apply + Save"** to persist your values across restarts.

## License

See `LICENSE`.

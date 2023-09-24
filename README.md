# video-tools

The **video-tools** repo contains a collection of tools used to capture and record
video footage from a VCR. This is a local workflow that involves running a VCR into a
video capture device, then using OBS to capture, deinterlace, and upscale the footage
before writing it to disk.

This workflow takes many cues from this YouTube video by **The Oldskool PC**:

- [How to convert VHS videotape to 60p digital video (2023)](https://youtu.be/tk-n7IlrXI4?si=UoV8nNArx4slICPU)

Since we want to be able to stream the video footage at
[twitch.tv/GoldenVCR](https://www.twitch.tv/goldenvcr) while recording, we need to run
two instances of OBS:

- A portable instance of OBS that's dedicated solely to capturing and recording VHS
  footage. This copy of OBS is installed to `obs/`, and it's largely managed by the
  tools in this repo.

- A main instance of OBS that's configured for streaming: its scenes be configured to
  capture video and audio from our portable, VHS-only instance of OBS. This
  installation of OBS is not managed by this repository.

Note that Windows is the only supported platform for **video-tools**: we install the
Windows version of OBS, and the scripts that help us operate OBS use the Win32 API.
However, the [`install-obs.sh`](./install-obs.sh) script requires a Windows-compatible
Bash shell: I use Git Bash.

## Required hardware

This workflow requires a VCR and a video capture device. I happen to be using:

- A **Sony SLV-N71** VCR
- An **I-O Data GV-USB2** USB capture device

I'm using the Windows drivers recommended in the description of the video linked above,
installed from `gvusb2_111.exe` (8958272 bytes in size; md5 checksum
`6675e635280c6938218241fee582c6fa`).

It's also important to ensure that you have sufficient USB bandwidth to run the capture
device alongside any other USB peripherals (cameras etc.) needed for streaming. It may
be necessary to connect devices to multiple different buses, or to reduce USB bandwidth
by lowering camera capture resolutions, configuring cameras to capture MJPEG instead of
uncompressed footage, etc.

## Initial setup

The [`obs/`](./obs/) directory contains a portable installation of OBS. This copy of
OBS is used solely for capturing and recording VHS footage locally.

We also have a handful of scripts used to make the process of capturing and editing
video easier. To ensure that you're ready to run these scripts:

1. Install the latest version of [Python 3](https://www.python.org/downloads/).
2. Install dependencies with `pip install -r requirements.txt`.
3. Use Git Bash (or another bash-compatible shell that has access to `cmd.exe`) to
   invoke [`./install-obs.sh`](./install-obs.sh). This will install and configure a
   local, portable installation of OBS.
4. Install [DaVinci Resolve 18](https://www.blackmagicdesign.com/products/davinciresolve).
5. Install [ffmpeg](https://ffmpeg.org/download.html) and ensure that the `ffmpeg` and
   `ffprobe` binaries are in your PATH.

We use [`obs/configs`](./obs/configs/) to store machine-specific configuration details,
including the OBS Profile and Scene Collection used for capture. If there's an existing
config directory at `obs/configs/your-hostname`, the OBS install script will symlink it
into `obs/config/obs-studio`.

If you're setting up this repo on a new machine, you'll need to configure OBS manually
as described below.

## OBS Configuration

To set up OBS for VCR capture on a new machine:

 1. Once installed, start OBS from `obs/bin/64bit/obs64.exe`
 2. In the auto-configuration wizard, select **Optimize for recording**, and choose a
   **Canvas Resolution** of 1920x1080 and an **FPS** value of 60.
 3. Apply the suggested settings, then click the **Settings** button in the main UI.
 4. Under **Output** &rarr; **Recording**, if using the `Simple` output mode:
    - Set **Recording Path** to `..\..\..\capture`
    - Set **Recording Format** to `.mkv`
 5. Under **Output**, change **Output Mode** to `Advanced` and configure the following:
    - **Streaming** tab &rarr; **Streaming Settings:**
      - **Audio Encoder:** `FFmpeg AAC`
      - **Video Encoder:** `NVIDIA NVENC H.264`
    - **Streaming** tab &rarr; **Encoder Settings:**
      - **Rate Control:** `CQP`
      - **CQ Level:** `18`
      - **Keyframe Interval:** `1 s`
      - **Preset:** `P5: Slow (Good Quality)`
      - **Tuning:** `High Quality`
      - **Multipass Mode:** `Two Passes (Quarter Resolution)`
      - **Profile:** `high`
      - **Look-ahead:** `off`
      - **Psycho Visual Tuning:** `on`
      - **GPU:** `0`
      - **Max B-frames:** `2`
    - **Recording** tab:
      - **Type:** `Standard`
      - **Recording Path:** `..\..\..\capture`
      - **Recording Format:** `Matroska Video (.mkv)`
      - **Video Encoder:** `(Use stream encoder)`
      - **Audio Encoder:** `(Use stream encoder)`
    - **Audio** tab, **Track 1:**
      - **Audio Bitrate:** `192`
 6. Under **Video**:
    - Set both **Resolution** values to `1440x900`
    - Set the **FPS** value to `59.94`
 7. Confirm your settings changes and return to the main UI.
 8. From the menu bar, choose **Profile** &rarr; **Rename** and enter `VHS`.
 9. Choose **Scene Collection** &rarr; **Rename** and enter `VHS`.
10. In the **Scenes** panel, rename the default Scene to `VHS`.
11. In the **Sources** panel, add a new **Video Capture Source** named `GV-USB2`, and:
    - For **Device**, choose `GV-USB2, Analog Capture`
    - Click **Configure Video**, and ensure that **VID DEINTERLACE METHOD** is set to
      `WEAVE`
12. Select the new **GV-USB2** source and press Ctrl-E to edit its transforms:
    - Set **Size** to `1440px` x `1080px`
13. Right-click the **GV-USB2** soure and choose **Deinterlacing** &rarr; **Yadif 2x**
14. Right-click the **GV-USB2** source and choose **Scale Filtering** &rarr; **Lanczos**
15. Arrange the UI as desired, ensuring that a point in the exact center of the
    window is still positioned over the video preview. My preferences:
    - Hide the **Scenes** panel via **Docks** &rarr; **Scenes**
    - Hide the **Scene Transitions** via **Docks** &rarr; **Scene Transitions**
    - Orient the **Audio Mixer** panel vertically, by clicking the **...** button in
      the panel and choosing **Vertical Layout**
    - Open the **Stats** panel via **Docks** &rarr; **Stats**
    - Dock the **Audio Mixer** panel to the left of the video preview
    - Dock the **Sources** panel to the left of the **Audio Mixer** panel
    - Dock the **Controls** panel beneath the **Sources** panel
    - Dock the **Stats** panel beneath the **Controls** panel
16. In the **Audio Mixer**, mute both the **Desktop Audio** and **Mic/Aux** inputs so
    that the only active input is **GV-USB2**.
17. Click the **Gear** button in the **Audio Mixer** to open the
    **Advanced Audio Properties** dialog, and:
    - For the **GV-USB2** input, set **Audio Monitoring** to `Monitor and Output`.
18. Play a tape and make a brief test recording. When you check the
    [`capture/`](./capture/) directory, you should have a new `.mkv` file that looks
    and sounds identical to what you saw in the OBS preview while recording.

If your new OBS configuration is working as expected, then you may wish to start
versioning it in [`obs/configs`](./obs/configs/). To do so, close OBS and then run
[`./bootstrap-obs-config.sh`](./bootstrap-obs-config.sh).

## Capture workflow

### Recording from OBS

When you're ready to start capturing video:

1. Turn on the VCR.
2. Run `python open.py` to ensure that our portable copy of OBS is running, with
   projector window open.
3. When ready to start writing video files to disk, click **Start Recording**.
4. When finished recording the current tape or segment, click **Stop Recording**.

OBS should be configured to write timestamped `.mkv` files into the `capture/`
directory. Once you've finished a tape, you can cut a new recording from your captured
footage.

### Cutting a new recording

To "cut" a recording, we simply grab all the clips recorded from OBS for a single tape,
and move them into a `capture/<tape-id>/` subdirectory, following a specific naming
convention. You can use the [`cut.py`](./cut.py) script to handle this process:

1. Verify that `capture/` contains only the clips for your desired tape
2. Run `python cut.py <tape-id>` to move those clips to `capture/<tape-id>`

For example, if we've finished recording two clips from tape 54, then we'll have a
couple of files that look something like this:

- `capture/2023-09-16 14-40-33.mkv`
- `capture/2023-09-16 15-02-20.mkv`

Running `python cut.py 54` will move those two files to:

- `capture/54/54_raw.001.mkv`
- `capture/54/54_raw.002.mkv`

### Editing the footage for a tape

Once you've got all the files for a tape organized in a `capture/<tape-id>`
subdirectory, you can use the [`edit.py`](./edit.py) script to automatically generate
a DaVinci Resolve project for that tape, with the proper settings
(1440x1080, 59.94 FPS) and a timeline prepopulated with all your clips. To create and
open a project in Resolve:

1. Run `python edit.py <tape-id> --detect-cuts`

For example, running `python edit.py 54` will open Resolve (if it's not already open)
create a new project called "54", open that project, create a single timeline, and add
both `54_raw.001.mkv` and `54_raw.002.mkv` to that timeline, in sequence.

The `--detect-cuts`/`-c` flag will cause the script to analyze the footage up-front to
detect full-frame scene changes in the image, and then place clip markers in Resolve at
the location of those cuts. You can make cut detection more or less sensitive to image
changes by lower or raising the `--cut-detection-threshold`/`-t` value. If the tape is
going to be exported as a single video, rather than being split into multiple segments,
you're free to omit the `--detect-cuts` flag.

Once the script has finished, you should have a timeline open in Resolve, with
_"Ready for edit."_ displayed in the script console. You can close the console window,
then begin editing. A few tips:

1. The **Up** and **Down** arrows will navigate to the start and end of each timeline
   item, **Left** and **Right** will navigate by a single frame, and **Ctrl+B** will
   split at the current playback position.
2. If you used `--detect-cuts`, the clip will have a marker at the location of each
   detected cut. You can quickly jump between markers using **Shift+Up** and
   **Shift+Down**. If the footage for a tape needs to be split into multiple segments
   (e.g. home movies, or multiple programs/commercials in a TV recording), you can
   quickly seek around and break the timeline into multiple clips.
3. To name a clip: right-click on the clip in the timeline and choose
   **Clip Attributes...**, then in the **Name** tab, enter a new **Clip Name** value.
   Naming clips allows the automated export process to identify the export filename.
   e.g. if tape 56 has two segments, and you name them `foobar` and `hello_world` in
   Resolve, they'll be exported as:
   - `56_01_foobar.mp4`
   - `56_02_hello_world.mp4`
4. If a phantom Resolve window starts cluttering your screen, open an Administrator
   command prompt and run `taskkill /f /im dwm.exe`.

### Trimming final clips based on the edit

Once you've got the footage in Resolve, you're free to continue working in Resolve
right up through the export process. However, for the basic VHS capture workflow that
involves minimal non-linear editing (i.e. simply cutting off heads and tails and
splitting a video into multiple clips), the [`trim.py`](./trim.py) script can help
automate the process of exporting final videos.

Exported clips are canonically written to `storage/<tape-id>/`, with the filename
matching either `<tape_id>.mp4` or `<tape_id>_##_<underscore-delimited-name>.mp4`.

If you're exporting clips with `trim.py` (instead of directly in Resolve), you'll want
to choose between one of two export modes:

- **Stream Copy:** Video will be copied directly from the source `.mkv`, without
  reencoding. This is very fast and does not add any compression overhead, but the
  video must begin on a keyframe, so the start point of your exported clip will be up
  to one second (or whatever keyframe interval you recorded with) ahead of your desired
  start point. This is a great choice for home movies, where seeing a bit of the
  previous scene isn't a problem, or for single-segment tapes where you simply need to
  cut the head and tail off the recording.

- **Reencode:** Video will be re-encoded using `libx264`. This takes much longer than a
  simple stream copy, and it introduces a bit of additional compression, but it ensures
  that the video begins and ends exactly where you placed your cuts in Resolve. Quality
  loss from recompression is largely imperceptible at the default CRF value (10), but
  you can use higher CRF values to reduce the final file size. This is the best choice
  for anything requiring precise cuts, such as trimming lots of 30-second commercials
  out of a TV broadcast.

When you're ready to export clips using the automated process:

1. Ensure that you have the desired timeline loaded in DaVinci Resolve
2. Decide whether to copy or reencode:
    - If using stream copy, run `python trim.py --copy`
    - If reencoding, run `python trim.py [--crf 10]`
3. Wait for the script to finish - it could take a while. As each clip is processed,
   you'll see the output of each ffmpeg command.

When finished, your exported files can be found in `storage/<tape-id>`. From there, you
can upload them to YouTube, offload them to external storage, etc.

## Configuring another OBS instance to stream while capturing

The [`open.py`](./open.py) script automatically opens a
**Windowed Projector (Preview)** window and sets it to the full resolution of the
captured footage, i.e. 1440x1080, making it a suitable target window for capturing with
another instance of OBS.

If you want to stream this footage from another instance of OBS while running a
capture, run `open.py` to open the VHS-recording-only copy of OBS, the open your main
OBS installation and set up a **Video Capture Device** source with these settings:

- **Window:** `[obs64.exe]: Windowed Projector (Preview)`
- **Capture Method:** `Windows 10 (1903 and up)`
- **Window Match Priority:** `Window title must match`
- **Capture Cursor:** `off`
- **Client Area:** `on`

Then add an **Application Audio Capture** source with these settings:

- **Window:** `[obs64.exe]: OBS 29.1.3 - Portable Mode - Profile: VHS - Scenes: VHS`
- **Window Match Priority:** `Window title must match`

Note that `open.py` is idempotent: you can run it as many times as you like, and it
will simply ensure that OBS is running with an appropriately-sized projector window. It
will have no extra effect if run repeatedly, so you can safely bind it to a hotkey or
run it periodically in a loop while streaming.

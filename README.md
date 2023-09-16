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

We also have a handful of scripts used to make the video capture process easier. To
ensure that you're ready to run these scripts:

1. Install the latest version of [Python 3](https://www.python.org/downloads/).
2. Install dependencies with `pip install -r requirements.txt`.
3. Use Git Bash (or another bash-compatible shell that has access to `cmd.exe`) to
   invoke [`./install-obs.sh`](./install-obs.sh). This will install and configure a
   local, portable installation of OBS.

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
 4. Under **Output** &rarr; **Recording**:
    - Set **Recording Path** to `..\..\..\capture`
    - Set **Recording Format** to `.mp4`
 5. Under **Video**:
    - Set both **Resolution** values to `1440x900`
    - Set the **FPS** value to `59.94`
 6. Confirm your settings changes and return to the main UI.
 7. From the menu bar, choose **Profile** &rarr; **Rename** and enter `VHS`.
 8. Choose **Scene Collection** &rarr; **Rename** and enter `VHS`.
 9. In the **Scenes** panel, rename the default Scene to `VHS`.
10. In the **Sources** panel, add a new **Video Capture Source** named `GV-USB2`, and:
    - For **Device**, choose `GV-USB2, Analog Capture`
    - Click **Configure Video**, and ensure that **VID DEINTERLACE METHOD** is set to
      `WEAVE`
11. Select the new **GV-USB2** source and press Ctrl-E to edit its transforms:
    - Set **Size** to `1440px` x `1080px`
12. Right-click the **GV-USB2** soure and choose **Deinterlacing** &rarr; **Yadif 2x**
13. Right-click the **GV-USB2** source and choose **Scale Filtering** &rarr; **Lanczos**
14. Arrange the UI as desired, ensuring that a point in the exact center of the
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
15. In the **Audio Mixer**, mute both the **Desktop Audio** and **Mic/Aux** inputs so
    that the only active input is **GV-USB2**.
16. Click the **Gear** button in the **Audio Mixer** to open the
    **Advanced Audio Properties** dialog, and:
    - For the **GV-USB2** input, set **Audio Monitoring** to `Monitor and Output`.
17. Play a tape and make a brief test recording. When you check the
    [`capture/`](./capture/) directory, you should have a new `.mp4` file that looks
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

OBS should be configured to write timestamped `.mp4` files into the `capture/`
directory. Once you've finished a tape, you can cut a new recording from your captured
footage.

### Cutting a new recording

To "cut" a recording, we simply grab all the clips recorded from OBS for a single tape,
and move them into a `storage/` directory, following a specific naming convention. You
can use the [`cut.py`](./cut.py) script to handle this process:

1. Verify that `capture/` contains only the clips for your desired tape
2. Run `python cut.py <tape-id>` to move those clips to `storage/<tape-id>`

For example, if we've finished recording two clips from tape 54, then we'll have a
couple of files that look something like this:

- `capture/2023-09-16 14-40-33.mp4`
- `capture/2023-09-16 15-02-20.mp4`

Running `python cut.py 54` will move those two files to:

- `storage/54/54_raw.001.mp4`
- `storage/54/54_raw.002.mp4`

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

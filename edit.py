import os
import io
import re
import sys
import subprocess
import argparse
from decimal import Decimal
from dataclasses import dataclass, asdict

from resolve_exec import resolve_exec


@dataclass
class InputVideoFile:
    path: str
    cut_frames: list[int]


def get_raw_footage(tape_id: str) -> list[str]:
    capture_dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'capture'))
    footage_root = os.path.join(capture_dir_path, tape_id)
    if not os.path.isdir(footage_root):
        raise RuntimeError('No such directory: %s' % footage_root)

    regex = re.compile(r'^' + tape_id + r'_raw\.\d{3}\.mkv$')
    raw_filenames = [f for f in os.listdir(footage_root) if regex.match(f)]
    return [os.path.join(footage_root, f) for f in sorted(raw_filenames)]


def timestamp_to_seconds(timestamp: str) -> Decimal:
    match = re.compile(r'^(\d{2}):(\d{2}):(\d{2})\.(\d{2})$').match(timestamp)
    if not match:
        raise ValueError('invalid timestamp: %s' % timestamp)

    hour = int(match[1])
    minute = int(match[2])
    second = int(match[3])
    whole_seconds = (hour * 3600) + (minute * 60) + second

    frac = Decimal('0.' + match[4])
    return Decimal(whole_seconds) + frac


def detect_cut_times(video_filepath: str, threshold: float) -> list[Decimal]:
    DURATION_REGEX = re.compile(r'^  Duration: (\d{2}:\d{2}:\d{2}\.\d{2}), start:.*$')
    PROGRESS_REGEX = re.compile(r'^frame=.*time=(\d{2}:\d{2}:\d{2}\.\d{2}).*$')
    CUT_FRAME_REGEX = re.compile(r'^\[Parsed_showinfo.*\spts_time:([^\s]+)\s.*$')

    times: list[Decimal] = []
    video_filter = "select='gt(scene,%f)',showinfo" % threshold
    args = ['ffmpeg', '-i', os.path.normpath(video_filepath), '-filter:v', video_filter, '-f', 'null', '-']

    filename = os.path.basename(video_filepath)
    duration_seconds: Decimal | None = None    
    
    print('Detecting cuts in %s (threshold: %0.3f)...' % (filename, threshold))
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in io.TextIOWrapper(p.stdout, encoding='utf-8'):
        duration_match = DURATION_REGEX.match(line)
        progress_match = PROGRESS_REGEX.match(line)
        cut_frame_match = CUT_FRAME_REGEX.match(line)
        assert (int(bool(duration_match)) + int(bool(progress_match)) + int(bool(cut_frame_match))) <= 1

        if duration_match:
            assert duration_seconds is None
            duration_seconds = timestamp_to_seconds(duration_match.group(1))
            assert duration_seconds > Decimal(0.0)
        elif progress_match:
            assert duration_seconds is not None
            timestamp = progress_match.group(1)
            position_seconds = timestamp_to_seconds(timestamp)
            progress_ratio = position_seconds / duration_seconds
            progress_pct = progress_ratio * Decimal(100.0)
            print('[%s @ %s]: %.2f%% finished (identified %d cut frames)' % (filename, timestamp, progress_pct, len(times)))
        elif cut_frame_match:
            seconds_str = cut_frame_match.group(1)
            times.append(Decimal(seconds_str))

    exitcode = p.wait()
    if exitcode != 0:
        raise RuntimeError("cut detection failed: ffmpeg returned exit code %d" % exitcode)
    return times


def collect_input_video_files(tape_id: str, detect_cuts: bool, cut_detection_threshold: float) -> list[InputVideoFile]:
    NTSC_DROP = Decimal('60000') / Decimal('1001')
    input_videos: list[InputVideoFile] = []
    for raw_video_filepath in get_raw_footage(tape_id):
        cut_frames: list[int] = []
        if detect_cuts:
            cut_times = detect_cut_times(raw_video_filepath, cut_detection_threshold)
            cut_frames = sorted(set([round(time * NTSC_DROP) for time in cut_times]))
        input_videos.append(InputVideoFile(
            path=raw_video_filepath,
            cut_frames=cut_frames,
        ))
    return input_videos


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python edit.py', description='prepares a DaVinci Resolve project for editing/trimming the footage captured from a VHS tape')
    parser.add_argument('tape_id', help='tape for which footage has been captured and placed in capture/<tape-id>/<tape-id>_raw.###.mkv')
    parser.add_argument('--detect-cuts', '-c', action='store_true', help='Use ffmpeg to detect cut frames and add markers to clips in Resolve')
    parser.add_argument('--cut-detection-threshold', '-t', type=float, default=0.2, help='threshold scene change detection score (sum of absolute differences between frames); lower is more sensitive')
    args = parser.parse_args()

    videos = collect_input_video_files(args.tape_id, args.detect_cuts, args.cut_detection_threshold)
    if not videos:
        raise RuntimeError('No input video files found for tape %s' % args.tape_id)

    gvcr_resolve = os.path.join(os.path.dirname(__file__), 'gvcr_resolve')
    script = 'create_vhs_project(resolve, %r, %r)' % (args.tape_id, [asdict(v) for v in videos])
    resolve_exec(gvcr_resolve, script)

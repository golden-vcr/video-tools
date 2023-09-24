import os
import io
import re
import sys
import time
import json
import tempfile
import binascii
import subprocess
import argparse
from decimal import Decimal

from resolve_exec import resolve_exec


def timecode_to_seconds(timecode: str) -> Decimal:
    match = re.compile(r'^(\d{2}):(\d{2}):(\d{2})\:(\d{2})$').match(timecode)
    if not match:
        raise ValueError('invalid timecode value: %s' % timecode)

    NTSC_FULL = Decimal('60')
    NTSC_DROP = Decimal('60000') / Decimal('1001')

    hour = int(match[1])
    minute = int(match[2])
    second = int(match[3])
    frame = int(match[4])

    # Resolve uses non-drop-frame timecode, but ffmpeg interprets our 59.94 footage
    # with drop-frame timecode, so we need to convert to seconds assuming 60 fps, then
    # divide by 0.999 (i.e. 59.94 / 60) to scale up to drop-frame timecode
    assumed_framerate = NTSC_FULL
    whole_seconds = (hour * 3600) + (minute * 60) + second
    frac = Decimal(frame) / Decimal(assumed_framerate)
    second_at_assumed_framerate = Decimal(whole_seconds) + frac

    return second_at_assumed_framerate / (NTSC_DROP / NTSC_FULL)


def get_keyframe_times(video_filepath: str) -> list[Decimal]:
    KEYFRAME_TIME_REGEX = re.compile(r'^([0-9.]+),K.*')
    
    args = ['ffprobe', '-loglevel', 'error', '-select_streams', 'v:0', '-show_entries', 'packet=pts_time,flags', '-of', 'csv=print_section=0', os.path.normpath(video_filepath)]
    times: list[Decimal] = []
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in io.TextIOWrapper(p.stdout, encoding='utf-8'):
        match = KEYFRAME_TIME_REGEX.match(line)
        if match:
            times.append(Decimal(match.group(1)))

    exitcode = p.wait()
    if exitcode != 0:
        raise RuntimeError("getting keyframe times failed: ffprobe returned exit code %d" % exitcode)
    return times


def find_nearest_keyframe_lte(keyframe_times: list[Decimal], second: Decimal) -> Decimal:
    left = 0
    right = len(keyframe_times) - 1
    result = None
    while left <= right:
        mid = (left + right) // 2
        if keyframe_times[mid] <= second:
            result = keyframe_times[mid]
            left = mid + 1
        else:
            right = mid - 1
    return result


def trim_without_reencode(src_filepath: str, dst_filepath: str, in_timecode: str, out_timecode: str, keyframe_times: list[Decimal]):
    # Since we're stream-copying an H.264 video stream, we need to go back to the
    # nearest keyframe before our desired in point, adding a little bit of lead time to
    # the segment we want to trim
    desired_in_point = timecode_to_seconds(in_timecode)
    in_point = find_nearest_keyframe_lte(keyframe_times, desired_in_point)
    assert in_point is not None

    # Trim from there to desired out point
    out_point = timecode_to_seconds(out_timecode)
    duration = out_point - in_point

    # Invoke ffmpeg to render our trimmed video, just copying a portion of the video
    # and audio streams into a new container rather than reencoding
    args = [
        'ffmpeg',
        '-ss', str(in_point),
        '-i', src_filepath,
        '-t', str(duration),
        '-map', '0',
        '-c', 'copy',
        dst_filepath,
    ]
    print('> %s' % ' '.join(args))
    subprocess.check_call(args)


def trim_with_x264_reencode(src_filepath: str, dst_filepath: str, in_timecode: str, out_timecode: str, crf: int):
    # Given timecode exported from Resolve, convert to the exact times in the input
    # video where we want to start and end our clip
    in_point = timecode_to_seconds(in_timecode)
    out_point = timecode_to_seconds(out_timecode)
    duration = out_point - in_point

    # Invoke ffmpeg to render our trimmed video, re-encoding with libx264 with
    # sufficient bitrate that the quality loss is imperceptible/tolerable
    args = [
        'ffmpeg',
        '-ss', str(in_point),
        '-i', src_filepath,
        '-t', str(duration),
        '-map', '0',
        '-c:v', 'libx264',
        '-preset', 'slow',
        '-crf', str(crf),
        '-c:a', 'copy',
        dst_filepath,
    ]
    print('> %s' % ' '.join(args))
    subprocess.check_call(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python trim.py', description='examines the current timeline in DaVinci resolve and exports clips using ffmpeg')
    parser.add_argument('--copy', '-c', action='store_true', help='copy video streams rather than re-encoding (faster and no quality loss, but pads out start of video to nearest keyframe)')
    parser.add_argument('--crf', '-crf', type=int, default=10, help='CRF for libx264 reencodes, only used when --copy is not passed (lower is higher quality, higher file size)')
    args = parser.parse_args()

    # Establish a temporary working directory so we can communicate between this
    # process and our script running in Resolve with basic file I/O
    with tempfile.TemporaryDirectory() as tempdir:
        # Create an isolated directory, and construct the path to the output file that
        # we want our Resolve script to write (but don't create the file)
        random_suffix = binascii.b2a_hex(os.urandom(4)).decode('ascii')
        dst_dirpath = os.path.join(tempdir, 'resolve_%s' % random_suffix)
        os.mkdir(dst_dirpath)
        dst_filepath = os.path.join(dst_dirpath, 'out.json')

        # Kick off execution of our export_vhs_project_to_json script in Resolve
        gvcr_resolve = os.path.join(os.path.dirname(__file__), 'gvcr_resolve')
        script = 'export_vhs_project_to_json(resolve, %r)' % dst_filepath
        resolve_exec(gvcr_resolve, script)

        # Continually check to see whether Resolve has written the file yet
        print('Waiting for output from Resolve script to be written to: %s' % dst_filepath)
        timeout = 2.0
        start = time.time()
        while True:
            time.sleep(0.1)
            if os.path.isfile(dst_filepath):
                # Once the file exists, wait a beat so ensure it's finished
                time.sleep(1.0)
                break

            elapsed = time.time() - start
            if elapsed > timeout:
                raise RuntimeError('Timed out waiting for output from Resolve script')
        
        # Parse the data from the file before our temp directory is cleaned up
        with open(dst_filepath) as fp:
            data = json.load(fp)

    # Run an intial loop to collect the set of input video files
    tape_id = data['name']
    src_filepaths = {clip['src_filepath'] for clip in data['clips']}

    # If we're copying video streams without reencoding, analyze each input video file
    # to determine where all the keyframes are
    keyframe_times_by_src_filepath = {}
    if args.copy:
        for src_filepath in sorted(src_filepaths):
            print('Finding keyframe times in %s...' % os.path.basename(src_filepath))
            keyframe_times_by_src_filepath[src_filepath] = get_keyframe_times(src_filepath)

    # Prepare an output directory
    dst_dirpath = os.path.join(os.path.dirname(__file__), 'storage', tape_id)
    os.makedirs(dst_dirpath, exist_ok=True)

    # Iterate over each clip from our Resolve timeline, and export a separate video for
    # each clip
    for clip in data['clips']:
        src_filepath = clip['src_filepath']
        dst_filename = clip['dst_filename']
        in_timecode = clip['in_timecode']
        out_timecode = clip['out_timecode']

        dst_filepath = os.path.join(dst_dirpath, dst_filename)
        if args.copy:
            keyframe_times = keyframe_times_by_src_filepath[src_filepath]
            trim_without_reencode(src_filepath, dst_filepath, in_timecode, out_timecode, keyframe_times)
        else:
            trim_with_x264_reencode(src_filepath, dst_filepath, in_timecode, out_timecode, args.crf)

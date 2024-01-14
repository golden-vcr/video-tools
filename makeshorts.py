import os
import argparse
import requests
from datetime import datetime

from resolve_exec import resolve_exec


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python makeshorts.py', description='prepares a DaVinci Resolve project for cutting shorts from an OBS broadcast of a Golden VCR stream')
    parser.add_argument('broadcast_id', help='id for the broadcast, corresponding to ../../gvcr-stream-capture/gvcr_broadcast_<broadcast-id>.mkv')
    args = parser.parse_args()

    stream_capture_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'gvcr-stream-capture'))
    mkv_filepath = os.path.join(stream_capture_root, 'gvcr_broadcast_%s.mkv' % args.broadcast_id)
    if not os.path.isfile(mkv_filepath):
        raise ValueError('No such file: %s' % mkv_filepath)

    broadcast_history_url = 'https://goldenvcr.com/api/showtime/history/%s' % args.broadcast_id
    r = requests.get(broadcast_history_url)
    if not r.ok:
        raise RuntimeError('GET %s failed with status %d' % (broadcast_history_url, r.status_code))
    broadcast = r.json()
    broadcast_start = datetime.strptime(broadcast['startedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')

    markers = []
    marker_fudge_seconds = -20
    for screening in broadcast['screenings']:
        screening_start = datetime.strptime(screening['startedAt'], '%Y-%m-%dT%H:%M:%S.%fZ')
        marker_second = max(0, (screening_start - broadcast_start).total_seconds() + marker_fudge_seconds)
        marker_frame = round(marker_second * 60)
        marker_text = 'Tape %d' % screening['tapeId']
        markers.append((marker_frame, marker_text))

    gvcr_resolve = os.path.join(os.path.dirname(__file__), 'gvcr_resolve')
    script = 'create_shorts_project(resolve, %r, %r)' % (mkv_filepath, markers)
    resolve_exec(gvcr_resolve, script)

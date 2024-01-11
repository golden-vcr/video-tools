import os
import argparse

from resolve_exec import resolve_exec


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python makeshorts.py', description='prepares a DaVinci Resolve project for cutting shorts from an OBS broadcast of a Golden VCR stream')
    parser.add_argument('broadcast_id', help='id for the broadcast, corresponding to ../../gvcr-stream-capture/gvcr_broadcast_<broadcast-id>.mkv')
    args = parser.parse_args()

    stream_capture_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'gvcr-stream-capture'))
    mkv_filepath = os.path.join(stream_capture_root, 'gvcr_broadcast_%s.mkv' % args.broadcast_id)
    if not os.path.isfile(mkv_filepath):
        raise ValueError('No such file: %s' % mkv_filepath)

    gvcr_resolve = os.path.join(os.path.dirname(__file__), 'gvcr_resolve')
    script = 'create_shorts_project(resolve, %r)' % mkv_filepath
    resolve_exec(gvcr_resolve, script)

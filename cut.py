import os
import re
import sys
import argparse

CAPTURE_FILENAME_REGEX = re.compile('\d{4}-\d{2}-\d{2} \d{2}-\d{2}-\d{2}\.mkv', re.IGNORECASE)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='python cut.py', description='renames captured footage for a single tape, collecting it in capture/<tape-id>/<tape-id>_raw.###.mkv')
    parser.add_argument('tape_id', help='tape id associated with all the loose .mkv files in the capture/ dir')
    args = parser.parse_args()

    dst_dirpath = os.path.join('capture', args.tape_id)
    if os.path.isdir(dst_dirpath):
        print('ERROR: Can not cut new recording to %s; directory already exists' % dst_dirpath)
        sys.exit(1)

    src_filenames = [f for f in os.listdir('capture') if CAPTURE_FILENAME_REGEX.match(f)]
    if not src_filenames:
        print('ERROR: No input files in capture directory; unable to cut recording to %s' % dst_dirpath)
        sys.exit(1)

    os.mkdir(dst_dirpath)

    print('Cutting %s...' % args.tape_id)

    move_operations = []
    for i, src_filename in enumerate(sorted(src_filenames)):
        dst_filename = '%s_raw.%03d.mkv' % (args.tape_id, i)
        src_filepath = os.path.join('capture', src_filename)
        dst_filepath = os.path.join(dst_dirpath, dst_filename)
        move_operations.append((src_filepath, dst_filepath))
    
    for src_filepath, dst_filepath in move_operations:
        print('%s --> %s' % (src_filepath, dst_filepath))
        os.rename(src_filepath, dst_filepath)
    
    print('Cut new recording to %s from %d captured video files.' % (dst_dirpath, len(src_filenames)))

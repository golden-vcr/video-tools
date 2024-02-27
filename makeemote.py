import os
import argparse

from imglib import Align
from imglib.framecrop import crop_frames
from imglib.frameresize import resize_frames
from imglib.gifrender import render_gif

EMOTES_ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'emotes'))
SIZES = [128, 112, 56, 28]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('emote_name')
    parser.add_argument('--align', '-a', choices=Align.choices, default='middle')
    parser.add_argument('--frameskip', '-s', type=int, default=1)
    parser.add_argument('--frameshift', '-t', type=int, default=0)
    parser.add_argument('--matte', '-m', default='#181818')
    parser.add_argument('--fps', '-r', type=int, default=20)
    args = parser.parse_args()
    align = Align.parse(args.align)

    print('Emote: %s' % args.emote_name)
    emote_dir = os.path.join(EMOTES_ROOTDIR, args.emote_name)
    assert os.path.isdir(emote_dir)
    print('Working from: %s' % emote_dir)
    
    render_dir = os.path.join(emote_dir, 'render')
    crop_dir = os.path.join(emote_dir, 'crop')
    resize_dir = os.path.join(emote_dir, 'resize')

    if os.path.isdir(render_dir) and not os.path.isdir(crop_dir):
        print('Cropping rendered frames...')
        crop_frames(render_dir, crop_dir, args.emote_name)
        print('Wrote cropped images to %s.' % crop_dir)

    assert os.path.isdir(crop_dir)
    for size in SIZES:
        output_dir = os.path.join(resize_dir, str(size))
        print('Resizing all cropped frames to to %dx%d...' % (size, size))
        resize_frames(crop_dir, output_dir, size, align)
        print('Wrote resized images to %s.' % output_dir)

    for size in SIZES:
        input_dir = os.path.join(resize_dir, str(size))
        gif_path = os.path.join(emote_dir, '%s_%d.gif' % (args.emote_name, size))
        print('Rendering an animated GIF at %dx%d...' % (size, size))
        render_gif(input_dir, gif_path, args.frameskip, args.frameshift, args.matte, args.fps)
        print('Wrote %s.' % gif_path)

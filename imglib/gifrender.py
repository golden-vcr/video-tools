import os
import shutil
import subprocess
from contextlib import contextmanager

import cv2
import numpy as np


def render_gif(input_dirpath: str, output_filepath: str, frameskip: int, frameshift: int, matte_color: str, fps: int):
    """
    Assembles a GIF from all images in input_dirpath, writing the resulting file to
    output_filepath. If frameshift if nonzero, the sequence will begin that many frames
    in from zero. If frameskip is nonzero, that many frames will be skipped for each
    frame rendered. matte_color indicates the desired background color, to preserve
    anti-aliasing (as a fringe) when rendered to a GIF with 1-bit alpha.

    TODO: fps involves weird ffpmeg magic and doesn't actually directly specify playback
    framerate; a sensible default value is somewhere around 20.
    """
    # Parse the input color as RGB hex, then convert it to normalized BGR
    assert len(matte_color) == 7 and matte_color[0] == '#'
    matte_r, matte_g, matte_b = int(matte_color[1:3], 16), int(matte_color[3:5], 16), int(matte_color[5:7], 16)
    bg_color_float = (matte_b / 255.0, matte_g / 255.0, matte_r / 255.0)

    # Create a temp directory to contain processed versions of the frames we want to
    # assemble a GIF from
    temp_frames_dirpath = output_filepath + '.tmp'
    with _tempdir(temp_frames_dirpath, delete=True):
        # Apply the desired skip and shift values to narrow down our set of input frames
        filenames = sorted(os.listdir(input_dirpath))
        for i in range(frameshift):
            filenames.append(filenames.pop(0))
        filenames = filenames[::1+frameskip]
        filepaths = [os.path.join(input_dirpath, f) for f in filenames]
        assert filepaths

        # Iterate over the input frames, renumbering them starting from 0 and getting
        # them ready to assemble into a GIF
        for i, filepath in enumerate(filepaths):
            temp_frame_filepath = os.path.join(temp_frames_dirpath, 'frame%04d.png' % i)

            # Read the input image and extract its original alpha channel
            im = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
            alpha = im[:,:,3]

            # Invert the alpha channel, normalize it to 0..1, then multiply it with the
            # desired background color to get a cutout of our background that can be
            # added to the original RGB values
            bg_mask = (255 - alpha).astype(float) / 255.0
            bg_mask_rgb = cv2.merge((bg_mask, bg_mask, bg_mask))
            bg = (bg_mask_rgb * bg_color_float * 255.0).astype(np.uint8)
            bg = cv2.cvtColor(bg, cv2.COLOR_RGB2RGBA)
            
            # Add our background cutout to the original image to get our final RGB
            # values, then convert the original alpha-channel to a 1-bit mask: for every
            # pixel in the input image where 0.0 < opacity < 1.0, we'll end up with a
            # fully opaque pixel with a fringe that encompasses the anti-aliasing
            # required to make our image look good on the desired background color
            temp_frame = cv2.add(bg, im)
            temp_frame[:,:,3] = (alpha != 0).astype(np.uint8) * 255

            # Save our modified frame to the temporary directory for this GIF file
            cv2.imwrite(temp_frame_filepath, temp_frame)

        # Use ffmpeg to render a .gif image from our frames
        subprocess.check_call([
            'ffmpeg',
            '-i', os.path.join(temp_frames_dirpath, r'frame%04d.png'),
            '-vf', 'fps=%d,split[s0][s1];[s0]palettegen=reserve_transparent=1[p];[s1][p]paletteuse' % fps,
            '-y',
            output_filepath,
        ])


@contextmanager
def _tempdir(path: str, delete: bool):
    os.makedirs(path, exist_ok=True)
    try:
        yield
    finally:
        if delete:
            shutil.rmtree(path)

import os
from typing import Sequence

import cv2
import numpy as np

from .core import Box


def crop_frames(input_dirpath: str, output_dirpath: str, output_filename_prefix: str):
    """
    Collects all frame images in input_dirpath, computes a bounding box that will fit
    the full extents of every frame's alpha channel, then crops each frame to that box
    and writes it to output_dirpath as '<output_filename_prefix>.####.png', with the
    first frame starting at 0000.
    """
    # Get a list of frames in the input directory (which we assume to only contain
    # per-frame images; no other files or directories)
    filenames = sorted(os.listdir(input_dirpath))
    filepaths = [os.path.join(input_dirpath, f) for f in filenames]

    # Compute a bounding box that encompasses the alpha channel of all frames
    box = _get_box_from_frames(filepaths)

    # Create the output directory if it doesn't exist, then write a copy of each frame,
    # cropped to that bounding box
    os.makedirs(output_dirpath, exist_ok=True)
    for i, input_filepath in enumerate(filepaths):
        # Figure out where to write our output file, using a naming convention that
        # renumbers all frames starting from 0
        output_filename = '%s.%04d.png' % (output_filename_prefix, i)
        output_filepath = os.path.join(output_dirpath, output_filename)

        # Open the original frame, crop it, and write it to our output path
        im = cv2.imread(input_filepath, cv2.IMREAD_UNCHANGED)
        im = im[box.y:box.y+box.h, box.x:box.x+box.w]
        cv2.imwrite(output_filepath, im)


def _get_box_from_frames(filepaths: Sequence[str]) -> Box:
    # We should have at least one input image in the sequence
    assert filepaths

    # Iterate over all frames to find the widest bounding box that covers them all
    min_left = 0x7fffffff
    min_top = 0x7fffffff
    max_right = -1
    max_bottom = -1
    for filepath in filepaths:
        # Read the frame, preserving (and requiring) an alpha channel
        im = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        assert im.ndim == 3 and im.shape[2] == 4
        alpha = im[:,:,3]

        # Compute a bounding box for this frame's alpha channel
        box = _get_box_from_alpha(alpha)
        right = box.x + box.w
        bottom = box.y + box.h

        # Grow our overall bounding box to encompass this frame
        if box.x < min_left:
            min_left = box.x
        if box.y < min_top:
            min_top = box.y
        if right > max_right:
            max_right = right
        if bottom > max_bottom:
            max_bottom = bottom
        
    # Return our final extents
    assert min_left != 0x7fffffff
    assert min_top != 0x7fffffff
    assert max_right != -1
    assert max_bottom != -1
    assert min_left <= max_right
    assert min_top <= max_bottom
    return Box(
        x=min_left,
        y=min_top,
        w=max_right - min_left,
        h=max_bottom - min_top,
    )


def _get_box_from_alpha(alpha: np.ndarray) -> Box:
    # We expect to be given a single image's alpha channel
    assert alpha.ndim == 2
    x, y, w, h = cv2.boundingRect(alpha)
    return Box(x=x, y=y, w=w, h=h)

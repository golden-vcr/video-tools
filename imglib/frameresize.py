import os

import cv2
import numpy as np

from .core import Align


def resize_frames(input_dirpath: str, output_dirpath: str, size: int, align: Align):
    """
    Collects all cropped frames in input_dirpath, then resizes each to a square image
    with the given size as both width and height, writing each resized frame to a file
    of the same name in output_dirpath. If align is Align.START, the image will be
    positioned at the top or left edge of the frame (for landscape or portrait aspect
    ratio, respectively); Align.MIDDLE corresponds to the center of the frame, and
    Align.END will place the image at the right or bottom edge of the frame.
    """
    # Get a list of frames in the input directory (which we assume to only contain
    # per-frame images; no other files or directories)
    filenames = sorted(os.listdir(input_dirpath))
    filepaths = [os.path.join(input_dirpath, f) for f in filenames]
    assert filepaths

    # Read the first frame to get the original, unmodified size of our input frames
    im = cv2.imread(filepaths[0], cv2.IMREAD_UNCHANGED)
    input_h, input_w, _ = im.shape

    # Determine the final size of our image once resized, and exactly how we should
    # shift it to fit in our square frame at the desired alignment
    resized_shift_x = 0
    resized_shift_y = 0
    if input_h > input_w:
        # Our image is tall, so it will occupy the full height of the resized image,
        # with its width scaled down at the same aspect ratio...
        resized_subject_h = size
        resized_subject_w = round(size * (input_w / input_h))
        assert resized_subject_w <= size

        # ...and we'll shift the image horizontally to position it at the start, middle,
        # or end of the X axis (i.e. left, center, or right)
        if align != Align.START:
            w_slack = size - resized_subject_w
            if align == Align.END:
                resized_shift_x = w_slack
            else:
                assert align == Align.MIDDLE
                resized_shift_x = w_slack // 2
    else:
        # Our image is wide, so it will occupy the full width of the resized image, with
        # its height scaled down at the same aspect ratio...
        resized_subject_w = size
        resized_subject_h = round(size * (input_h / input_w))
        assert resized_subject_h <= size

        # ...and we'll shift the image vertically to position it at the start, middle,
        # or end of the Y axis (i.e. top, middle, or bottom)
        if align != Align.START:
            h_slack = size - resized_subject_h
            if align == Align.END:
                resized_shift_y = h_slack
            else:
                assert align == Align.MIDDLE
                resized_shift_y = h_slack // 2
    
    # Iterate over all frames, resizing them to the desired dimensions and aligning them
    # as desired, then writing them to the output directory
    os.makedirs(output_dirpath, exist_ok=True)
    for input_filepath in filepaths:
        # In the output directory, use the same filename as the input file
        output_filepath = os.path.join(output_dirpath, os.path.basename(input_filepath))

        # Load the input image and resize it in its original aspect ratio
        im = cv2.imread(input_filepath, cv2.IMREAD_UNCHANGED)
        im = cv2.resize(im, (resized_subject_w, resized_subject_h), interpolation=cv2.INTER_AREA)

        # Create a new square buffer and blit the resized image into it
        resized = np.zeros((size, size, im.shape[2]), im.dtype)
        resized[resized_shift_y:resized_shift_y+resized_subject_h, resized_shift_x:resized_shift_x+resized_subject_w] = im
        cv2.imwrite(output_filepath, resized)

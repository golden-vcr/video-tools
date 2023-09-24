import os
import shutil
import tempfile
import binascii
import csv
import json


def create_vhs_project(resolve, tape_id, videos):
    # Verify that we have at least one input video file, and that each item is a dict
    # produced by the InputVideoFile dataclass defined in edit.py
    if not videos:
        raise RuntimeError('must have at least one video file to create a project')
    for video in videos:
        if 'path' not in video:
            raise ValueError('invalid format for InputVideoFile dict: must have a "path" attribute')
        if not isinstance(video['path'], str):
            raise ValueError('invalid format for InputVideoFile dict: "path" must be a string')
        if 'cut_frames' not in video:
            raise ValueError('invalid format for InputVideoFile dict: must have a "cut_frames" attribute')
        if not isinstance(video['cut_frames'], list):
            raise ValueError('invalid format for InputVideoFile dict: "cut_frames" must be a list')
        if not all([isinstance(x, int) for x in video['cut_frames']]):
            raise ValueError('invalid format for InputVideoFile dict: "cut_frames" must be a list of ints')
        if not os.path.isfile(video['path']):
            raise RuntimeError('invalid InputVideoFile: no such file exists at %s' % video['path'])
    
    # Find the blank project template that we copy and import to create our project,
    # since the Resolve scripting API doesn't fully support modifying project settings
    # like timeline playback framerate
    template_filename = '_resolve_1440x1080_5994.drp'
    template_drp_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', template_filename))
    if not os.path.isfile(template_drp_filepath):
        raise RuntimeError('resolve project template not found at: %s' % template_drp_filepath)

    # Copy that file to a new temp directory with the desired name of our project, then
    # import that project to create it in Resolve (using whatever Project Library is
    # active, since the scripting API doesn't let us access or select libraries)
    with tempfile.TemporaryDirectory() as tempdir:
        import_drp_filename = '%s.drp' % tape_id
        import_drp_filepath = os.path.join(tempdir, import_drp_filename)
        print('Copying %s as %s...' % (template_filename, import_drp_filename))
        shutil.copy(template_drp_filepath, import_drp_filepath)

        print('Importing a new project from %s...' % import_drp_filename)
        ok = resolve.GetProjectManager().ImportProject(import_drp_filepath)
        if not ok:
            raise RuntimeError('Failed to import project from %s' % import_drp_filepath)

    # Load our newly-created project
    print("Loading new project '%s'..." % tape_id)
    project = resolve.GetProjectManager().LoadProject(tape_id)
    if not project:
        raise RuntimeError('Failed to load project %s' % tape_id)

    # Import each of our clips, creating a MediaPoolItem for each one
    print("Importing clips...")
    video_file_paths = [v['path'] for v in videos]
    media_pool_items = resolve.GetMediaStorage().AddItemListToMediaPool(video_file_paths)
    assert len(media_pool_items) == len(video_file_paths)

    # The scripting API isn't clear about whether AddItemListToMediaPool preserves
    # ordering, but let's assume that it does and just verify with an assert: if this
    # assertion ever fails, then we need to re-sort media_pool_items
    for i, media_pool_item in enumerate(media_pool_items):
        expected_filename = os.path.basename(video_file_paths[i])
        assert media_pool_item.GetName() == expected_filename

    # Create a timeline in our project and populate it by adding each of our input
    # clips sequentially, and dropping in markers at the noted cut frames if supplied
    print('Preparing timeline for %s from %d video file(s)...' % (tape_id, len(videos)))
    media_pool = project.GetMediaPool()
    timeline = media_pool.CreateEmptyTimeline(tape_id)
    assert timeline

    for video, media_pool_item in zip(videos, media_pool_items):
        print('Adding %s with %d cut frame marker(s)...' % (media_pool_item.GetName(), len(video['cut_frames'])))
        ok = media_pool.AppendToTimeline(media_pool_item)
        assert ok
        timeline_item = timeline.GetItemListInTrack('video', 1)[-1]
        assert timeline_item.GetMediaPoolItem().GetMediaId() == media_pool_item.GetMediaId()
        for frame_id in video['cut_frames']:
            ok = timeline_item.AddMarker(frame_id, 'Sand', 'cut', '', 1)
            assert ok

    print('Ready for edit.')


def export_vhs_project_to_json(resolve, dst_filepath):
    # Grab the currently active project and timeline, and list all video clips in track 1
    project = resolve.GetProjectManager().GetCurrentProject()
    tape_id = project.GetName()
    timeline = project.GetCurrentTimeline()
    timeline_items = timeline.GetItemListInTrack('video', 1)

    # Make a first pass to validate that all clips are named appropriately, and to
    # validate that each clip has a valid source video file on disk
    for i, timeline_item in enumerate(timeline_items):
        clip_num = i + 1
        clip_slug = timeline_item.GetName()

        media_pool_item = timeline_item.GetMediaPoolItem()
        assert media_pool_item
        if clip_slug == media_pool_item.GetName():
            raise RuntimeError('video clip at index %d (%s) has not been renamed' % (i, clip_slug))

        filepath = media_pool_item.GetClipProperty('File Path')
        assert filepath
        assert os.path.isfile(filepath)

    # Export to CSV, then parse that CSV so we have the same data in-memory (bleh)
    csv_clips = [] # (clip_name, source_in, source_out)
    with tempfile.TemporaryDirectory() as tempdir:
        random_suffix = binascii.b2a_hex(os.urandom(4)).decode('ascii')
        csv_filename = '_%s_%s.csv' % (tape_id, random_suffix)
        csv_filepath = os.path.join(tempdir, csv_filename)
        ok = timeline.Export(csv_filepath, resolve.EXPORT_TEXT_CSV)
        assert ok

        with open(csv_filepath, 'r') as fp:
            reader = csv.DictReader(fp)
            video_clip_rows = [row for row in reader if row['V'] == 'V1']
            for row in video_clip_rows:
                csv_clips.append((row['Name'], row['Source In'], row['Source Out']))
    
    # Sanity-check that our CSV data lines up 1:1 with our video clips in the timeline
    assert len(csv_clips) == len(timeline_items)
    for csv_clip, timeline_item in zip(csv_clips, timeline_items):
        clip_name, _, _ = csv_clip
        assert timeline_item.GetName() == clip_name

    # Write everything to JSON
    data = {
        'type': 'vhs-project',
        'version': 1,
        'name': tape_id,
        'clips': [],
    }
    for i, timeline_item in enumerate(timeline_items):
        clip_name, source_in, source_out = csv_clips[i]
        data['clips'].append({
            'src_filepath': timeline_item.GetMediaPoolItem().GetClipProperty('File Path'),
            'dst_filename': '%s_%02d_%s.mp4' % (tape_id, i + 1, clip_name),
            'in_timecode': source_in,
            'out_timecode': source_out,
        })
    with open(dst_filepath, 'w') as fp:
        json.dump(data, fp, indent=4)

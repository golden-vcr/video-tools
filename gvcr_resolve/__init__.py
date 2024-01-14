import os
import re
import shutil
import tempfile
import datetime
import binascii
import csv
import json
import tempfile
import zipfile
import time


def _create_and_load_project_from_template(resolve, template_filename, project_name):
    # Find the blank project template that we copy and import to create our project,
    # since the Resolve scripting API doesn't fully support modifying project settings
    # like timeline playback framerate
    template_drp_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', template_filename))
    if not os.path.isfile(template_drp_filepath):
        raise RuntimeError('resolve project template not found at: %s' % template_drp_filepath)

    # Copy that file to a new temp directory with the desired name of our project, then
    # import that project to create it in Resolve (using whatever Project Library is
    # active, since the scripting API doesn't let us access or select libraries)
    with tempfile.TemporaryDirectory() as tempdir:
        import_drp_filename = '%s.drp' % project_name
        import_drp_filepath = os.path.join(tempdir, import_drp_filename)
        print('Copying %s as %s...' % (template_filename, import_drp_filename))
        shutil.copy(template_drp_filepath, import_drp_filepath)

        print('Importing a new project from %s...' % import_drp_filename)
        ok = resolve.GetProjectManager().ImportProject(import_drp_filepath)
        if not ok:
            raise RuntimeError('Failed to import project from %s' % import_drp_filepath)

    # Load our newly-created project
    print("Loading new project '%s'..." % project_name)
    project = resolve.GetProjectManager().LoadProject(project_name)
    if not project:
        raise RuntimeError('Failed to load project %s' % project_name)


def _transform_shorts_video_for_chat(video_item):
    video_item.SetProperty('ZoomX', 4.0)
    video_item.SetProperty('ZoomY', 4.0)
    video_item.SetProperty('Pan', -1620.0)
    video_item.SetProperty('Tilt', 800.0)


def _transform_shorts_video_for_face(video_item):
    video_item.SetProperty('ZoomX', 3.0)
    video_item.SetProperty('ZoomY', 3.0)
    video_item.SetProperty('Pan', -1210.0)
    video_item.SetProperty('Tilt', 330.0)
    video_item.SetProperty('CropBottom', 380.0)


def _transform_shorts_video_for_vcr(video_item):
    video_item.SetProperty('ZoomX', 1.375)
    video_item.SetProperty('ZoomY', 1.375)
    video_item.SetProperty('Pan', 186.0)


def _mutate_drp_to_extend_clip_duration(drp_filepath, video_item_name, duration):
    # Open the .drp file, which is a ZIP archive containing a few files describing the
    # Resolve project
    drp_tmp_filepath = drp_filepath + '.tmp'
    with zipfile.ZipFile(drp_filepath) as drp_file:
        # We should have exactly one timeline, with a corresponding
        # SeqContainer/<uuid>.xml file
        sequence_file_paths = [f for f in drp_file.namelist() if f.startswith('SeqContainer/') and f.endswith('.xml')]
        if len(sequence_file_paths) != 1:
            raise RuntimeError('Expected 1 SeqContainer/*.xml file in %s; got %d' % (drp_filepath, len(sequence_file_paths)))

        # Read the contents of that file, which should be an XML document
        sequence_file_path = sequence_file_paths[0]
        with drp_file.open(sequence_file_path) as sequence_file:
            sequence_file_data = sequence_file.read()

        # Process that XML document as plain-text, iterating line-by-line and changing
        # only the duration of the clip that matches the desired name
        has_seen_clip_name = False
        has_updated_clip_duration = False
        updated_lines = []
        sep = b'\r\n' if b'\r\n' in sequence_file_data else b'\n'
        for line in sequence_file_data.split(sep):
            line = line.decode()
            updated_line = line
            if not has_updated_clip_duration:
                if has_seen_clip_name:
                    if '<Duration>' in line and '</Duration>' in line:
                        updated_line = line[:line.index('>')+1] + str(duration) + '</Duration>'
                        has_updated_clip_duration = True
                else:
                    if ('<Name>%s</Name>' % video_item_name) in line:
                        has_seen_clip_name = True
            updated_lines.append(updated_line)
        updated_sequence_file_data = sep.join([s.encode() for s in updated_lines]) + sep

        # Write a new .drp ZIP file at a temporary location, replacing the original
        # timeline XML file with our updated version
        with zipfile.ZipFile(drp_tmp_filepath, 'w') as drp_tmp_file:
            for item in drp_file.infolist():
                if item.filename == sequence_file_path:
                    drp_tmp_file.writestr(item, updated_sequence_file_data)
                else:
                    drp_tmp_file.writestr(item, drp_file.read(item))

    # Replace the original .drp file with our new version
    os.remove(drp_filepath)
    os.rename(drp_tmp_filepath, drp_filepath)


def create_shorts_project(resolve, mkv_filepath, markers):
    # Ensure that we have a valid OBS recording of the desired broadcast
    if not os.path.isfile(mkv_filepath):
        raise ValueError('input mkv does not exist at %s' % mkv_filepath)
    work_dirpath, mkv_filename = os.path.split(mkv_filepath)

    # Resolve a path to the '_resolve_shortbars.png' file that contains black bars for
    # our facecam + branding overlay
    shortbars_png_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '_resolve_shortbars.png'))
    if not os.path.isfile(shortbars_png_filepath):
        raise ValueError('file not found: %s' % shortbars_png_filepath)

    # Parse the broadcast ID from the filename, falling back to a timestamp
    broadcast_id = datetime.datetime.now().strftime('%Y-%m-%d-%H%M')
    broadcast_id_match = re.compile(r'.*broadcast_(\d+)').match(mkv_filepath)
    if broadcast_id_match:
        broadcast_id = broadcast_id_match.group(1)
    print("Creating shorts project for broadcast %s..." % broadcast_id)
    
    # Open a new project with a resolution of 1080x1920 and a framerate of 60 FPS
    project_name = 'gvcrs_%s' % broadcast_id
    _create_and_load_project_from_template(resolve, '_resolve_1080x1920_60.drp', project_name)
    project = resolve.GetProjectManager().GetCurrentProject()

    # Import the recording of our broadcast
    print("Importing %s..." % mkv_filepath)
    new_media_pool_items = resolve.GetMediaStorage().AddItemListToMediaPool([mkv_filepath])
    assert len(new_media_pool_items) == 1
    media_pool_item = new_media_pool_items[0]

    # Import our shortbars PNG
    print("Importing %s..." % shortbars_png_filepath)
    new_media_pool_items = resolve.GetMediaStorage().AddItemListToMediaPool([shortbars_png_filepath])
    assert len(new_media_pool_items) == 1
    shortsbars_media_pool_item = new_media_pool_items[0]

    # Create a timeline to contain our entire broadcast, reoriented vertically
    timeline_name = 'gvcrs_%s' % broadcast_id
    print("Creating timeline: %s" % timeline_name)
    media_pool = project.GetMediaPool()
    timeline = media_pool.CreateEmptyTimeline(timeline_name)
    assert timeline

    # We'll have a single audio track for our recording's audio, then four video tracks:
    # - Video 4: PNG overlay containing black bars and branding
    # - Video 3: Video feed from VCR (leftmost 4:3 region of recording)
    # - Video 2: Face cam (4:3 region at top of right sidebar)
    # - Video 1: Chat (Lower region of right sidebar)
    ok = timeline.AddTrack('video') # Create Video 2
    assert ok
    ok = timeline.AddTrack('video') # Create Video 3
    assert ok
    ok = timeline.AddTrack('video') # Create Video 4
    assert ok

    # Add our video tracks, with Track 1 last - as soon as Track 1 contains any clips,
    # AppendToTimeline will append new clips at the end time of that track, rather than
    # at the beginning of the sequence, when called with an implicit startFrame
    print("Adding footage to timeline...")
    MEDIA_TYPE_VIDEO_ONLY = 1
    ok = media_pool.AppendToTimeline([{"mediaPoolItem": shortsbars_media_pool_item, "mediaType": MEDIA_TYPE_VIDEO_ONLY, "trackIndex": 4}])
    assert ok
    ok = media_pool.AppendToTimeline([{"mediaPoolItem": media_pool_item, "mediaType": MEDIA_TYPE_VIDEO_ONLY, "trackIndex": 3}])
    assert ok
    ok = media_pool.AppendToTimeline([{"mediaPoolItem": media_pool_item, "mediaType": MEDIA_TYPE_VIDEO_ONLY, "trackIndex": 2}])
    assert ok
    ok = media_pool.AppendToTimeline([{"mediaPoolItem": media_pool_item, "mediaType": MEDIA_TYPE_VIDEO_ONLY, "trackIndex": 1}])
    assert ok

    # Add the audio to track 1
    MEDIA_TYPE_AUDIO_ONLY = 2
    ok = media_pool.AppendToTimeline([{"mediaPoolItem": media_pool_item, "mediaType": MEDIA_TYPE_AUDIO_ONLY, "trackIndex": 1}])
    assert ok

    # We should now have a single shortbars graphic, a single audio clip, and three
    # identical video clips, all unlinked: get references to the corresponding
    # TimelineItems
    audio_1_items = timeline.GetItemListInTrack('audio', 1)
    video_1_items = timeline.GetItemListInTrack('video', 1)
    video_2_items = timeline.GetItemListInTrack('video', 2)
    video_3_items = timeline.GetItemListInTrack('video', 3)
    video_4_items = timeline.GetItemListInTrack('video', 4)
    assert len(audio_1_items) == 1
    assert len(video_1_items) == 1
    assert len(video_2_items) == 1
    assert len(video_3_items) == 1
    assert len(video_4_items) == 1
    audio_item = audio_1_items[0]
    chat_video_item = video_1_items[0]
    face_video_item = video_2_items[0]
    vcr_video_item = video_3_items[0]
    blackbars_video_item = video_4_items[0]

    # Transform each video clip so that the individual elements of the stream layout are
    # stacked vertically
    print("Applying video transforms to build vertical layout...")
    _transform_shorts_video_for_chat(chat_video_item)
    _transform_shorts_video_for_face(face_video_item)
    _transform_shorts_video_for_vcr(vcr_video_item)

    # Iterate through our list of (marker_frame, marker_text) pairs and create a marker
    # on the timeline to indicate where each tape starts
    print("Adding markers to indicate start of each tape...")
    for marker_frame, marker_text in markers:
        timeline.AddMarker(marker_frame, 'Sand', marker_text, '', 1)

    # We need to extend our _resolve_shortbars.png image overlay clip to match the
    # full duration of the timeline, but the Resolve scripting API does not let us set
    # the duration of a clip, so we need to export the entire project to .drp, modify
    # that .drp on disk to set the duration of our clip, then re-import the project
    project_name = project.GetName()
    project_manager = resolve.GetProjectManager()
    video_item_name = blackbars_video_item.GetName()
    duration = int(timeline.GetEndFrame()) - int(timeline.GetStartFrame())
    with tempfile.TemporaryDirectory() as temp_dirpath:
        # Export the project to disk so we can manipulate the timing of clips
        drp_filepath = os.path.join(temp_dirpath, '%s.drp' % project_name)
        print("Exporting to %s" % drp_filepath)
        project_manager.SaveProject()
        project_manager.ExportProject(project_name, drp_filepath)

        # Switch to a dummy project to unload the original project so we can delete it
        project_manager.LoadProject('_blank')

        # Delete the original project so we'll be able to reimport it with the same name
        project_manager.DeleteProject(project_name)

        # Modify the .drp so that the duration of our blackbars clip in this timeline is
        # extended to match the full duration of the timeline
        _mutate_drp_to_extend_clip_duration(drp_filepath, video_item_name, duration)

        # Import and reload the project from the modified .drp
        print("Re-importing from %s" % drp_filepath)
        project_manager.ImportProject(drp_filepath)
        project_manager.LoadProject(project_name)

    # Re-acquire references now that we've loaded a new project
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()
    audio_item = timeline.GetItemListInTrack('audio', 1)[0]
    chat_video_item = timeline.GetItemListInTrack('video', 1)[0]
    face_video_item = timeline.GetItemListInTrack('video', 2)[0]
    vcr_video_item = timeline.GetItemListInTrack('video', 3)[0]
    blackbars_video_item = timeline.GetItemListInTrack('video', 4)[0]

    # Link all our clips together so they can be edited as a single item
    ok = timeline.SetClipsLinked([
        blackbars_video_item,
        vcr_video_item,
        face_video_item,
        chat_video_item,
        audio_item,
    ], True)
    assert ok

    print('Ready for edit.')


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

    # Open a new project with a resolution of 1440x1080 and a framerate of 59.94 FPS
    _create_and_load_project_from_template(resolve, '_resolve_1440x1080_5994.drp', tape_id)

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

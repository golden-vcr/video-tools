import os
import re
import shutil
import tempfile


def get_raw_footage(tape_id):
    storage_dir_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'storage'))
    footage_root = os.path.join(storage_dir_path, tape_id)
    if not os.path.isdir(footage_root):
        raise RuntimeError('No such directory: %s' % footage_root)

    regex = re.compile(r'^' + tape_id + r'_raw\.\d{3}\.mp4$')
    raw_filenames = [f for f in os.listdir(footage_root) if regex.match(f)]
    return [os.path.join(footage_root, f) for f in sorted(raw_filenames)]


def populate_vhs_project(resolve):
    project = resolve.GetProjectManager().GetCurrentProject()
    tape_id = project.GetName()

    video_file_paths = get_raw_footage(tape_id)
    if not video_file_paths:
        print('No raw footage found for %s.' % tape_id)

    print('Preparing timeline for %s from %d clip(s)...' % (tape_id, len(video_file_paths)))

    clips = resolve.GetMediaStorage().AddItemListToMediaPool(video_file_paths)
    assert len(clips) == len(video_file_paths)

    media_pool = project.GetMediaPool()
    timeline = media_pool.CreateEmptyTimeline(tape_id)
    assert timeline

    for clip in clips:
        media_pool.AppendToTimeline(clip)

    print('Ready for edit.')


def create_vhs_project(resolve, tape_id):
    template_filename = '_resolve_1440x1080_5994.drp'
    template_drp_filepath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', template_filename))
    with tempfile.TemporaryDirectory() as tempdir:
        import_drp_filename = '%s.drp' % tape_id
        import_drp_filepath = os.path.join(tempdir, import_drp_filename)
        print('Copying %s as %s...' % (template_filename, import_drp_filename))
        shutil.copy(template_drp_filepath, import_drp_filepath)

        print('Importing a new project from %s...' % import_drp_filename)
        ok = resolve.GetProjectManager().ImportProject(import_drp_filepath)
        if not ok:
            raise RuntimeError('Failed to import project from %s' % import_drp_filepath)

    print("Loading new project '%s'..." % tape_id)
    project = resolve.GetProjectManager().LoadProject(tape_id)
    if not project:
        raise RuntimeError('Failed to load project %s' % tape_id)

    populate_vhs_project(resolve)


if __name__ == '__main__':
    populate_vhs_project(resolve)

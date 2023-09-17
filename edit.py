import os
import sys

from resolve_exec import resolve_exec


if __name__ == '__main__':
    tape_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not tape_id:
        print('Usage: python edit.py [tape-id]')
        sys.exit(1)

    gvcr_resolve = os.path.join(os.path.dirname(__file__), 'gvcr_resolve')
    resolve_exec(gvcr_resolve, "create_vhs_project(resolve, %r)" % tape_id)

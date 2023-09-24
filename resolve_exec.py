import os
import sys
import subprocess
from dataclasses import dataclass

import psutil
import win32con
import win32api
import win32gui
import win32process
import win32clipboard


def find_resolve_pid() -> int | None:
    result = None
    for p in psutil.process_iter():
        if p.name() == 'Resolve.exe':
            assert result is None
            result = p.pid
    return result            


def get_window_dimensions(hwnd: int) -> tuple[int, int]:
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    return width, height


@dataclass
class ResolveWindows:
    splash: int | None
    projects: int | None
    editor: int | None
    console: int | None

    def __bool__(self) -> bool:
        if self.splash or self.projects or self.editor or self.console:
            return True
        return False

    @classmethod
    def find(cls, resolve_pid) -> "ResolveWindows":
        def enum_windows_handler(hwnd: int, ctx: ResolveWindows):
            if win32gui.IsWindowVisible(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == resolve_pid:
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title == 'Resolve':
                        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                        if style & win32con.WS_BORDER == 0:
                            assert ctx.splash is None
                            ctx.splash = hwnd
                        else:
                            assert ctx.console is None
                            ctx.console = hwnd
                    elif window_title == 'Project Manager':
                        assert ctx.projects is None
                        ctx.projects = hwnd
                    elif window_title.startswith('DaVinci Resolve - '):
                        assert ctx.editor is None
                        ctx.editor = hwnd
                    elif window_title:
                        raise RuntimeError("Unexpected additional window for Resolve process: '%s'" % window_title)

        result = cls(splash=None, projects=None, editor=None, console=None)
        win32gui.EnumWindows(enum_windows_handler, result)
        return result


def get_resolve_install_dir() -> str:
    override_value = os.getenv('RESOLVE_INSTALL_DIR')
    if override_value:
        return override_value
    
    programfiles_root = os.getenv('PROGRAMFILES')
    assert programfiles_root
    return os.path.join(programfiles_root, 'Blackmagic Design', 'DaVinci Resolve')


def find_resolve_exe() -> str:
    install_dir = get_resolve_install_dir()
    resolve_exe_path = os.path.join(install_dir, 'Resolve.exe')
    if not os.path.isfile(resolve_exe_path):
        raise RuntimeError('Resolve.exe not found at %s: install Resolve or set RESOLVE_INSTALL_DIR' % install_dir)
    return resolve_exe_path


def launch_resolve() -> int:
    resolve_exe = find_resolve_exe()
    p = subprocess.Popen([resolve_exe], cwd=os.path.dirname(resolve_exe))
    return p.pid


def set_foreground_window(hwnd: int):
    num_attempts = 5
    for i in range(num_attempts):
        try:
            win32gui.SetForegroundWindow(hwnd)
            break
        except:
            if i == num_attempts - 1:
                raise
            win32api.Sleep(100)


def activate_resolve_editor_window() -> tuple[int, ResolveWindows]:
    # Check whether Resolve.exe is running: if not, launch it
    pid = find_resolve_pid()
    if not pid:
        pid = launch_resolve()
        print("Launching Resolve...")
    print("Resolve has PID %d" % pid)

    # Run a loop, periodically checking for windows associated with that PID
    solo_projects_hwnd: int | None = None
    for _ in range(500):
        # Wait a brief moment, then look for Resolve windows
        win32api.Sleep(100)
        hwnds = ResolveWindows.find(pid)

        # If we have no windows yet, do nothing this loop
        if not hwnds:
            continue

        # If we have a console without a main editor window, something's wrong
        if hwnds.console and not hwnds.editor:
            raise RuntimeError('Detected Resolve console window without main editor window')

        # If the splash screen is still up, wait a little longer and then try again
        if hwnds.splash:
            win32api.Sleep(500)
            continue

        # If the project manager is up but we already have a main editor window open,
        # close the project manager so the main editor will be the only window left on
        # our next iteration
        if hwnds.projects and hwnds.editor:
            print("Closing project manager window...")
            win32gui.PostMessage(hwnds.projects, win32con.WM_CLOSE, 0, 0)
            continue

        # If we've reached this point, we have either projects or editor, not both
        assert int(bool(hwnds.projects)) + int(bool(hwnds.editor)) == 1

        # If we have just the editor window, then we can activate it and return
        if hwnds.editor:
            print("Activating main editor window...")
            win32gui.ShowWindow(hwnds.editor, win32con.SW_SHOWMAXIMIZED)
            set_foreground_window(hwnds.editor)
            win32api.Sleep(100)
            return pid, hwnds

        # Otherwise, we just have the projects window: break out of this loop and into
        # another routine that'll get us from there to a solo editor window
        solo_projects_hwnd = hwnds.projects
        break
    
    # If we ended our loop without returning or breaking, then we timed out
    if not solo_projects_hwnd:
        raise RuntimeError("Timed out waiting for Resolve projects or editor window to appear")

    # We have a project manager window by itself: try clicking the "Open" button to
    # close the project manager and open a main editor window for whatever project was
    # already selected
    print("Activating solo project manager window...")
    win32gui.ShowWindow(solo_projects_hwnd, win32con.SW_SHOW)
    set_foreground_window(solo_projects_hwnd)

    # Send a LMB click event at the location of the "Open" button in the lower-right
    print("Clicking 'Open' to switch to main editor window...")
    width, height = get_window_dimensions(solo_projects_hwnd)
    click_pos = win32api.MAKELONG(width - 74, height - 31)
    win32gui.SendMessage(solo_projects_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, click_pos)
    win32gui.SendMessage(solo_projects_hwnd, win32con.WM_LBUTTONUP, 0, click_pos)

    # Spin in a final loop until we just have a main editor window and nothing else:
    for _ in range(500):
        win32api.Sleep(10)
        hwnds = ResolveWindows.find(pid)
        if hwnds.editor and not hwnds.projects and not hwnds.splash:
            print("Activating main editor window...")
            win32gui.ShowWindow(hwnds.editor, win32con.SW_SHOWMAXIMIZED)
            set_foreground_window(hwnds.editor)
            win32api.Sleep(100)
            return pid, hwnds

    # If we click and no main window ever shows up, something went wrong
    raise RuntimeError("Timed out waiting for Resolve project window to appear")


def simulate_click(hwnd: int, x: int, y: int):
    screen_pos = win32gui.ClientToScreen(hwnd, (x, y))
    win32api.SetCursorPos(screen_pos)
    win32api.Sleep(10)

    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    set_foreground_window(hwnd)

    client_pos = win32api.MAKELONG(x, y)
    win32api.Sleep(10)
    win32api.SendMessage(hwnd, win32con.WM_MOUSEMOVE, 0, client_pos)
    win32api.Sleep(10)
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, client_pos)
    win32api.Sleep(10)
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, client_pos)


def open_console_window(pid: int, editor_hwnd: int) -> ResolveWindows:
    # Click at the magic on-screen position where the 'Workspace' menu bar item is
    # (Resolve doesn't activate the menu on Alt), then arrow up twice to select the
    # 'Console' menu item, then press Enter
    print("Opening 'Workspace' -> 'Console' from menu bar...")
    simulate_click(editor_hwnd, 680, 8)
    win32gui.SendMessage(editor_hwnd, win32con.WM_KEYDOWN, win32con.VK_UP, 0)
    win32gui.SendMessage(editor_hwnd, win32con.WM_KEYDOWN, win32con.VK_UP, 0)
    win32gui.SendMessage(editor_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)

    # Wait until the console window appears
    for _ in range(100):
        win32api.Sleep(10)
        hwnds = ResolveWindows.find(pid)
        if hwnds.console:
            win32api.Sleep(400)
            return hwnds

    raise RuntimeError("Timed out waiting for Resolve console window to appear")


def close_console_window(pid: int, console_hwnd: int) -> ResolveWindows:
    print("Closing console window...")
    win32gui.PostMessage(console_hwnd, win32con.WM_CLOSE, 0, 0)
    for _ in range(100):
        win32api.Sleep(10)
        hwnds = ResolveWindows.find(pid)
        if not hwnds.console:
            return hwnds

    raise RuntimeError("Timed out waiting for Resolve console window to close")


def activate_python3_console_window(pid: int, hwnds: ResolveWindows) -> ResolveWindows:
    # If we already have a console, close it
    if hwnds.console:
        hwnds = close_console_window(pid, hwnds.console)
    
    # Open a fresh console window
    assert not hwnds.console and hwnds.editor
    hwnds = open_console_window(pid, hwnds.editor)
    assert hwnds.console

    # Send a click event to ensure that the 'Py3' button is selected
    print("Clicking on 'Py3' interpreter button...")
    simulate_click(hwnds.console, 270, 15)

    # Press Tab a couple of times to ensure that the text input has received focus
    print('Tabbing to text input field...')
    win32gui.SendMessage(hwnds.console, win32con.WM_KEYDOWN, win32con.VK_TAB, 0)
    win32gui.SendMessage(hwnds.console, win32con.WM_KEYDOWN, win32con.VK_TAB, 0)

    # Press Ctrl-A then Backspace, to clear the input
    win32api.Sleep(100)
    print('Clearing text input...')
    win32gui.SendMessage(hwnds.console, win32con.WM_KEYDOWN, win32con.VK_END, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.Sleep(10)
    win32gui.SendMessage(hwnds.console, win32con.WM_KEYDOWN, ord('A'), 0)
    win32api.Sleep(10)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.Sleep(100)
    win32gui.SendMessage(hwnds.console, win32con.WM_KEYDOWN, win32con.VK_BACK, 0)
    win32api.Sleep(10)

    return hwnds


def paste_text(text: str, hwnd: int):
    win32clipboard.OpenClipboard(None)
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32con.CF_TEXT)
    win32clipboard.CloseClipboard()

    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.Sleep(10)
    win32gui.SendMessage(hwnd, win32con.WM_KEYDOWN, ord('V'), 0)
    win32api.Sleep(10)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def resolve_exec(package_dirpath: str, expression: str):
    # Build a one-liner that we can execute in Resolve to run our desired script function
    parent_directory, package_name = os.path.split(package_dirpath)
    lines = [
        '__rx_dir = %r' % parent_directory,
        '__rx_modname = %r' % package_name,
        'sys.path = [__rx_dir] + [p for p in sys.path if p != __rx_dir]',
        '__rx_mod = importlib.import_module(__rx_modname)',
        'importlib.reload(__rx_mod)',
        'print(__rx_mod.%s)' % expression,
    ]
    script = '; '.join(lines)
    print(script)

    # Ensure that the Resolve script console is the active window, taking whatever
    # actions are needed to make that happen (launching Resolve, selecting a project,
    # opening the console window, etc.)
    pid, hwnds = activate_resolve_editor_window()
    hwnds = activate_python3_console_window(pid, hwnds)
    assert hwnds.console

    # Use the clipboard API to paste our text, then hit Enter to run it
    paste_text(script, hwnds.console)
    win32api.Sleep(100)
    win32gui.SendMessage(hwnds.console, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)

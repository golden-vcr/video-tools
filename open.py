import os
import subprocess
import re
import sys

import win32api
import win32con
import win32gui
import win32process

OBS_WINDOW_TITLE_REGEX = re.compile(r'^OBS \d+\.\d+\.\d+ - Portable Mode - Profile: VHS - Scenes: VHS$')
OBS_PREVIEW_CLICK_POS_X = 0.75
OBS_PREVIEW_CLICK_POS_Y = 0.4

PROJECTOR_WINDOW_SIZE_W = 1440 + 16
PROJECTOR_WINDOW_SIZE_H = 1080 + 39


def find_obs_window():
    def enum_windows_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            match = OBS_WINDOW_TITLE_REGEX.match(window_title)
            if match:
                assert not ctx[0]
                ctx[0] = hwnd

    result = [None]
    win32gui.EnumWindows(enum_windows_handler, result)
    return result[0]


def find_projector_window(obs_hwnd):
    _, obs_pid = win32process.GetWindowThreadProcessId(obs_hwnd)

    def enum_windows_handler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            window_title = win32gui.GetWindowText(hwnd)
            if window_title == 'Windowed Projector (Preview)':
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == obs_pid:
                    assert not ctx[0]
                    ctx[0] = hwnd

    result = [None]
    win32gui.EnumWindows(enum_windows_handler, result)
    return result[0]


def activate_window(hwnd):
    win32gui.ShowWindow(hwnd, win32con.SW_SHOWMAXIMIZED)
    win32gui.SetForegroundWindow(hwnd)


def launch_obs():
    obs_exe_path = os.path.join(os.path.dirname(__file__), 'obs', 'bin', '64bit', 'obs64.exe')
    assert os.path.isfile(obs_exe_path)

    subprocess.Popen([obs_exe_path], cwd=os.path.dirname(obs_exe_path))

    for i in range(100):
        win32api.Sleep(100)
        obs_hwnd = find_obs_window()
        if obs_hwnd:
            win32api.Sleep(100)
            return obs_hwnd

    raise RuntimeError('Failed to launch OBS')


def open_obs_preview_context_menu(obs_hwnd):
    rect = win32gui.GetWindowRect(obs_hwnd)
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    
    x = int(width * OBS_PREVIEW_CLICK_POS_X)
    y = int(height * OBS_PREVIEW_CLICK_POS_Y)
    pos = win32api.MAKELONG(x, y)
    win32gui.SendMessage(obs_hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, pos)
    win32gui.SendMessage(obs_hwnd, win32con.WM_RBUTTONUP, 0, pos)


def open_obs_projector_window(obs_hwnd):
    open_obs_preview_context_menu(obs_hwnd)

    for i in range(5):
        win32gui.SendMessage(obs_hwnd, win32con.WM_KEYDOWN, win32con.VK_DOWN, 0)
    win32gui.SendMessage(obs_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)

    for i in range(100):
        win32api.Sleep(10)
        projector_hwnd = find_projector_window(obs_hwnd)
        if projector_hwnd:
            return projector_hwnd
    
    raise RuntimeError('Failed to open OBS projector window')


if __name__ == '__main__':
    obs_hwnd = find_obs_window()
    if not obs_hwnd:
        obs_hwnd = launch_obs()
    assert obs_hwnd

    projector_hwnd = find_projector_window(obs_hwnd)
    if not projector_hwnd:
        activate_window(obs_hwnd)
        projector_hwnd = open_obs_projector_window(obs_hwnd)
    assert projector_hwnd

    win32gui.SetWindowPos(projector_hwnd, obs_hwnd, 0, 0, PROJECTOR_WINDOW_SIZE_W, PROJECTOR_WINDOW_SIZE_H, 0)

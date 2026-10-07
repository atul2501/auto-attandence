"""Runs in the background from the Startup folder.

- On login: punch in (once per day).
- On shutdown / restart / sign-out: holds Windows for a few seconds and punches out.
"""
import ctypes
import threading
import time
from ctypes import wintypes

import punch

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_QUERYENDSESSION = 0x0011
WM_ENDSESSION = 0x0016


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
user32.ShutdownBlockReasonCreate.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.ShutdownBlockReasonDestroy.argtypes = [wintypes.HWND]

last_punch_out = 0.0


def wnd_proc(hwnd, msg, wparam, lparam):
    global last_punch_out
    if msg == WM_QUERYENDSESSION:
        # Windows may ask more than once during one shutdown - punch only once
        if time.time() - last_punch_out > 60:
            last_punch_out = time.time()
            punch.log.info("Windows is shutting down - punching out")
            user32.ShutdownBlockReasonCreate(hwnd, "Punching out of HRM attendance...")
            try:
                punch.punch("out", attempts=2, wait_net=0)
            except Exception:
                punch.log.exception("Punch out crashed")
            user32.ShutdownBlockReasonDestroy(hwnd)
        return 1  # allow shutdown
    if msg == WM_ENDSESSION:
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def main():
    # Only one copy may run
    kernel32.CreateMutexW(None, False, "Local\\FTS_AutoPunch")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return

    # Ask Windows to notify us before most other apps at shutdown
    kernel32.SetProcessShutdownParameters(0x3FF, 0)

    proc = WNDPROC(wnd_proc)
    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASSW(lpfnWndProc=proc, hInstance=hinst, lpszClassName="FTSAutoPunch")
    user32.RegisterClassW(ctypes.byref(wc))
    # Hidden top-level window (message-only windows don't get shutdown messages)
    hwnd = user32.CreateWindowExW(0, "FTSAutoPunch", "FTS Auto Punch", 0,
                                  0, 0, 0, 0, None, None, hinst, None)
    if not hwnd:
        punch.log.error("Could not create window: %d", ctypes.get_last_error())
        return

    threading.Thread(target=punch.punch, args=("in",), daemon=True).start()

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    main()

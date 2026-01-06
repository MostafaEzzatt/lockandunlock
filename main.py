from pynput import keyboard, mouse
import threading

# Debug flag - set to True to log key events
DEBUG = False

# State variable
mouse_lock_listener = None

def lock_mouse():
    global mouse_lock_listener

    if mouse_lock_listener is None:
        # Start a listener that suppresses all mouse events
        mouse_lock_listener = mouse.Listener(suppress=True)
        mouse_lock_listener.start()
        # print("Mouse LOCKED (Input Suppressed). Press Ctrl+Alt+U to UNLOCK.")
    else:
        # print("Mouse is already LOCKED.")
        pass


def unlock_mouse():
    global mouse_lock_listener

    if mouse_lock_listener is not None:
        # Stop the listener to restore mouse control
        mouse_lock_listener.stop()
        mouse_lock_listener = None
        # print("Mouse UNLOCKED.")
    else:
        # print("Mouse is not locked.")
        pass

# --- Keyboard lock state and helpers ---
keyboard_lock_listener = None
keyboard_auto_unlock_timer = None
keyboard_pressed = set()
AUTO_UNLOCK_SECONDS = 30


def _key_name(key):
    """Map pynput key objects to simple names we care about in a robust way.

    Handles: keyboard.Key modifiers, KeyCode.char, and KeyCode.vk (virtual-key codes)
    where some platforms provide numeric vk values (e.g., 85 for 'U').
    """
    # Key (modifier) instances
    if isinstance(key, keyboard.Key):
        if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return 'ctrl'
        if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, getattr(keyboard.Key, 'alt_gr', None)):
            # include alt_gr where available
            return 'alt'
        return None

    # KeyCode (regular character) instances
    try:
        ch = getattr(key, 'char', None)
        if ch:
            return ch.lower()
    except Exception:
        pass

    # Some platforms expose a virtual-key code on KeyCode objects (e.g., vk=85 for 'U').
    vk = getattr(key, 'vk', None)
    try:
        if isinstance(vk, int):
            # Map ASCII letter VKs (A-Z) to lowercase letters
            if 65 <= vk <= 90:
                return chr(vk).lower()
            # Map lowercase ASCII if present
            if 97 <= vk <= 122:
                return chr(vk)
    except Exception:
        pass

    return None


def _on_key_press(key):
    name = _key_name(key)
    if DEBUG:
        print(f"[DEBUG] key press: {key!r} -> {name}")
    if name:
        keyboard_pressed.add(name)
    else:
        # Fallback: sometimes char is not available; inspect repr for letter hints
        repr_s = repr(key).lower()
        if DEBUG:
            print(f"[DEBUG] key repr fallback: {repr_s}")
        # Look for a lone letter like 'u' in the repr (best-effort)
        if "'u'" in repr_s or "u" in repr_s:
            name = 'u'
            keyboard_pressed.add(name)

    if DEBUG:
        print(f"[DEBUG] current keys pressed: {keyboard_pressed}")

    # Unlock combo: Ctrl + Alt + U
    if 'ctrl' in keyboard_pressed and 'alt' in keyboard_pressed and 'u' in keyboard_pressed:
        # print("Unlock combo detected. Unlocking keyboard and mouse if locked.")
        # Unlock both to be safe
        unlock_both()
        # Clear state to avoid repeated triggers
        keyboard_pressed.clear()


def _on_key_release(key):
    name = _key_name(key)
    if DEBUG:
        print(f"[DEBUG] key release: {key!r} -> {name}")
    if name and name in keyboard_pressed:
        keyboard_pressed.remove(name)
    if DEBUG:
        print(f"[DEBUG] current keys pressed after release: {keyboard_pressed}")


def lock_keyboard():
    """Start a keyboard listener that suppresses all keystrokes except for unlock combo."""
    global keyboard_lock_listener, keyboard_auto_unlock_timer, keyboard_pressed

    if keyboard_lock_listener is None:
        keyboard_pressed.clear()
        keyboard_lock_listener = keyboard.Listener(suppress=True, on_press=_on_key_press, on_release=_on_key_release)
        keyboard_lock_listener.start()
        if DEBUG:
            print("[DEBUG] keyboard listener started")

        # Start auto-unlock timer
        keyboard_auto_unlock_timer = threading.Timer(AUTO_UNLOCK_SECONDS, lambda: (print("Auto-unlock timer expired; unlocking devices."), unlock_both()))
        keyboard_auto_unlock_timer.daemon = True
        keyboard_auto_unlock_timer.start()
        if DEBUG:
            print(f"[DEBUG] auto-unlock timer started ({AUTO_UNLOCK_SECONDS}s)")

        # print(f"Keyboard LOCKED (Input Suppressed). Press Ctrl+Alt+U to UNLOCK or wait {AUTO_UNLOCK_SECONDS} seconds for auto-unlock.")
    else:
        # print("Keyboard is already LOCKED.")
        pass


def unlock_keyboard():
    """Stop keyboard suppression and cancel auto-unlock timer."""
    global keyboard_lock_listener, keyboard_auto_unlock_timer

    if keyboard_lock_listener is not None:
        if keyboard_auto_unlock_timer:
            keyboard_auto_unlock_timer.cancel()
            keyboard_auto_unlock_timer = None
            if DEBUG:
                print("[DEBUG] auto-unlock timer cancelled")
        keyboard_lock_listener.stop()
        if DEBUG:
            print("[DEBUG] keyboard listener stop() called; joining thread")
        # Wait for the listener thread to exit cleanly
        try:
            keyboard_lock_listener.join()
        except Exception:
            pass
        keyboard_lock_listener = None
        # print("Keyboard UNLOCKED.")
    else:
        # print("Keyboard is not locked.")
        pass


def unlock_both():
    unlock_mouse()
    unlock_keyboard()

def lock_both():
    lock_mouse()
    lock_keyboard()

# Setup the Keyboard Hotkey listener
hotkeys = {
    '<ctrl>+<alt>+l': lock_both,
    '<ctrl>+<alt>+u': unlock_both,
    # '<ctrl>+<alt>+k': lock_keyboard
}

# print("Listening for Ctrl + Alt + L to lock both mouse and keyboard, Ctrl + Alt + U to unlock...")

try:
    with keyboard.GlobalHotKeys(hotkeys) as h:
        h.join()
except KeyboardInterrupt:
    if mouse_lock_listener:
        mouse_lock_listener.stop()
        mouse_lock_listener = None
    # Cleanup keyboard lock if active
    if keyboard_lock_listener:
        if keyboard_auto_unlock_timer:
            keyboard_auto_unlock_timer.cancel()
            keyboard_auto_unlock_timer = None
        keyboard_lock_listener.stop()
        try:
            keyboard_lock_listener.join()
        except Exception:
            pass
        keyboard_lock_listener = None
    # print("\nScript stopped.")
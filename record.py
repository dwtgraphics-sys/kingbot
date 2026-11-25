# -*- coding: utf-8 -*-
"""
Teach the bot a routine by doing it once yourself.

    python record.py gather

Before EACH action, put the mouse on the button and press a hotkey, then do the
action yourself so the game moves to the next screen:

  F8  = remember a CLICK at the mouse position
  F9  = remember the NEXT KEY you press (e.g. Space, F, B)
  F10 = remember an IMAGE under the mouse: click it only if it is visible
        (good for buttons that are not always there, e.g. alliance Help)
  F6  = remember an IMAGE under the mouse: click EVERY copy visible
        (good for resource bubbles above farms / mills / quarries)
  F7  = add an extra 3 second wait (for slow screens)
  ESC = save and finish
"""
import sys, time
from common import *


def main():
    if len(sys.argv) < 2:
        print("Usage: python record.py ROUTINE_NAME")
        return
    name = sys.argv[1]
    g = Game()
    g.focus()
    steps = []
    n_img = 0
    print(__doc__)
    print(f"Recording routine '{name}'. Game area: {g.w}x{g.h}")
    last = time.time()

    while True:
        time.sleep(0.02)
        g.refresh()
        mx, my = pyautogui.position()
        rx, ry = g.to_rel(mx, my)

        if key_down(VK["F8"]):
            wait_key_release(VK["F8"])
            steps.append({"click": [round(rx, 4), round(ry, 4)], "after": 2.0})
            print(f"  + click at {rx:.3f}, {ry:.3f}")

        elif key_down(VK["F9"]):
            wait_key_release(VK["F9"])
            print("  ... press the key to record")
            key = None
            while key is None:
                time.sleep(0.02)
                for vk, kname in KEY_NAMES.items():
                    if key_down(vk):
                        wait_key_release(vk)
                        key = kname
                        break
            steps.append({"key": key, "after": 2.0})
            print(f"  + key '{key}'")
            continue  # don't let a recorded ESC end the recording

        elif key_down(VK["F10"]) or key_down(VK["F6"]):
            find_all = key_down(VK["F6"])
            wait_key_release(VK["F6"]); wait_key_release(VK["F10"])
            n_img += 1
            tname = f"{name}_{n_img}"
            g.save_template_around(tname, rx, ry)
            steps.append({"click_img": tname, "all": find_all, "optional": True, "after": 1.5})
            print(f"  + image '{tname}' ({'click all' if find_all else 'click if visible'})")

        elif key_down(VK["F7"]):
            wait_key_release(VK["F7"])
            steps.append({"wait": 3})
            print("  + wait 3s")

        elif key_down(VK["ESC"]):
            wait_key_release(VK["ESC"])
            break

    routines = load_json(ROUTINES_FILE, {})
    routines[name] = steps
    save_json(ROUTINES_FILE, routines)
    print(f"Saved '{name}' with {len(steps)} steps to routines.json")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
Claude channel: lets Claude drive the game THROUGH Kingbot (which can click the game).
Claude writes claude_cmd.json in the Kingbot folder:
  {"id": 5, "actions": [{"click": [0.5, 0.4]}, {"key": "space"}, {"wait": 3},
                        {"drag": [0.5, 0.5, 0.3, 0.5]}, {"scroll": -3}, {"shot": "map"}, {"launch": true}]}
Kingbot runs the actions once, saves screenshots of the game area to claude_out/<name>.png
and writes claude_done.json with the same id and a short log.
Coordinates are relative to the game area (0..1).
"""
import os, json, time
import cv2
from common import BASE, log, load_json, save_json, find_window, Game, press_key, pyautogui

CMD = os.path.join(BASE, "claude_cmd.json")
DONE = os.path.join(BASE, "claude_done.json")
OUT = os.path.join(BASE, "claude_out")


def check(sleep):
    if not os.path.exists(CMD):
        return
    cmd = load_json(CMD, {})
    cid = cmd.get("id")
    if cid is None or load_json(DONE, {}).get("id") == cid:
        return
    os.makedirs(OUT, exist_ok=True)
    out, ok = [], True
    log(f"Claude command {cid}: {len(cmd.get('actions', []))} actions")
    try:
        g = None
        for a in cmd.get("actions", []):
            if "launch" in a:
                import game_launcher
                try:
                    os.remove(game_launcher.LAST_TRY_FILE)
                except Exception:
                    pass
                out.append(f"launch: {game_launcher.ensure_game_running(sleep)}")
                continue
            if "windows" in a:
                import game_launcher
                for hwnd, title, cls, exe, r in game_launcher.list_windows():
                    out.append(f"win {hwnd} '{title[:40]}' {cls} {exe.split(chr(92))[-1]} {r}")
                continue
            if "launcher_start" in a:
                import game_launcher
                out.append(f"launcher_start: {game_launcher.press_launcher_start()}")
                continue
            if "wait" in a:
                sleep(float(a["wait"]))
                continue
            if g is None:
                if not find_window():
                    out.append("game window not found")
                    ok = False
                    break
                g = Game()
                g.focus()
            g.refresh()
            if "click" in a:
                rx, ry = a["click"]
                out.append(f"click {rx:.3f},{ry:.3f}: {'ok' if g.click_rel(rx, ry) else 'SKIPPED'}")
                sleep(a.get("after", 0.8))
            elif "key" in a:
                press_key(a["key"])
                out.append(f"key {a['key']}")
                sleep(a.get("after", 0.8))
            elif "drag" in a:
                x1, y1, x2, y2 = a["drag"]
                sx, sy = g.to_screen(x1, y1)
                ex, ey = g.to_screen(x2, y2)
                pyautogui.moveTo(sx, sy)
                pyautogui.mouseDown()
                pyautogui.moveTo(ex, ey, duration=0.6)
                pyautogui.mouseUp()
                out.append("drag")
                sleep(a.get("after", 1.0))
            elif "scroll" in a:
                cx, cy = g.to_screen(0.5, 0.5)
                pyautogui.moveTo(cx, cy)
                pyautogui.scroll(int(a["scroll"]) * 120)
                out.append(f"scroll {a['scroll']}")
                sleep(a.get("after", 1.0))
            elif "smart" in a:
                import smart
                g.focus()
                smart.SMART[a["smart"]](g, sleep)
                out.append(f"smart {a['smart']} done (see log.txt)")
            elif "shot" in a:
                img = g.screenshot()
                p = os.path.join(OUT, a["shot"] + ".png")
                cv2.imwrite(p, img)
                out.append(f"shot {a['shot']} {img.shape[1]}x{img.shape[0]}")
    except Exception as e:
        ok = False
        out.append(f"error: {e!r}")
    save_json(DONE, {"id": cid, "ok": ok, "time": time.strftime("%H:%M:%S"), "log": out})
    log(f"Claude command {cid} done: {'ok' if ok else 'FAILED'}")

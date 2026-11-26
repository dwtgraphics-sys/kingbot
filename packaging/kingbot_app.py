# -*- coding: utf-8 -*-
"""
SEC-04: entry point of the PROTECTED (packaged) Kingbot build - the frozen Kingbot.exe runs this.

It keeps the application code (frozen, read-only inside the exe) apart from the runtime files
(settings, state, logs, templates, backups), which stay WRITABLE in a folder next to the exe:

    dist/Kingbot/
        Kingbot.exe            <- the protected build (this file, frozen)
        _internal/ ...         <- bundled Python + libraries + the bot's .py as bytecode
        runtime/               <- KINGBOT_HOME: everything the bot reads and writes lives here
            local_config.json  github_token.txt  log.txt  *_state*.json  templates/  backups/  ...

Because KINGBOT_HOME points at runtime/, rebuilding or replacing the exe never touches the user's
settings or state. The exit code is passed straight back to the launcher (3 = restart, 0 = stop).
"""
import os, sys


def main():
    exe_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    home = os.environ.get("KINGBOT_HOME") or os.path.join(exe_dir, "runtime")
    os.environ["KINGBOT_HOME"] = home
    os.makedirs(home, exist_ok=True)
    try:
        os.chdir(home)
    except Exception:
        pass
    import bot
    bot.main()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(0)

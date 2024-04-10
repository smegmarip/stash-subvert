import json
import os
import sys

os.chdir(os.path.dirname(os.path.realpath(__file__)))

from extract import scan_scenes

from common import (
    stash_log,
    exit_plugin,
    pluginhumanname,
    clear_logfile,
    BATCH_QTY,
)

try:
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print(
        "You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)",
        file=sys.stderr,
    )


def main():
    global stash

    json_input = json.loads(sys.stdin.read())
    FRAGMENT_SERVER = json_input["server_connection"]
    stash = StashInterface(FRAGMENT_SERVER)

    ARGS = False
    PLUGIN_ARGS = False
    HOOKCONTEXT = False

    # Task Button handling
    try:
        PLUGIN_ARGS = json_input["args"]["mode"]
        ARGS = json_input["args"]
    except:
        pass

    # Clear log file
    clear_logfile()

    if PLUGIN_ARGS:
        stash_log("--Starting " + pluginhumanname + " Plugin --", lvl="debug")

        if "ExtractAll" in PLUGIN_ARGS:
            stash_log("running ExtractAll", lvl="info")
            scan_scenes(stash=stash, batch=BATCH_QTY)

    exit_plugin(msg="ok")


if __name__ == "__main__":
    main()

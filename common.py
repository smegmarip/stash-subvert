import os
import re
import sys
import json
from urllib.parse import urlparse
import uuid
import random
import string
import requests
import base64

# import face_recognition
import traceback
import warnings
import numpy as np
from io import BytesIO
from datetime import datetime
from typing import Any, List, Tuple
from glob import glob

try:
    import stashapi.log as log
    from stashapi.stashapp import StashInterface
except ModuleNotFoundError:
    print(
        "You need to install the stashapp-tools (stashapi) python module. (CLI: pip install stashapp-tools)",
        file=sys.stderr,
    )

plugincodename = "subvert"
pluginhumanname = "Subvert"

# Configuration/settings file... because not everything can be easily built/controlled via the UI plugin settings
# If you don't need this level of configuration, just define the default_settings here directly in code,
#    and you can remove the _defaults.py file and the below code
if not os.path.exists("config.py"):
    with open(plugincodename + "_defaults.py", "r") as default:
        config_lines = default.readlines()
    with open("config.py", "w") as firstrun:
        firstrun.write("from " + plugincodename + "_defaults import *\n")
        for line in config_lines:
            if not line.startswith("##"):
                firstrun.write(f"#{line}")


import config

default_settings = config.default_settings

PLUGIN_NAME = f"[{pluginhumanname}] "
STASH_URL = default_settings["stash_url"]
STASH_TMP = default_settings["stash_tmpdir"]
STASH_LOGFILE = default_settings["stash_logfile"]
BATCH_QTY = default_settings["batch_quantity"]

warnings.filterwarnings("ignore")


def stash_log(*args, **kwargs):
    messages = []
    for input in args:
        if not isinstance(input, str):
            try:
                messages.append(json.dumps(input, default=default_json))
            except:
                continue
        else:
            messages.append(input)
    if len(messages) == 0:
        return

    lvl = kwargs["lvl"] if "lvl" in kwargs else "info"
    message = " ".join(messages)

    if lvl == "trace":
        log.LEVEL = log.StashLogLevel.TRACE
        log.trace(message)
    elif lvl == "debug":
        log.LEVEL = log.StashLogLevel.DEBUG
        log.debug(message)
    elif lvl == "info":
        log.LEVEL = log.StashLogLevel.INFO
        log.info(message)
    elif lvl == "warn":
        log.LEVEL = log.StashLogLevel.WARNING
        log.warning(message)
    elif lvl == "error":
        log.LEVEL = log.StashLogLevel.ERROR
        log.error(message)
    elif lvl == "result":
        log.result(message)
    elif lvl == "progress":
        try:
            progress = min(max(0, float(args[0])), 1)
            log.progress(str(progress))
        except:
            pass
    log.LEVEL = log.StashLogLevel.INFO


def default_json(t):
    return f"{t}"


def get_config_value(section, prop):
    global _config
    return _config.get(section=section, option=prop)


def clear_tempdir():
    tmpdir = STASH_TMP if STASH_TMP.endswith(os.path.sep) else (STASH_TMP + os.path.sep)
    for f in glob(f"{tmpdir}*.srt"):
        try:
            os.remove(f)
        except OSError as e:
            stash_log(f"could not remove {f}", lvl="error")
            continue
    stash_log("cleared temp directory.", lvl="debug")


def clear_logfile():
    if STASH_LOGFILE and os.path.exists(STASH_LOGFILE):
        with open(STASH_LOGFILE, "w") as file:
            pass


def exit_plugin(msg=None, err=None):
    if msg is None and err is None:
        msg = pluginhumanname + " plugin ended"
    output_json = {}
    if msg is not None:
        stash_log(f"{msg}", lvl="debug")
        output_json["output"] = msg
    if err is not None:
        stash_log(f"{err}", lvl="error")
        output_json["error"] = err
    print(json.dumps(output_json))
    sys.exit()


def save_to_local(url, ext="jpg"):
    directory = STASH_TMP if STASH_TMP.endswith(os.path.sep) else (STASH_TMP + os.path.sep)
    # Generate a unique filename
    filename = f"{directory}downloaded_{uuid.uuid4()}.{ext}"

    try:
        # Send an HTTP GET request to the URL
        response = requests.get(url)

        # Check if the request was successful (status code 200)
        if response.status_code == 200:
            # Open the local file in binary write mode and write the content from the URL to it
            with open(filename, "wb") as local_file:
                local_file.write(response.content)
            stash_log(f"Downloaded and saved file to {filename}", lvl="debug")
        else:
            stash_log(f"Failed to download file: {response.status_code}", lvl="error")
            return None
    except requests.exceptions.RequestException as e:
        stash_log(f"Failed to download file: {e}", lvl="error")
        return None

    return filename


def get_stash_video(vid_data):
    props = ["id", "path", "format", "width", "height", "duration", "frame_rate"]
    raw = None
    files = vid_data["files"]

    for file in files:
        test: str = file["path"]
        if os.path.exists(test):
            raw = {k: file[k] for k in props}
            break

    if raw is None:
        url = vid_data["paths"]["stream"]
        ext = "mp4"
        ext_match = re.search(r"\.([^.]+)$", files[0]["path"])
        if ext_match:
            ext = ext_match.group(1)
        raw = {k: file[k] for k in props}
        raw["path"] = save_to_local(url, ext)

    if raw is not None:
        raw["sprite"] = vid_data["paths"]["sprite"]
        raw["vtt"] = vid_data["paths"]["vtt"]
        valid = (
            ".m4v",
            ".mp4",
            ".mov",
            ".wmv",
            ".avi",
            ".mpg",
            ".mpeg",
            ".rmvb",
            ".rm",
            ".flv",
            ".asf",
            ".mkv",
            ".webm",
            ".flv",
            ".3gp",
            ".ogg",
        )
        if raw["path"].lower().endswith(valid):
            return raw

    return None

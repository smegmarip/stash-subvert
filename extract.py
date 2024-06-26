import json
import os
import re
import time
import traceback
from stashapi.stashapp import StashInterface
from common import (
    SUBTITLE_TAG_ID,
    get_stash_video,
    stash_log,
    system_call,
    the_id,
    to_integer,
    update_scene,
)


def scan_scenes(stash: StashInterface, path=None, batch: int = 10):
    total = 1
    counter = 0
    timeout = 5

    params = {}
    if SUBTITLE_TAG_ID:
        params["tags"] = {"value": SUBTITLE_TAG_ID, "modifier": "EXCLUDES", "depth": 0}

    if path:
        # path = "\.(ogg|mkv)$"
        params["path"] = {"value": path, "modifier": "MATCHES_REGEX"}

    while True:
        counter += 1
        _current, scenes = stash.find_scenes(
            f=params,
            filter={
                "per_page": batch,
                "page": counter,
                "sort": "updated_at",
                "direction": "ASC",
            },
            get_count=True,
        )

        if counter == 1:
            total = int(_current)

        _current = batch * (counter - 1)

        if _current >= total:
            break

        num_scenes = len(scenes)
        stash_log(f"received {num_scenes} / {total - _current} scenes", lvl="info")
        # stash_log("scenes", scenes, lvl="debug")

        for i in range(num_scenes):
            scene = scenes[i]
            _current += 1
            progress = (float(_current)) / float(total)
            stash_log(progress, lvl="progress")
            stash_log(
                f"{round(progress * 100, 2)}%: ",
                f"evaluating scene index: {((counter - 1) * batch) + i} (id: {scene['id']})",
                lvl="info",
            )
            extract_subtitles(stash=stash, scene=scene)

        stash_log("--end of loop--", lvl="debug")
        time.sleep(timeout)


def extract_subtitles(stash: StashInterface, scene: dict):
    try:
        stash_log(scene, lvl="debug")
        scene_data = get_stash_video(scene)

        if scene_data is None:
            stash_log("invalid video extension.", lvl="info")
            return

        scene_path = scene_data["path"]
        tags = to_integer(the_id(scene["tags"]))
        num_tags = len(tags)
        output_dir = os.path.dirname(scene_path)

        # Extract subtitle tracks from the video using ffmpeg
        cmd = ["ffmpeg", "-i", scene_path]
        stream_info, _ = system_call(cmd)
        stash_log(stream_info, lvl="debug")
        subtitle_tracks = re.findall(r"Stream #\d+:(\d+)(?:\(([^\)]+)\))?:[\t ]+Subtitle:.*", stream_info)

        if subtitle_tracks:
            stash_log(subtitle_tracks, lvl="debug")
            for i, subtitle_track in enumerate(subtitle_tracks, start=0):
                lang = subtitle_track[1] if subtitle_track[1] and not subtitle_track[1].isspace() else None
                subtitle_name = os.path.splitext(os.path.basename(scene_path))[0]
                if lang:
                    subtitle_name = f"{subtitle_name}.{lang}"
                subtitle_path = os.path.join(output_dir, f"{subtitle_name}.srt")

                # Check if subtitle file already exists
                if os.path.exists(subtitle_path):
                    stash_log(f"Subtitle file {subtitle_path} already exists. Skipping extraction.", lvl="info")
                    if SUBTITLE_TAG_ID != 0 and SUBTITLE_TAG_ID not in tags:
                        tags.append(SUBTITLE_TAG_ID)
                    continue

                # Extract subtitles to SRT format using ffmpeg
                cmd = ["ffmpeg", "-i", scene_path, f"-map", f"0:s:{i}", "-c:s", "srt", subtitle_path]
                system_call(cmd)
                stash_log(f"Subtitle file: {subtitle_name} created.", lvl="info")
                if SUBTITLE_TAG_ID != 0 and SUBTITLE_TAG_ID not in tags:
                    tags.append(SUBTITLE_TAG_ID)

            if SUBTITLE_TAG_ID != 0 and len(tags) != num_tags:
                update_scene(stash=stash, id=scene["id"], tags=tags)
                stash_log("update_scene", f"scene #{scene['id']} updated.", lvl="info")

    except Exception as ex:
        stash_log(f"{scene_path}: {ex}", lvl="error")
        stash_log(traceback.format_exc(), lvl="error")
        if len(tags) != num_tags:
            update_scene(stash=stash, id=scene["id"], tags=tags)
            stash_log("update_scene", f"scene #{scene['id']} updated.", lvl="info")

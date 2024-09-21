import logging
import os
import json
import time
import shutil
import asyncio
from datetime import datetime
from config import Config
from plugins.functions.display_progress import humanbytes, progress_for_pyrogram
from plugins.functions.ran_text import random_char
from plugins.script import Translation
from plugins.utitles import Mdata01, Mdata02, Mdata03

# Set up logging configuration
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


async def youtube_dl_call_back(_bot, update):
    # Constants
    AD_STRING_TO_REPLACE = "please report this issue on https://github.com/kalanakt/All-Url-Uploader/issues"

    cb_data = update.data
    tg_send_type, youtube_dl_format, youtube_dl_ext, ranom = cb_data.split("|")
    print(cb_data)
    random1 = random_char(5)
    save_ytdl_json_path = (
        Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + f"{ranom}" + ".json"
    )

    try:
        with open(save_ytdl_json_path, "r", encoding="utf8") as f:
            response_json = json.load(f)
    except FileNotFoundError as e:
        await update.message.edit(f"Error: {e}")
        await update.message.delete()
        return False

    youtube_dl_url = update.message.reply_to_message.text
    custom_file_name = (
        str(response_json.get("title")) + "_" + youtube_dl_format + "." + youtube_dl_ext
    )
    youtube_dl_username = None
    youtube_dl_password = None

    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        if len(url_parts) == 2:
            youtube_dl_url, custom_file_name = map(str.strip, url_parts)
        elif len(url_parts) == 4:
            (
                youtube_dl_url,
                custom_file_name,
                youtube_dl_username,
                youtube_dl_password,
            ) = map(str.strip, url_parts)
        else:
            for entity in update.message.reply_to_message.entities:
                if entity.type == "text_link":
                    youtube_dl_url = entity.url
                elif entity.type == "url":
                    o = entity.offset
                    length = entity.length
                    youtube_dl_url = youtube_dl_url[o: o + length]

    await update.message.edit_caption(
        caption=Translation.DOWNLOAD_START.format(custom_file_name)
    )
    description = Translation.CUSTOM_CAPTION_UL_FILE

    if "fulltitle" in response_json:
        description = response_json["fulltitle"][:1021]

    tmp_directory_for_each_user = (
        Config.DOWNLOAD_LOCATION + "/" + str(update.from_user.id) + f"{random1}"
    )

    if not os.path.isdir(tmp_directory_for_each_user):
        os.makedirs(tmp_directory_for_each_user)

    download_directory = f"{tmp_directory_for_each_user}/{custom_file_name}"

    command_to_exec = []

    if tg_send_type == "audio":
        command_to_exec = [
            "yt-dlp",
            "-c",
            "--max-filesize",
            str(Config.TG_MAX_FILE_SIZE),
            "--bidi-workaround",
            "--extract-audio",
            "--audio-format",
            youtube_dl_ext,
            "--audio-quality",
            youtube_dl_format,
            youtube_dl_url,
            "-o",
            download_directory,
        ]
    else:
        minus_f_format = youtube_dl_format
        if "youtu" in youtube_dl_url:
            minus_f_format = f"{youtube_dl_format}+bestaudio"
        command_to_exec = [
            "yt-dlp",
            "-c",
            "--max-filesize",
            str(Config.TG_MAX_FILE_SIZE),
            "--embed-subs",
            "-f",
            minus_f_format,
            "--bidi-workaround",
            youtube_dl_url,
            "-o",
            download_directory,
        ]

    if Config.HTTP_PROXY != "":
        command_to_exec.extend(["--proxy", Config.HTTP_PROXY])

    if youtube_dl_username is not None:
        command_to_exec.extend(["--username", youtube_dl_username])

    if youtube_dl_password is not None:
        command_to_exec.extend(["--password", youtube_dl_password])

    command_to_exec.extend(["--no-warnings"])

    logger.info(command_to_exec)
    start = datetime.now()

    process = await asyncio.create_subprocess_exec(
        *command_to_exec,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()
    e_response = stderr.decode().strip()
    t_response = stdout.decode().strip()

    logger.info(e_response)
    logger.info(t_response)

    if e_response and AD_STRING_TO_REPLACE in e_response:
        error_message = e_response.replace(AD_STRING_TO_REPLACE, "")
        await update.message.edit_caption(text=error_message)
        return False

    if t_response:
        logger.info(t_response)
        try:
            os.remove(save_ytdl_json_path)
        except FileNotFoundError:
            pass

        end_one = datetime.now()
        time_taken_for_download = (end_one - start).seconds

        try:
            # Check if file exists and get its size
            if os.path.exists(download_directory):
                file_size = os.stat(download_directory).st_size
            else:
                logger.debug(f"File not found, trying .mkv extension")
                download_directory = os.path.splitext(download_directory)[0] + ".mkv"
                if os.path.exists(download_directory):
                    file_size = os.stat(download_directory).st_size
                else:
                    logger.error(f"File not found: {download_directory}")
                    await update.message.edit(f"File not found: {download_directory}")
                    return False
        except FileNotFoundError:
            logger.error(f"File not found: {download_directory}")
            await update.message.edit(f"File not found: {download_directory}")
            return False

        download_location = f"{Config.DOWNLOAD_LOCATION}/{update.from_user.id}.jpg"
        thumb = download_location if os.path.isfile(download_location) else None

        if file_size > Config.TG_MAX_FILE_SIZE:
            await update.message.edit_caption(
                caption=Translation.RCHD_TG_API_LIMIT.format(
                    time_taken_for_download, humanbytes(file_size)
                )
            )
        else:
            await update.message.edit_caption(
                caption=Translation.UPLOAD_START.format(custom_file_name)
            )

            start_time = time.time()

            if tg_send_type == "video":
                width, height, duration = await Mdata01(download_directory)
                await update.message.reply_video(
                    video=download_directory,
                    caption=description,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    thumb=thumb,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time,
                    ),
                )
            elif tg_send_type == "audio":
                duration = await Mdata03(download_directory)
                await update.message.reply_audio(
                    audio=download_directory,
                    caption=description,
                    duration=duration,
                    thumb=thumb,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time,
                    ),
                )
            elif tg_send_type == "vm":
                width, duration = await Mdata02(download_directory)
                await update.message.reply_video_note(
                    video_note=download_directory,
                    duration=duration,
                    length=width,
                    thumb=thumb,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time,
                    ),
                )
            else:
                await update.message.reply_document(
                    document=download_directory,
                    caption=description,
                    thumb=thumb,
                    progress=progress_for_pyrogram,
                    progress_args=(
                        Translation.UPLOAD_START,
                        update.message,
                        start_time,
                    ),
                )

            end_two = datetime.now()
            time_taken_for_upload = (end_two - end_one).seconds
            logger.info(f"Downloaded in {time_taken_for_download}s. Uploaded in {time_taken_for_upload}s.")
        try:
            shutil.rmtree(tmp_directory_for_each_user)
        except Exception as e:
            logger.error(f"Error while deleting directory: {e}")
    else:
        await update.message.edit_caption(text=Translation.NO_VOID_FORMAT_FOUND)

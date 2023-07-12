import re
import json
from moviepy.editor import (
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
    concatenate_videoclips,
    ImageClip,
    CompositeVideoClip,
    TextClip,
    AudioFileClip,
    AudioClip,
    ColorClip,
)
from PIL import Image, ImageDraw
import numpy as np


class Composer:
    def __init__(self, script_path, config):
        self.config = config
        self.h = config["video_height"]
        self.w = config["video_width"]
        self.size = (self.w, self.h)
        self.parse_the_script(script_path)
        self.calculate_start_time()
        self.calculate_end_time()
        self.duration = (self.end_time - self.start_time) / 1000

        print("start_time: ", self.start_time)
        print("end_time: ", self.end_time)
        print("video_gap_head: ", self.video_gap_head_duration)
        print("audio_gap_head: ", self.audio_gap_head_duration)
        print("video_gap_tail: ", self.video_gap_tail_duration)
        print("audio_gap_tail: ", self.audio_gap_tail_duration)
        print("the output video will have duration: ", self.duration)

    def parse_the_script(self, script_path):
        with open(script_path) as f:
            parsed_script = json.load(f)
            self.script = parsed_script
            self.recorder = parsed_script["recorder"]
            self.recorder["avatar"] = (
                parsed_script.get("recorder", {}).get("avatar")
                or self.config["default_avatar"]
            )

            self.videos = parsed_script.get("videos", [])
            self.audios = parsed_script.get("audios", [])
            self.screens = parsed_script.get("screens", [])

    def calculate_start_time(self):
        start_time = float("inf")
        first_video_start = (
            self.get_timestamp_from_media_path(self.videos[0])
            if len(self.videos)
            else float("inf")
        )
        first_audio_start = (
            self.get_timestamp_from_media_path(self.audios[0])
            if len(self.audios)
            else float("inf")
        )
        first_screen_start = (
            self.get_timestamp_from_media_path(self.screens[0])
            if len(self.screens)
            else float("inf")
        )

        if first_video_start:
            start_time = min(start_time, first_video_start)

        if first_audio_start:
            start_time = min(start_time, first_audio_start)

        if first_screen_start:
            start_time = min(start_time, first_screen_start)

        self.video_gap_head_duration = (
            first_video_start - start_time if first_video_start else start_time
        ) / 1000
        self.audio_gap_head_duration = (
            first_audio_start - start_time if first_audio_start else start_time
        ) / 1000
        self.screen_gap_head_duration = (
            first_screen_start - start_time if first_screen_start else start_time
        ) / 1000
        self.start_time = start_time

    def calculate_end_time_of_media_file(self, media_path, type="video"):
        start = self.get_timestamp_from_media_path(media_path)
        media = (
            VideoFileClip(media_path) if type == "video" else AudioFileClip(media_path)
        )
        return start + media.duration * 1000

    def calculate_end_time(self):
        end_time = 0
        last_video_end = (
            self.calculate_end_time_of_media_file(self.videos[-1])
            if len(self.videos)
            else 0
        )
        last_audio_end = (
            self.calculate_end_time_of_media_file(self.audios[-1], type="audio")
            if len(self.audios)
            else 0
        )
        last_screen_end = (
            self.calculate_end_time_of_media_file(self.screens[-1])
            if len(self.screens)
            else 0
        )

        if last_video_end:
            print("end time video", last_video_end)
            end_time = max(end_time, last_video_end)

        if last_audio_end:
            print("end time audio", last_audio_end)
            end_time = max(end_time, last_audio_end)

        if last_screen_end:
            print("end time screen", last_screen_end)
            end_time = max(end_time, last_screen_end)

        self.video_gap_tail_duration = (
            end_time - last_video_end if last_video_end else end_time
        ) / 1000
        self.audio_gap_tail_duration = (
            end_time - last_audio_end if last_audio_end else end_time
        ) / 1000
        self.screen_gap_tail_duration = (
            end_time - last_screen_end if last_screen_end else end_time
        ) / 1000
        self.end_time = end_time

    #  ╭──────────────────────────────────────────────────────────╮
    #  │                     Video Processing                     │
    #  ╰──────────────────────────────────────────────────────────╯
    def create_circle_avatar(self):
        """
        For the parts when the recorder turn off his/her webcam
        the circle of his/her avatar will be displayed instead.
        This function will create a circle image for that case.

        :return: circle ImageClip
        """
        # define placeholder size
        # square obviously
        size = (self.config["avatar_size"], self.config["avatar_size"])

        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size[0], size[1]), fill=255)
        mask_array = np.array(mask)

        # Load the image and resize it to 100x100
        image = ImageClip(self.recorder["avatar"]).resize(size)

        # Set the mask of the original image using set_mask
        mask_clip = ImageClip(np.uint8(mask_array) * 255, ismask=True)
        masked_image = image.set_mask(mask_clip)

        return masked_image

    def create_video_placeholder(self, duration):
        """
        For the parts when the recorder turn off his/her webcam
        the circle of his/her avatar will be displayed instead.
        This function will take the circle image convert it to a video clip
        with the given duration.

        :param img_path: path/to/the/avatar
        :param duration: duration of the output clip
        :return: circle ImageClip
        """
        avatar_img = self.create_circle_avatar()

        # Create the composite video clip with the masked image in the center
        placeholder_clip = CompositeVideoClip(
            [avatar_img.set_pos("center")], size=self.size
        ).set_duration(duration)

        return placeholder_clip

    def get_timestamp_from_media_path(self, media_path):
        """
        The name of media file contains the timestamp (i.e: 1688998315842.webm)
        We will calculate the time (synchronization) base on this value

        :param media_path: path/to/media/file
        :return: timestamp or None
        """
        timestamp_matched = re.search(r"/(\d+)\.(webm|mp4|wav)$", media_path)

        if timestamp_matched:
            return int(timestamp_matched.group(1))

        return None

    def calculate_gap_duration(self, first_path, second_path, type="video"):
        """
        Calculate the gap duration between two clips

        Simply take the timestamp from two clips then do the math
        - formulas: t2 - (t1 + first_clip.duration) / 1000
        (divide to 1000 to convert to second unit)

        :param first_path: path/to/the/first/media/path
        :param second_path: path/to/the/second/media/path
        :param type: audio | video
        :return: duration in second
        """
        # Load the first media clip
        clip1 = (
            VideoFileClip(first_path) if type == "video" else AudioFileClip(first_path)
        )

        # Calculate the gap duration
        t1 = self.calculate_end_time_of_media_file(first_path)
        t2 = self.get_timestamp_from_media_path(second_path)
        duration = t2 - t1

        return duration / 1000

    def get_video_gap_between_two_videos(self, first_path, second_path):
        """
        Get video gap between two videos
        Create a placeholder video between video files

        :param first_path: path/to/the/first/media/path
        :param second_path: path/to/the/second/media/path
        :return: Placeholder VideoClip
        """
        duration = self.calculate_gap_duration(first_path, second_path)
        gap_video = self.create_video_placeholder(duration)

        return gap_video

    def gen_gaps_of_set_videos(self):
        """
        Given a set of videos, this function will generate the gap videos
        between them

        :return: List of Placeholder VideoClips
        """
        gaps = []

        for i in range(len(self.videos) - 1):
            gaps.append(
                self.get_video_gap_between_two_videos(
                    self.videos[i], self.videos[i + 1]
                )
            )

        return gaps

    def fill_the_video_gaps(self):
        """
        Given a set of videos, this function will merge the videos and the gaps
        between them into a single list

        :param set_video_paths: List of video files
        :return: List of VideoClips
        """
        gaps = self.gen_gaps_of_set_videos()
        clips = list(map(VideoFileClip, self.videos))

        solid_streams = []

        # merge two arrays
        i = 1
        while len(gaps) or len(clips):
            if i % 2:
                solid_streams.append(clips.pop(0))
            else:
                solid_streams.append(gaps.pop(0))
            i += 1

        solid_streams.extend(clips)
        solid_streams.extend(gaps)

        # if the video was recorder after audio or screen
        if self.video_gap_head_duration > 0:
            solid_streams.insert(
                0, self.create_video_placeholder(self.video_gap_head_duration)
            )

        if self.video_gap_tail_duration > 0:
            solid_streams.append(
                self.create_video_placeholder(self.video_gap_tail_duration)
            )

        return solid_streams

    #  ╭──────────────────────────────────────────────────────────╮
    #  │                     Audio processing                     │
    #  ╰──────────────────────────────────────────────────────────╯
    def get_audio_gap_between_two_audios(self, first_path, second_path):
        """
        Get audio gap between two audio
        Create a silent audio clip between video files

        :param first_path: path/to/the/first/media/path
        :param second_path: path/to/the/second/media/path
        :return:  a silent AudioClip
        """
        duration = self.calculate_gap_duration(first_path, second_path, type="audio")
        gap_audio = AudioClip(make_frame=lambda _: 0, duration=duration)

        return gap_audio

    def gen_gaps_of_set_audios(self):
        """
        Given a set of audios, this function will generate the gap audios
        between them

        :param set_audio_paths: List of audio files
        :return: List of Placeholder AudioClips
        """
        gaps = []

        for i in range(len(self.audios) - 1):
            gaps.append(
                self.get_audio_gap_between_two_audios(
                    self.audios[i], self.audios[i + 1]
                )
            )

        return gaps

    def fill_the_audio_gaps(self):
        """
        Given a set of audios, this function will merge the audios and the gaps
        between them into a single list

        :return: List of AudioClips
        """
        gaps = self.gen_gaps_of_set_audios()
        clips = list(map(lambda t: AudioFileClip(t), self.audios))

        solid_streams = []

        # merge two arrays
        i = 1
        while len(gaps) or len(clips):
            if i % 2:
                solid_streams.append(clips.pop(0))
            else:
                solid_streams.append(gaps.pop(0))
            i += 1

        solid_streams.extend(clips)
        solid_streams.extend(gaps)

        # if the audio was recorder after video or screen
        # create a silent audio and add it to the head
        if self.audio_gap_head_duration > 0:
            solid_streams.insert(
                0,
                AudioClip(
                    make_frame=lambda _: 0, duration=self.audio_gap_head_duration
                ),
            )
        if self.audio_gap_tail_duration > 0:
            solid_streams.append(
                AudioClip(
                    make_frame=lambda _: 0, duration=self.audio_gap_tail_duration
                ),
            )

        return solid_streams

    def create_name_box(self):
        text = f'  {self.recorder["name"]}  '
        font = self.config["font"]
        fontsize = self.config["name_box_font_size"]
        color = "white"

        # Create the TextClip with the given properties
        text_clip = TextClip(
            text, font=font, fontsize=fontsize, color=color, bg_color="gray10"
        )

        # Set the position of the TextClip to the left bottom corner
        x = 10
        y = self.h - text_clip.h - 10
        position = (x, y)
        text_clip = text_clip.set_position(position)

        return text_clip

    def merge_webcam_and_screen(self, webcam, screen):
        screen_width = int(self.w * 3 / 4)
        webcam_width = int(self.w * 1 / 4)

        bg_clip = ColorClip(size=(screen_width, 720), color=(26, 26, 26), ismask=False)

        screen = screen.resize(width=screen_width)
        webcam = webcam.resize(width=webcam_width)
        # webcam = webcam.set_duration(screen.duration)
        bg_clip = bg_clip.set_duration(screen.duration)
        final_clip = CompositeVideoClip(
            [
                bg_clip,
                screen.set_position((0, (self.size[1] / 2) - screen.h / 2)),
                webcam.set_position((screen_width, (self.size[1] / 2) - webcam.h / 2)),
            ],
            size=self.size,
            bg_color=(0, 0, 0),
        )

        return final_clip

    def handle_layout_changes(self, solid_clip):
        if len(self.screens) == 0:
            return solid_clip

        layout_change_timestamps = []
        for screen in self.screens:
            start = self.get_timestamp_from_media_path(screen)
            end = self.calculate_end_time_of_media_file(screen)
            duration = (end - start) / 1000
            layout_change_timestamps.append((start, end, duration))

        sub_clips = []
        start = self.start_time
        for [event, screen] in zip(layout_change_timestamps, self.screens):
            # handle before layout change
            start_time = (start - self.start_time) / 1000
            end_time = (event[0] - self.start_time) / 1000

            sub_clips.append(solid_clip.subclip(start_time, end_time))

            # handle while layout change
            composite = self.merge_webcam_and_screen(
                solid_clip.subclip(end_time, end_time + event[2]), VideoFileClip(screen)
            )
            sub_clips.append(composite)
            start = event[1]

        # case the screen share is finish before the stream end
        if self.screen_gap_tail_duration > 0:
            sub_clips.append(
                solid_clip.subclip(
                    self.duration - self.screen_gap_tail_duration, self.duration
                )
            )

        final_clip = concatenate_videoclips(sub_clips, method="compose")
        return final_clip

    def compose(self):
        webcam_stream = self.create_webcam_stream()
        final = self.handle_layout_changes(webcam_stream)
        output_filepath = f'{self.config["output_dir"]}/{self.script["meeting_id"]}.mp4'
        final.write_videofile(output_filepath)

    def create_webcam_stream(self):
        # get the solid webcam stream
        # fill the gaps (where recorder turn off the camera)
        # with his/her avatar image
        video_streams = self.fill_the_video_gaps()
        solid_webcam_clips = concatenate_videoclips(video_streams, method="compose")

        # get the solid audio streams
        solid_audio_clips = concatenate_audioclips(self.fill_the_audio_gaps())
        solid_webcam_clips = solid_webcam_clips.set_audio(solid_audio_clips)

        # create name box for the recorder
        text_clip = self.create_name_box()

        # merge them together
        final_clip = CompositeVideoClip(
            [solid_webcam_clips, text_clip], size=self.size, bg_color=(26, 26, 26)
        )
        final_clip.duration = solid_webcam_clips.duration

        return final_clip

        # output_filepath = f'{self.config["output_dir"]}/{self.script["meeting_id"]}.mp4'
        # final_clip.write_videofile(output_filepath)

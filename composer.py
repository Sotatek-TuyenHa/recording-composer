import re
import json
from moviepy.editor import VideoFileClip, concatenate_audioclips, concatenate_videoclips, concatenate_videoclips, ImageClip, CompositeVideoClip, TextClip, AudioFileClip, AudioClip
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

    def parse_the_script(self, script_path):
        with open(script_path) as f:
            parsed_script = json.load(f)
            self.script = parsed_script
            self.recorder = parsed_script["recorder"]
            self.recorder["avatar"] = parsed_script.get("recorder", {}).get("avatar") or self.config["default_avatar"]

            self.videos = parsed_script.get("videos", [])
            self.audios = parsed_script.get("audios", [])
            self.screens = parsed_script.get("screens", [])

    def calculate_start_time(self):
        start_time = float("inf")
        first_video_start = self.get_timestamp_from_media_path(self.videos[0]) if len(self.videos) else float("inf")
        first_audio_start = self.get_timestamp_from_media_path(self.audios[0]) if len(self.audios) else float("inf")
        first_screen_start = self.get_timestamp_from_media_path(self.screens[0]) if len(self.screens) else float("inf")

        if first_video_start:
            start_time = min(start_time, first_video_start)

        if first_audio_start:
            start_time = min(start_time, first_audio_start)

        if first_screen_start:
            start_time = min(start_time, first_screen_start)

        self.video_start = first_video_start - start_time if first_video_start else start_time
        self.audio_start = first_audio_start - start_time if first_audio_start else start_time
        self.screen_start = first_screen_start - start_time if first_screen_start else start_time
        self.start_time = start_time

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

        mask = Image.new('L', size, 0)
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
        placeholder_clip = CompositeVideoClip([avatar_img.set_pos("center")], size=self.size).set_duration(duration)

        return placeholder_clip

    def get_timestamp_from_media_path(self, media_path):
        """
        The name of media file contains the timestamp (i.e: 1688998315842.webm)
        We will calculate the time (synchronization) base on this value

        :param media_path: path/to/media/file
        :return: timestamp or None
        """
        timestamp_matched = re.search(r'/(\d+)\.(webm|mp4|wav)$', media_path)

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
        clip1 = VideoFileClip(first_path)
        if type == "audio":
            clip1 = AudioFileClip(first_path)

        # Calculate the gap duration
        t1 = self.get_timestamp_from_media_path(first_path)
        t2 = self.get_timestamp_from_media_path(second_path)
        duration = t2 - (t1 + clip1.duration)

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
            gaps.append(self.get_video_gap_between_two_videos(self.videos[i], self.videos[i+1]))

        return gaps


    def fill_the_video_gaps(self):
        """
        Given a set of videos, this function will merge the videos and the gaps
        between them into a single list

        :param img_path: path/to/the/avatar
        :param set_video_paths: List of video files
        :return: List of VideoClips
        """
        gaps = self.gen_gaps_of_set_videos()
        clips = list(map(VideoFileClip, self.videos))

        solid_streams = []

        # merge two arrays
        i = 1
        while len(gaps) or len(clips):
            if (i % 2):
                solid_streams.append(clips.pop(0))
            else:
                solid_streams.append(gaps.pop(0))
            i+=1

        solid_streams.extend(clips)
        solid_streams.extend(gaps)

        # if the video was recorder after audio or screen
        if self.video_start > 0:
            solid_streams.insert(0, self.create_video_placeholder(self.video_start))

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
            gaps.append(self.get_audio_gap_between_two_audios(self.audios[i], self.audios[i+1]))

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
            if (i % 2):
                solid_streams.append(clips.pop(0))
            else:
                solid_streams.append(gaps.pop(0))
            i+=1

        solid_streams.extend(clips)
        solid_streams.extend(gaps)

        # if the audio was recorder after video or screen
        # create a silent audio and add it to the head
        if self.audio_start > 0:
            solid_streams.insert(0, AudioClip(make_frame=lambda _: 0, duration=self.audio_start))

        return solid_streams


    def create_name_box(self):
        text = f'  {self.recorder["name"]}  '
        font = self.config["font"]
        fontsize = self.config["name_box_font_size"]
        color = "white"

        # Create the TextClip with the given properties
        text_clip = TextClip(text, font=font, fontsize=fontsize, color=color, bg_color="gray10")

        # Set the position of the TextClip to the left bottom corner
        x = 10
        y = self.h - text_clip.h - 10
        position = (x, y)
        text_clip = text_clip.set_position(position)

        return text_clip

    def compose(self):
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
        final_clip = CompositeVideoClip([solid_webcam_clips, text_clip], size=self.size)
        final_clip.duration = solid_webcam_clips.duration

        output_filepath = f'{self.config["output_dir"]}/{self.script["meeting_id"]}.mp4'
        final_clip.write_videofile(output_filepath)

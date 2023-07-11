import sys
import os
import configparser
from composer import Composer

def build_config():
    config = configparser.ConfigParser()
    config.read('config.ini')

    rel_output_dir = config["composer"]["output_dir"]
    output_dir = os.path.join(os.path.dirname(__file__), rel_output_dir)

    # assets related
    assets_path = os.path.join(os.path.dirname(__file__), config["assets"]["path"])

    font_file = config["assets"]["font"]
    font = os.path.join(assets_path, font_file)

    default_avatar = os.path.join(assets_path, config["assets"]["default_avatar"])

    return {
        "video_height": int(config["composer"]["video_height"]),
        "video_width": int(config["composer"]["video_width"]),
        "name_box_font_size": int(config["composer"]["name_box_font_size"]),
        "output_dir": output_dir,
        "assets_path": assets_path,
        "font": font,
        "default_avatar": default_avatar,
        "avatar_size": int(config["composer"]["avatar_size"])
    }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        script_path = sys.argv[1]
        config = build_config()
        composer = Composer(script_path, config)
        composer.compose()
    else:
        print("Err! A script file is required!")

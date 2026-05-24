import os
from src.betaloop import start_betaloop

DEFAULT_CONFIG_FILE_NAME = "config.txt"

if __name__ == "__main__":
    betaloop_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(betaloop_dir, DEFAULT_CONFIG_FILE_NAME)

    start_betaloop(config_file_path)
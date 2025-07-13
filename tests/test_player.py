import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import app

# Prevent scheduler from starting during tests
patcher = patch.object(app.MediaPlayer, "start_scheduler", lambda self: None)
patcher.start()


def test_play_video_mpv_missing(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    with patch.object(app, "CONFIG_FILE", str(config)):
        player = app.MediaPlayer()
        with patch("shutil.which", return_value=None):
            success, msg = player.play_video()
        assert not success
        assert "mpv" in msg


def test_mpv_log_file_constant():
    assert os.path.basename(app.MPV_LOG_FILE) == "mpv.log"

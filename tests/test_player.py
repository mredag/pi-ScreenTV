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


def test_play_video_reports_log_on_failure(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    log_file = tmp_path / "mpv.log"
    with patch.object(app, "CONFIG_FILE", str(cfg)), patch.object(app, "MPV_LOG_FILE", str(log_file)):
        player = app.MediaPlayer()

        class DummyProc:
            returncode = 1

            def poll(self):
                return 1

        with patch("shutil.which", return_value="/usr/bin/mpv"), \
            patch("subprocess.Popen", return_value=DummyProc()), \
            patch("os.path.exists", return_value=True), \
            patch("time.sleep"):
            success, msg = player.play_video(video_list=["test.mp4"])

        assert not success
        assert "mpv" in msg
        assert os.path.exists(log_file)


def test_play_video_passes_paths(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}")
    with patch.object(app, "CONFIG_FILE", str(cfg)):
        player = app.MediaPlayer()

        class DummyProc:
            def poll(self):
                return None

        with patch("shutil.which", return_value="/usr/bin/mpv"), \
            patch("subprocess.Popen", return_value=DummyProc()) as popen_mock, \
            patch("os.path.exists", return_value=True), \
            patch("time.sleep"):
            player.play_video(video_list=["a.mp4", "b.mp4"])

        args, _ = popen_mock.call_args
        cmd = args[0]
        assert os.path.join(app.VIDEO_DIR, "a.mp4") in cmd
        assert os.path.join(app.VIDEO_DIR, "b.mp4") in cmd

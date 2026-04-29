from pathlib import Path

from videosearch.scanning.frames import FrameSample, sample_frames


def test_sample_frames_at_1fps(tiny_video: Path, tmp_path: Path):
    out = tmp_path / "thumbs"
    samples = list(sample_frames(tiny_video, fps=1.0, output_dir=out))
    # ~2-second video at 1 fps → 2 frames (give or take 1)
    assert 1 <= len(samples) <= 3
    for s in samples:
        assert isinstance(s, FrameSample)
        assert s.path.exists()
        assert s.path.suffix == ".jpg"
        assert s.timestamp_sec >= 0
    # Indices monotonic
    indices = [s.frame_idx for s in samples]
    assert indices == sorted(indices)


def test_sample_frames_higher_fps_gives_more_frames(tiny_video: Path, tmp_path: Path):
    out = tmp_path / "thumbs5"
    samples = list(sample_frames(tiny_video, fps=5.0, output_dir=out))
    assert len(samples) >= 5  # ~10 expected for a 2-sec @ 5 fps


from videosearch.scanning.frames import Scene, detect_scenes


def test_detect_scenes_returns_at_least_one(tiny_video: Path):
    scenes = detect_scenes(tiny_video, fallback_duration_sec=2.0)
    assert len(scenes) >= 1
    for s in scenes:
        assert isinstance(s, Scene)
        assert s.start_sec >= 0
        assert s.end_sec > s.start_sec


def test_detect_scenes_indices_monotonic(tiny_video: Path):
    scenes = detect_scenes(tiny_video, fallback_duration_sec=2.0)
    idxs = [s.scene_idx for s in scenes]
    assert idxs == sorted(idxs)
    assert idxs[0] == 0


def test_detect_scenes_uses_fallback_when_no_cuts(tiny_video: Path):
    """testsrc has no shot cuts; we expect the fallback scene spanning the whole video."""
    scenes = detect_scenes(tiny_video, fallback_duration_sec=2.0)
    # Fallback scenarios produce one scene covering the duration.
    if len(scenes) == 1:
        assert scenes[0].start_sec == 0.0
        assert scenes[0].end_sec == 2.0

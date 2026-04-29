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

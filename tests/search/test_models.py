from videosearch.search.models import Moment, SearchResponse, VideoResult


def test_moment_construction():
    m = Moment(timestamp_sec=1.5, score=0.8, thumb_path="/tmp/t.jpg", caption=None)
    assert m.timestamp_sec == 1.5
    assert m.score == 0.8
    assert m.thumb_path == "/tmp/t.jpg"
    assert m.caption is None


def test_moment_with_caption():
    m = Moment(timestamp_sec=2.0, score=0.5, thumb_path=None, caption="a scene")
    assert m.caption == "a scene"
    assert m.thumb_path is None


def test_video_result_construction():
    moments = [Moment(timestamp_sec=1.0, score=0.9, thumb_path=None, caption=None)]
    vr = VideoResult(video_id="v1", top_score=0.9, moments=moments)
    assert vr.video_id == "v1"
    assert vr.top_score == 0.9
    assert len(vr.moments) == 1


def test_search_response_construction():
    vr = VideoResult(video_id="v1", top_score=0.7, moments=[])
    resp = SearchResponse(query="cats", results=[vr])
    assert resp.query == "cats"
    assert len(resp.results) == 1

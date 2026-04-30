from videosearch.search.rrf import rrf_fuse


def test_single_list_preserves_order():
    result = rrf_fuse([["a", "b", "c"]])
    ids = [id_ for id_, _ in result]
    scores = [s for _, s in result]
    assert ids == ["a", "b", "c"]
    assert scores[0] > scores[1] > scores[2]


def test_item_in_both_lists_scores_higher():
    result = rrf_fuse([["a", "b"], ["b", "c"]])
    scores = {id_: s for id_, s in result}
    # "b" appears at rank 1 in list 0 and rank 0 in list 1 → highest combined score
    assert scores["b"] > scores["a"]
    assert scores["b"] > scores["c"]


def test_empty_input_returns_empty():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[]]) == []


def test_k_parameter_affects_score_magnitude():
    result_k1 = rrf_fuse([["a"]], k=1)
    result_k60 = rrf_fuse([["a"]], k=60)
    # k=1: 1/(1+0+1)=0.5; k=60: 1/(60+0+1)≈0.0164
    assert result_k1[0][1] > result_k60[0][1]


def test_returns_all_unique_ids():
    result = rrf_fuse([["a", "b"], ["b", "c", "d"]])
    ids = [id_ for id_, _ in result]
    assert set(ids) == {"a", "b", "c", "d"}

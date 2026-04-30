from __future__ import annotations


def rrf_fuse(ranked_lists: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Merge N ranked ID lists using Reciprocal Rank Fusion: score(d) = Σ 1/(k+rank+1)."""
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, id_ in enumerate(ranked):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

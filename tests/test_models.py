"""Tests for model scoring and selection."""

from datetime import datetime, timezone, timedelta

from modules.models import (
    ModelCandidate,
    _compute_scores,
    _normalize,
    _freshness,
    _recency,
    _days_since,
)


def _make_candidate(
    repo_id="test/model",
    downloads=1000,
    likes=100,
    trending_score=5.0,
    age_days=30,
    modified_days=7,
    size_gb=5.0,
):
    now = datetime.now(timezone.utc)
    return ModelCandidate(
        repo_id=repo_id,
        pipeline="text-generation",
        downloads=downloads,
        size_gb=size_gb,
        format="mlx",
        likes=likes,
        trending_score=trending_score,
        created_at=(now - timedelta(days=age_days)).isoformat(),
        last_modified=(now - timedelta(days=modified_days)).isoformat(),
    )


def test_normalize_basic():
    assert _normalize([0, 5, 10]) == [0.0, 0.5, 1.0]


def test_normalize_identical():
    result = _normalize([5, 5, 5])
    assert all(v == 0.5 for v in result)


def test_freshness_decays_with_age():
    now = datetime.now(timezone.utc)
    fresh = _freshness((now - timedelta(days=1)).isoformat(), now)
    old = _freshness((now - timedelta(days=180)).isoformat(), now)
    assert fresh > old
    assert fresh > 0.9  # 1 day old should be near 1.0
    assert old < 0.3    # 180 days old should be low


def test_freshness_unknown_date():
    now = datetime.now(timezone.utc)
    result = _freshness("", now)
    assert result < 0.1  # unknown = assume old


def test_recency_recent():
    now = datetime.now(timezone.utc)
    result = _recency((now - timedelta(days=3)).isoformat(), now)
    assert result == 1.0


def test_recency_old():
    now = datetime.now(timezone.utc)
    result = _recency((now - timedelta(days=100)).isoformat(), now)
    assert result == 0.0


def test_scoring_favors_trending_recent():
    """A recent trending model should score higher than an old downloaded one."""
    new_trending = _make_candidate(
        repo_id="new/hot",
        downloads=500,
        likes=200,
        trending_score=50.0,
        age_days=10,
        modified_days=2,
    )
    old_popular = _make_candidate(
        repo_id="old/popular",
        downloads=100000,
        likes=50,
        trending_score=1.0,
        age_days=300,
        modified_days=200,
    )

    candidates = [new_trending, old_popular]
    _compute_scores(candidates)

    assert new_trending.score > old_popular.score


def test_scoring_single_candidate():
    """Single candidate should get a valid score."""
    c = _make_candidate()
    _compute_scores([c])
    assert 0.0 <= c.score <= 1.0


def test_scoring_empty_list():
    _compute_scores([])  # should not raise


def test_days_since_valid():
    now = datetime.now(timezone.utc)
    iso = (now - timedelta(days=10)).isoformat()
    result = _days_since(iso, now)
    assert 9.9 < result < 10.1


def test_days_since_invalid():
    now = datetime.now(timezone.utc)
    result = _days_since("not-a-date", now)
    assert result == 365.0

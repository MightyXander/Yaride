"""Служба сохранения оценки и текстового отзыва (тонкая обёртка над репозиторием)."""

from __future__ import annotations

from app.repo import Repo
from app.security.rating_input import normalize_review_text


class RatingService:
    def __init__(self, repo: Repo) -> None:
        self._repo = repo

    def submit(
        self,
        rater_tg_user_id: int,
        trip_id: int,
        rated_tg_user_id: int,
        stars: int,
        raw_review: str | None,
    ) -> None:
        review = normalize_review_text(raw_review)
        self._repo.submit_trip_rating(
            rater_tg_user_id,
            trip_id,
            rated_tg_user_id,
            stars,
            review_text=review,
        )

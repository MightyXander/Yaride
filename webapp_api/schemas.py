"""Pydantic-модели запросов Mini App API. Ответы отдаём как dict (через сериализаторы в serializers.py)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    role: str  # 'driver' | 'passenger'
    dl_series_number: str | None = None
    dl_valid_until: str | None = None  # ISO YYYY-MM-DD
    car_model: str | None = None
    car_color: str | None = None
    car_plate: str | None = None


class CreateTripRequest(BaseModel):
    start_point_id: int
    end_point_id: int
    trip_date: str  # YYYY-MM-DD
    departure_time: str  # HH:MM
    price_rub: int = Field(gt=0)
    seats_total: int = Field(ge=1, le=8)
    comment: str | None = Field(default=None, max_length=500)


class BookRequest(BaseModel):
    trip_id: int


class CancelBookingRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RateRequest(BaseModel):
    trip_id: int
    rated_tg_user_id: int
    stars: int = Field(ge=1, le=5)
    review_text: str | None = Field(default=None, max_length=500)


class FavoriteRequest(BaseModel):
    # Можно добавить избранное либо по паре точек, либо из конкретной поездки.
    start_point_id: int | None = None
    end_point_id: int | None = None
    trip_id: int | None = None


class CreateTemplateRequest(BaseModel):
    start_point_id: int
    end_point_id: int
    price_rub: int = Field(gt=0)
    seats_total: int = Field(ge=1, le=8)
    comment: str | None = Field(default=None, max_length=500)


class PublishTemplateRequest(BaseModel):
    trip_date: str  # YYYY-MM-DD
    departure_time: str  # HH:MM


class PassengerRatingThresholdRequest(BaseModel):
    threshold: str  # "3.0" | "4.0" | "4.5" | "off"

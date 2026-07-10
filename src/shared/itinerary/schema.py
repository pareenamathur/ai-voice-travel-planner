"""Canonical itinerary JSON schema (Phase 3 Task 1).

Pydantic models for the day-wise itinerary structure stored in session state,
passed through Planning/Edit artifacts, and produced by the Itinerary Builder MCP
in later phases. No scheduling logic lives here.
"""

from __future__ import annotations

from datetime import date as Date
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator


class TransportMode(StrEnum):
    WALK = "walk"
    DRIVE = "drive"
    TRANSIT = "transit"
    RIDE_HAIL = "ride_hail"
    OTHER = "other"


class ActivityCategory(StrEnum):
    SIGHTSEEING = "sightseeing"
    CULTURE = "culture"
    FOOD = "food"
    SHOPPING = "shopping"
    NATURE = "nature"
    REST = "rest"
    OTHER = "other"


class TravelerConstraints(BaseModel):
    """Traveler preferences and constraints applied to the itinerary."""

    interests: list[str] = Field(default_factory=list)
    pace: str | None = None
    party_size: int | None = Field(default=None, ge=1)
    mobility_notes: str | None = None
    daily_window_start: str | None = Field(
        default=None,
        description="Preferred daily start time (HH:MM).",
        pattern=r"^\d{2}:\d{2}$",
    )
    daily_window_end: str | None = Field(
        default=None,
        description="Preferred daily end time (HH:MM).",
        pattern=r"^\d{2}:\d{2}$",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class PoiReference(BaseModel):
    """Normalized POI reference used by itinerary activities."""

    poi_id: str = Field(..., min_length=1, description="Stable POI identifier (e.g. OSM id).")
    name: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    category: str | None = None
    source: str = Field(default="osm", examples=["osm"])
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    """Grounding citation attached to an itinerary or activity."""

    citation_id: str = Field(..., min_length=1)
    source_url: str | None = None
    section: str | None = None
    document_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Activity(BaseModel):
    """A single scheduled stop within a day plan."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    poi_id: str | None = Field(
        default=None,
        description="Reference to a POI in the itinerary poi_registry.",
    )
    category: ActivityCategory | str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_time: str | None = Field(
        default=None,
        description="Local start time (HH:MM).",
        pattern=r"^\d{2}:\d{2}$",
    )
    end_time: str | None = Field(
        default=None,
        description="Local end time (HH:MM).",
        pattern=r"^\d{2}:\d{2}$",
    )
    duration_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TravelSegment(BaseModel):
    """Travel leg between two activities."""

    from_activity_id: str = Field(..., min_length=1)
    to_activity_id: str = Field(..., min_length=1)
    travel_minutes: int = Field(..., ge=0)
    transport_mode: TransportMode | str = TransportMode.WALK
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DayPlan(BaseModel):
    """One day within an itinerary."""

    day_number: int = Field(..., ge=1)
    date: Date | None = None
    notes: str | None = None
    activities: list[Activity] = Field(default_factory=list)
    travel_segments: list[TravelSegment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Itinerary(BaseModel):
    """Canonical itinerary document."""

    city: str = Field(..., min_length=1)
    total_days: int = Field(..., ge=1)
    start_date: Date | None = None
    traveler_constraints: TravelerConstraints = Field(default_factory=TravelerConstraints)
    days: list[DayPlan] = Field(default_factory=list)
    poi_registry: list[PoiReference] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("days")
    @classmethod
    def validate_day_count(cls, days: list[DayPlan]) -> list[DayPlan]:
        if not days:
            return days

        day_numbers = [day.day_number for day in days]
        if len(day_numbers) != len(set(day_numbers)):
            raise ValueError("day_number values must be unique within an itinerary")
        return days

    @model_validator(mode="after")
    def validate_total_days(self) -> Self:
        if self.days and len(self.days) > self.total_days:
            raise ValueError("days length cannot exceed total_days")
        return self

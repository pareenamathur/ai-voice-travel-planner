/**
 * TypeScript mirror of ``src/shared/itinerary/schema.py`` (canonical Itinerary).
 * JSON field names and optionality match the Pydantic models exactly.
 */

export type TransportMode = "walk" | "drive" | "transit" | "ride_hail" | "other" | string;

export type ActivityCategory =
  | "sightseeing"
  | "culture"
  | "food"
  | "shopping"
  | "nature"
  | "rest"
  | "other"
  | string;

export interface TravelerConstraints {
  interests?: string[];
  pace?: string | null;
  party_size?: number | null;
  mobility_notes?: string | null;
  daily_window_start?: string | null;
  daily_window_end?: string | null;
  metadata?: Record<string, unknown>;
}

export interface PoiReference {
  poi_id: string;
  name: string;
  latitude: number;
  longitude: number;
  category?: string | null;
  source?: string;
  metadata?: Record<string, unknown>;
}

export interface Citation {
  citation_id: string;
  source_url?: string | null;
  section?: string | null;
  document_id?: string | null;
  metadata?: Record<string, unknown>;
}

export interface Activity {
  id: string;
  title: string;
  poi_id?: string | null;
  category?: ActivityCategory | null;
  latitude?: number | null;
  longitude?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes?: number | null;
  notes?: string | null;
  citations?: Citation[];
  metadata?: Record<string, unknown>;
}

export interface TravelSegment {
  from_activity_id: string;
  to_activity_id: string;
  travel_minutes: number;
  transport_mode?: TransportMode;
  notes?: string | null;
  metadata?: Record<string, unknown>;
}

export interface DayPlan {
  day_number: number;
  date?: string | null;
  notes?: string | null;
  activities?: Activity[];
  travel_segments?: TravelSegment[];
  metadata?: Record<string, unknown>;
}

/** Canonical itinerary document (props contract for ItineraryView). */
export interface Itinerary {
  city: string;
  total_days: number;
  start_date?: string | null;
  traveler_constraints?: TravelerConstraints;
  days?: DayPlan[];
  poi_registry?: PoiReference[];
  citations?: Citation[];
  metadata?: Record<string, unknown>;
}

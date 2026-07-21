from __future__ import annotations

import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from icalendar import Calendar

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "appdaemon" / "apps"))
import openmeteo2ical  # noqa: E402


class OpenMeteo2ICalTests(unittest.TestCase):
    def test_build_calendar_is_parseable_and_contains_visibility(self) -> None:
        forecast = {
            "latitude": 48.7424,
            "longitude": 9.10785,
            "timezone": "Europe/Berlin",
            "location": "Dachswald",
            "calendar_name": "Dachswald Wetter",
            "days": [
                {
                    "uid_prefix": "487424-910785",
                    "date_ical": "20260720",
                    "weather_code": 0,
                    "temp_min": 10,
                    "temp_max": 22,
                    "sunrise_local": "05:40",
                    "sunset_local": "21:15",
                    "daylight_h": 15.6,
                    "precip_sum": 1.2,
                    "precip_hours": 0.5,
                    "wind_speed_max": 28,
                    "uv_index_max": 7.3,
                    "generated_local": "2026-07-20 15:44:14",
                    "three_hour_chunks": [
                        {
                            "start_h": 0,
                            "end_h": 3,
                            "weather_code": 1,
                            "temperature": 13,
                            "apparent_temperature": 12,
                            "humidity": 84,
                            "precip_probability": 12,
                            "precipitation": 0.0,
                            "wind_speed": 6,
                            "wind_direction": 220,
                            "visibility": 9000,
                        }
                    ],
                }
            ],
        }

        ical = openmeteo2ical.build_calendar(
            forecast,
            generated_at=datetime(2026, 7, 20, 13, 44, 14, tzinfo=UTC),
            source_url="https://api.open-meteo.com/v1/forecast",
        )

        parsed = Calendar.from_ical(ical)
        events = [component for component in parsed.walk() if component.name == "VEVENT"]

        self.assertEqual(len(events), 1)
        description = str(events[0].get("description"))
        self.assertIn("👀9.0km", description)
        self.assertIn("Forecast by Open-Meteo", description)
        self.assertLess(description.index("0h -  3h"), description.index("🌅 Sunrise"))


if __name__ == "__main__":
    unittest.main()

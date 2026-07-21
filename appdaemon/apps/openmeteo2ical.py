from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

try:
    from appdaemon.plugins.hass import hassapi as hass
except ImportError:  # pragma: no cover - enables local testing without AppDaemon
    class _HassBase:
        pass

    class hass:  # type: ignore
        Hass = _HassBase


HOURLY_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "visibility",
    "weather_code",
]

DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "sunrise",
    "sunset",
    "daylight_duration",
    "precipitation_sum",
    "precipitation_hours",
    "wind_speed_10m_max",
    "uv_index_max",
]

WEATHER_EMOJI = {
    0: "☀️",
    1: "🌤",
    2: "⛅",
    3: "☁️",
    45: "🌫",
    48: "🌫",
    51: "🌦",
    53: "🌦",
    55: "🌧",
    56: "🌧",
    57: "🌧",
    61: "🌧",
    63: "🌧",
    65: "🌧",
    66: "🌧",
    67: "🌧",
    71: "🌨",
    73: "🌨",
    75: "❄️",
    77: "❄️",
    80: "🌦",
    81: "🌧",
    82: "⛈",
    85: "🌨",
    86: "🌨",
    95: "⛈",
    96: "⛈",
    99: "⛈",
}


def to_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def to_float(value: Any) -> float:
    return float(value)


def to_int(value: Any) -> int:
    return int(round(float(value)))


def weather_emoji(code: Any) -> str:
    return WEATHER_EMOJI.get(to_int(code), "❓")


def build_calendar(forecast: dict[str, Any], generated_at: datetime, source_url: str) -> str:
    timestamp = generated_at.astimezone(UTC)
    calendar = Calendar()
    calendar.add("prodid", "openmeteo2ical")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("X-WR-CALNAME", forecast["calendar_name"])
    calendar.add("X-WR-TIMEZONE", forecast["timezone"])
    calendar.add("X-PUBLISHED-TTL", "PT1H")

    for index, day in enumerate(forecast["days"]):
        summary = (
            f"{weather_emoji(day['weather_code'])} "
            f"{round(to_float(day['temp_min']))}°C / {round(to_float(day['temp_max']))}°C"
        )

        aggregate_lines = []
        for chunk in day["three_hour_chunks"]:
            aggregate_lines.append(
                (
                    f"{chunk['start_h']:>2}h - {chunk['end_h']:>2}h: "
                    f"{weather_emoji(chunk['weather_code'])} "
                    f"🌡{round(to_float(chunk['temperature']))}°C "
                    f"🤗{round(to_float(chunk['apparent_temperature']))}°C "
                    f"💧{round(to_float(chunk['humidity']))}% "
                    f"☔{round(to_float(chunk['precip_probability']))}% "
                    f"🌧{to_float(chunk['precipitation']):.1f}mm "
                    f"💨{round(to_float(chunk['wind_speed']))}km/h "
                    f"🧭{round(to_float(chunk['wind_direction']))}° "
                    f"👀{to_float(chunk['visibility']) / 1000:.1f}km"
                )
            )

        details = [
            f"🌅 Sunrise: {day['sunrise_local']}",
            f"🌇 Sunset: {day['sunset_local']}",
            f"☀️ Daylight: {round(to_float(day['daylight_h']), 1)} h",
            f"☔ Precipitation: {to_float(day['precip_sum']):.1f} mm ({to_float(day['precip_hours']):.1f} h)",
            f"💨 Max wind: {round(to_float(day['wind_speed_max']))} km/h",
            f"🧴 UV max: {to_float(day['uv_index_max']):.1f}",
            f"Last update: {day['generated_local']}",
            "Forecast by Open-Meteo",
            source_url,
        ]

        event = Event()
        event.add("uid", f"{day['uid_prefix']}-{index}@openmeteo2ical")
        event.add("sequence", 1)
        event.add("class", "PUBLIC")
        event.add("created", datetime(2020, 1, 1, tzinfo=UTC))
        event.add("geo", (forecast["latitude"], forecast["longitude"]))
        event.add("dtstamp", timestamp)
        event.add("dtstart", date.fromisoformat(day["date_ical"][0:4] + "-" + day["date_ical"][4:6] + "-" + day["date_ical"][6:8]))
        event.add("description", "\n".join([*aggregate_lines, "", *details]))
        event.add("location", forecast["location"])
        event.add("url", "https://open-meteo.com/")
        event.add("status", "CONFIRMED")
        event.add("summary", summary)
        event.add("transp", "TRANSPARENT")
        calendar.add_component(event)

    return calendar.to_ical().decode("utf-8")


class OpenMeteoToICal(hass.Hass):
    def initialize(self) -> None:
        self.latitude = float(self.args.get("latitude"))
        self.longitude = float(self.args.get("longitude"))
        self.location = str(self.args.get("location", "Weather"))
        self.calendar_name = str(self.args.get("calendar_name", f"{self.location} Wetter"))
        self.timezone = str(self.args.get("timezone", "Europe/Berlin"))
        self.output_file = Path(self.args.get("output_file", "/config/www/openmeteo.ics"))
        self.forecast_days = min(max(int(self.args.get("forecast_days", 14)), 1), 16)
        self.interval_minutes = max(int(self.args.get("interval_minutes", 60)), 15)
        self.include_past_days = max(int(self.args.get("past_days", 0)), 0)

        self.log(
            f"openmeteo2ical started for {self.location} ({self.latitude}, {self.longitude}), "
            f"updating every {self.interval_minutes} minutes"
        )

        self.update_ical({})
        self.run_every(self.update_ical, "now+00:01:00", self.interval_minutes * 60)

    def update_ical(self, _: dict[str, Any]) -> None:
        try:
            generated_at = datetime.now(tz=UTC)
            forecast = self.fetch_forecast(generated_at)
            ical_text = build_calendar(forecast, generated_at, self.args.get("source_url", "https://api.open-meteo.com/v1/forecast"))
            self.write_output(ical_text)
            self.log(f"Wrote iCal forecast with {len(forecast['days'])} events to {self.output_file}")
        except Exception as exc:  # pragma: no cover
            self.error(f"openmeteo2ical update failed: {exc}")

    def fetch_forecast(self, generated_at: datetime) -> dict[str, Any]:
        import openmeteo_requests

        client = openmeteo_requests.Client()
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": HOURLY_VARIABLES,
            "daily": DAILY_VARIABLES,
            "timezone": self.timezone,
            "forecast_days": self.forecast_days,
            "past_days": self.include_past_days,
            "wind_speed_unit": self.args.get("wind_speed_unit", "kmh"),
            "temperature_unit": self.args.get("temperature_unit", "celsius"),
            "precipitation_unit": self.args.get("precipitation_unit", "mm"),
        }

        response = client.weather_api("https://api.open-meteo.com/v1/forecast", params=params)[0]
        timezone = to_text(response.Timezone())
        tz = ZoneInfo(timezone)

        hourly = response.Hourly()
        hourly_time = list(range(hourly.Time(), hourly.TimeEnd(), hourly.Interval()))
        hourly_data = {
            variable: hourly.Variables(index).ValuesAsNumpy()
            for index, variable in enumerate(HOURLY_VARIABLES)
        }

        hourly_rows: dict[str, list[dict[str, Any]]] = {}
        for idx, timestamp in enumerate(hourly_time):
            local_dt = datetime.fromtimestamp(timestamp, tz=UTC).astimezone(tz)
            key = local_dt.date().isoformat()
            row = {
                "start_h": local_dt.hour,
                "end_h": min(local_dt.hour + 3, 24),
                "temperature": hourly_data["temperature_2m"][idx],
                "apparent_temperature": hourly_data["apparent_temperature"][idx],
                "humidity": hourly_data["relative_humidity_2m"][idx],
                "precip_probability": hourly_data["precipitation_probability"][idx],
                "precipitation": hourly_data["precipitation"][idx],
                "wind_speed": hourly_data["wind_speed_10m"][idx],
                "wind_direction": hourly_data["wind_direction_10m"][idx],
                "visibility": hourly_data["visibility"][idx],
                "weather_code": hourly_data["weather_code"][idx],
            }
            if local_dt.hour % 3 == 0:
                hourly_rows.setdefault(key, []).append(row)

        daily = response.Daily()
        daily_time = list(range(daily.Time(), daily.TimeEnd(), daily.Interval()))
        daily_data = {
            variable: daily.Variables(index).ValuesAsNumpy()
            for index, variable in enumerate(DAILY_VARIABLES)
        }

        uid_prefix = f"{str(self.latitude).replace('.', '')}-{str(self.longitude).replace('.', '')}"
        days: list[dict[str, Any]] = []
        for idx, timestamp in enumerate(daily_time):
            local_dt = datetime.fromtimestamp(timestamp, tz=UTC).astimezone(tz)
            key = local_dt.date().isoformat()
            sunrise = datetime.fromtimestamp(daily_data["sunrise"][idx], tz=UTC).astimezone(tz)
            sunset = datetime.fromtimestamp(daily_data["sunset"][idx], tz=UTC).astimezone(tz)
            days.append(
                {
                    "uid_prefix": uid_prefix,
                    "date_ical": local_dt.strftime("%Y%m%d"),
                    "weather_code": daily_data["weather_code"][idx],
                    "temp_min": daily_data["temperature_2m_min"][idx],
                    "temp_max": daily_data["temperature_2m_max"][idx],
                    "sunrise_local": sunrise.strftime("%H:%M"),
                    "sunset_local": sunset.strftime("%H:%M"),
                    "daylight_h": to_float(daily_data["daylight_duration"][idx]) / 3600,
                    "precip_sum": daily_data["precipitation_sum"][idx],
                    "precip_hours": daily_data["precipitation_hours"][idx],
                    "wind_speed_max": daily_data["wind_speed_10m_max"][idx],
                    "uv_index_max": daily_data["uv_index_max"][idx],
                    "generated_local": generated_at.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S"),
                    "three_hour_chunks": hourly_rows.get(key, []),
                }
            )

        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": timezone,
            "location": self.location,
            "calendar_name": self.calendar_name,
            "days": days,
        }

    def write_output(self, content: str) -> None:
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.output_file.with_suffix(f"{self.output_file.suffix}.tmp")
        temp_file.write_text(content, encoding="utf-8")
        temp_file.replace(self.output_file)

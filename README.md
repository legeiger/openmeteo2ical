# openmeteo2ical

Home Assistant AppDaemon app that converts Open-Meteo forecast data into an iCal file.

![Screenshot of resulting calendar entries](https://raw.githubusercontent.com/legeiger/openmeteo2ical/main/screenshot_calendar.png)

## Features
- Generates an `.ics` file every hour (configurable) for up to 14 days (max 16 by API)
- Uses `openmeteo-requests` + `icalendar` for RFC-compliant output
- Keeps calendar format close to provider-style daily events, with richer emoji-based details
- Configurable via `appdaemon/apps/apps.yaml`

## Install
```bash
pip install openmeteo-requests icalendar numpy<2.4.0
```

## Configure
Copy and adapt:
- `/home/runner/work/openmeteo2ical/openmeteo2ical/appdaemon/apps/apps.yaml`

Set at least:
- `latitude`
- `longitude`
- `location`
- `output_file`

## Run
Place `/home/runner/work/openmeteo2ical/openmeteo2ical/appdaemon/apps/openmeteo2ical.py` in your AppDaemon apps folder and restart AppDaemon.

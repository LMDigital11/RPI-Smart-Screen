import requests

from config import config

WMO_CODES = {
    0: ("clear", "Clear sky"),
    1: ("mostly_clear", "Mostly clear"),
    2: ("partly_cloudy", "Partly cloudy"),
    3: ("overcast", "Overcast"),
    45: ("fog", "Fog"),
    48: ("fog", "Rime fog"),
    51: ("drizzle", "Light drizzle"),
    53: ("drizzle", "Drizzle"),
    55: ("drizzle", "Heavy drizzle"),
    61: ("rain", "Light rain"),
    63: ("rain", "Rain"),
    65: ("rain", "Heavy rain"),
    71: ("snow", "Light snow"),
    73: ("snow", "Snow"),
    75: ("snow", "Heavy snow"),
    80: ("rain", "Rain showers"),
    81: ("rain", "Rain showers"),
    82: ("rain", "Violent showers"),
    95: ("storm", "Thunderstorm"),
    96: ("storm", "Thunderstorm with hail"),
    99: ("storm", "Thunderstorm with hail"),
}

ENDPOINT = "https://api.open-meteo.com/v1/forecast"


class WeatherService:
    def get(self, force=False):
        wc = config.get()["weather"]
        lat, lon = wc.get("latitude"), wc.get("longitude")
        if lat is None or lon is None:
            return {"available": False}
        unit = "fahrenheit" if wc.get("unit") == "fahrenheit" else "celsius"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "weather_code,is_day,wind_speed_10m"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "sunrise,sunset,precipitation_probability_max"
            ),
            "timezone": "auto",
            "forecast_days": 1,
            "temperature_unit": unit,
            "wind_speed_unit": "kmh",
        }
        try:
            resp = requests.get(ENDPOINT, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            current = data["current"]
            daily = data["daily"]
            code = current["weather_code"]
            icon, label = WMO_CODES.get(code, ("clear", "Unknown"))
            return {
                "available": True,
                "condition": label,
                "icon": icon,
                "is_day": bool(current.get("is_day", 1)),
                "temperature": current["temperature_2m"],
                "feels_like": current["apparent_temperature"],
                "humidity": current["relative_humidity_2m"],
                "wind_kmh": current["wind_speed_10m"],
                "high": daily["temperature_2m_max"][0],
                "low": daily["temperature_2m_min"][0],
                "sunrise": daily["sunrise"][0],
                "sunset": daily["sunset"][0],
                "rain_chance": daily.get("precipitation_probability_max", [0])[0],
                "unit": unit,
            }
        except requests.RequestException:
            return {"available": False}


weather = WeatherService()
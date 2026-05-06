"""天气查询工具 - 使用 Open-Meteo API（免费无需 API key）"""
import httpx
from datetime import datetime
from typing import Any, Dict, Optional

from ..base import BaseTool, ToolResult


class WeatherTool(BaseTool):
    name: str = "weather"
    description: str = "查询全球城市的实时天气和天气预报，支持当前天气和未来7天预报。"
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "城市名称（如：上海、北京、Shanghai、Beijing）"},
            "country": {"type": "string", "description": "国家代码（如：CN、US），可选"},
            "forecast_days": {
                "type": "integer",
                "description": "预报天数（1-7），不填则返回当前天气",
                "minimum": 1,
                "maximum": 7,
            },
        },
        "required": ["city"],
    }

    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

    CITY_COORDS = {
        "上海": (31.2304, 121.4737),
        "北京": (39.9042, 116.4074),
        "广州": (23.1291, 113.2644),
        "深圳": (22.5431, 114.0579),
        "杭州": (30.2741, 120.1551),
        "成都": (30.5728, 104.0668),
        "武汉": (30.5928, 114.3055),
        "西安": (34.3416, 108.9398),
        "重庆": (29.4316, 106.9123),
        "南京": (32.0603, 118.7969),
        "天津": (39.3434, 117.3616),
        "苏州": (31.2989, 120.5853),
        "郑州": (34.7466, 113.6253),
        "长沙": (28.2282, 112.9388),
        "青岛": (36.0671, 120.3826),
        "沈阳": (41.8057, 123.4328),
        "宁波": (29.8683, 121.5440),
        "厦门": (24.4798, 118.0894),
        "大连": (38.9140, 121.6147),
        "东莞": (23.0489, 113.7447),
    }

    async def execute(self, **kwargs) -> ToolResult:
        city = kwargs.get("city", "").strip()
        forecast_days = kwargs.get("forecast_days")

        if not city:
            return ToolResult(success=False, output="", error="请提供城市名称")

        try:
            lat, lon = await self._get_coordinates(city)
            if lat is None:
                return ToolResult(success=False, output="", error=f"找不到城市: {city}")

            if forecast_days and forecast_days > 0:
                return await self._get_forecast(lat, lon, forecast_days)
            return await self._get_current_weather(lat, lon, city)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"天气查询失败: {str(e)}")

    async def _get_coordinates(self, city: str) -> tuple:
        if city in self.CITY_COORDS:
            return self.CITY_COORDS[city]

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.GEOCODE_URL, params={"name": city, "count": 1, "language": "zh", "format": "json"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("results"):
                    r = data["results"][0]
                    return (r["latitude"], r["longitude"])
        return (None, None)

    async def _get_current_weather(self, lat: float, lon: float, city: str) -> ToolResult:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "timezone": "Asia/Shanghai",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.WEATHER_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                cw = data.get("current_weather", {})

                weather_code = cw.get("weathercode", 0)
                weather_desc = self._get_weather_desc(weather_code)
                temperature = cw.get("temperature", 0)
                windspeed = cw.get("windspeed", 0)

                output = (
                    f"{city} 当前天气\n"
                    f"天气状况: {weather_desc}\n"
                    f"🌡️ 温度: {temperature}°C\n"
                    f"💨 风速: {windspeed} km/h\n"
                    f"数据来源: Open-Meteo"
                )
                return ToolResult(success=True, output=output, metadata=data)
            return ToolResult(success=False, output="", error=f"API 请求失败: {resp.status_code}")

    async def _get_forecast(self, lat: float, lon: float, days: int) -> ToolResult:
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min",
            "timezone": "Asia/Shanghai",
            "forecast_days": days,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.WEATHER_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})

                dates = daily.get("time", [])
                codes = daily.get("weathercode", [])
                maxTemps = daily.get("temperature_2m_max", [])
                minTemps = daily.get("temperature_2m_min", [])

                lines = [f"📅 {days}天天气预报"]
                for i, d in enumerate(dates):
                    desc = self._get_weather_desc(codes[i] if i < len(codes) else 0)
                    max_t = maxTemps[i] if i < len(maxTemps) else 0
                    min_t = minTemps[i] if i < len(minTemps) else 0
                    dt = datetime.strptime(d, "%Y-%m-%d")
                    weekday = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][dt.weekday()]
                    lines.append(f"{dt.strftime('%m/%d')} {weekday}: {desc}, {min_t:.0f}~{max_t:.0f}°C")

                lines.append(f"\n数据来源: Open-Meteo")
                return ToolResult(success=True, output="\n".join(lines), metadata=data)
            return ToolResult(success=False, output="", error=f"API 请求失败: {resp.status_code}")

    def _get_weather_desc(self, code: int) -> str:
        mapping = {
            0: "☀️ 晴",
            1: "🌤️ 晴间多云",
            2: "⛅ 多云",
            3: "☁️ 阴",
            45: "🌫️ 雾",
            48: "🌫️ 雾凇",
            51: "🌦️ 小雨",
            53: "🌧️ 中雨",
            55: "🌧️ 大雨",
            61: "🌧️ 小雨",
            63: "🌧️ 中雨",
            65: "🌧️ 大雨",
            71: "🌨️ 小雪",
            73: "🌨️ 中雪",
            75: "❄️ 大雪",
            77: "❄️ 冰粒",
            80: "🌦️ 阵雨",
            81: "🌧️ 中阵雨",
            82: "⛈️ 强阵雨",
            85: "🌨️ 阵雪",
            86: "❄️ 强阵雪",
            95: "⛈️ 雷暴",
            96: "⛈️ 雷暴冰雹",
            99: "⛈️ 强雷暴冰雹",
        }
        return mapping.get(code, f"🌡️ 代码{code}")

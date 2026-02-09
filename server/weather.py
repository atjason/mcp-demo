import json
from urllib.parse import quote
from urllib.request import urlopen

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-mcp")

BASE_URL = "https://wis.qq.com/weather/common?source=pc&weather_type=observe&province={province}&city={city}&county={county}"


def _format_update_time(s: str) -> str:
    """Format update_time like 202602090850 -> 2026-02-09 08:50"""
    if not s or len(s) < 12:
        return s
    return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"


@mcp.tool()
def get_weather(province: str, city: str, county: str) -> str:
    """
    Get current weather for a location in China (province, city, county).
    Uses Tencent Weather API.
    """
    url = BASE_URL.format(
        province=quote(province),
        city=quote(city),
        county=quote(county),
    )
    try:
        with urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return f"获取天气失败: {e}"

    if data.get("status") != 200:
        return f"接口错误: {data.get('message', 'unknown')}"

    observe = (data.get("data") or {}).get("observe")
    if not observe:
        return "暂无观测数据"

    degree = observe.get("degree", "-")
    weather = observe.get("weather") or observe.get("weather_short", "-")
    humidity = observe.get("humidity", "-")
    wind_dir = observe.get("wind_direction_name", "-")
    wind_power = observe.get("wind_power", "-")
    raw_time = observe.get("update_time", "")
    update_time = _format_update_time(raw_time) if raw_time else "-"

    return (
        f"{province} {city} {county}：{degree}°C，{weather}，"
        f"湿度 {humidity}%，{wind_dir} {wind_power} 级，更新时间 {update_time}。"
    )


if __name__ == "__main__":
    mcp.run()

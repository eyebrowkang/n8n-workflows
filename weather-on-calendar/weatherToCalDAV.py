"""
n8n Code in Python

Weather to CalDAV
从 OpenWeatherMap JSON 数据提取天气信息并写入 CalDAV 日历
参考文档:
https://openweathermap.org/api/one-call-3#current
https://openweathermap.org/weather-conditions

其中 _items[0]["json"] 为前一步http request的返回值
"""

import json
import hashlib
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo

import caldav
from icalendar import Calendar, Event, Alarm

# ============ 配置区域 ============
CALDAV_URL = "https://caldav.example.com/testuser"  # CalDAV 服务器地址
CALDAV_USERNAME = "testuser"
CALDAV_PASSWORD = "password123"
CALENDAR_NAME = "Weather"  # 日历名称，不存在会自动创建
# 保留历史天气数据天数（默认保留过去 7 天；设为 0 表示不保留）
KEEP_PAST_DAYS = 7
# 天气 emoji 映射
WEATHER_EMOJI = {
    "clear sky": "☀️",
    "few clouds": "🌤️",
    "scattered clouds": "⛅",
    "broken clouds": "☁️",
    "overcast clouds": "☁️",
    "shower rain": "🌦️",
    "light rain": "🌧️",
    "moderate rain": "🌧️",
    "rain": "🌧️",
    "heavy rain": "🌧️",
    "thunderstorm": "⛈️",
    "light snow": "🌨️",
    "snow": "❄️",
    "heavy snow": "❄️",
    "mist": "🌫️",
    "fog": "🌫️",
    "haze": "🌫️",
}

def kelvin_to_celsius(k: float) -> float:
    """开尔文转摄氏度"""
    return k - 273.15


def get_weather_emoji(description: str) -> str:
    """根据天气描述获取 emoji"""
    return WEATHER_EMOJI.get(description.lower(), "🌡")


def parse_weather_data(data: dict) -> list[dict]:
    """
    解析 OpenWeatherMap JSON 数据
    返回天气事件列表
    """
    events = []
    tz = ZoneInfo(data["timezone"])
    tz_name = data.get("timezone")

    # 解析当前天气 (today)
    current = data["current"]
    current_dt = datetime.fromtimestamp(current["dt"], tz=tz)
    weather_info = current["weather"][0]

    events.append({
        "date": current_dt.date(),
        "description": weather_info["description"],
        "emoji": get_weather_emoji(weather_info["description"]),
        "temp": kelvin_to_celsius(current["temp"]),
        "feels_like": kelvin_to_celsius(current["feels_like"]),
        "humidity": current["humidity"],
        "wind_speed": current["wind_speed"],
        "is_current": True,
        "temp_min": None,
        "temp_max": None,
        "summary": f"当前: {weather_info['description']}",
        "pop": None,
        "snow": current.get("snow", {}).get("1h"),
        "rain": current.get("rain", {}).get("1h"),
        "timezone": tz_name,
    })

    # 解析未来几天天气
    for day in data["daily"]:
        day_dt = datetime.fromtimestamp(day["dt"], tz=tz)
        weather_info = day["weather"][0]

        # 跳过今天（已经用 current 处理）
        if day_dt.date() == current_dt.date():
            continue

        events.append({
            "date": day_dt.date(),
            "description": weather_info["description"],
            "emoji": get_weather_emoji(weather_info["description"]),
            "temp": kelvin_to_celsius(day["temp"]["day"]),
            "feels_like": kelvin_to_celsius(day["feels_like"]["day"]),
            "temp_min": kelvin_to_celsius(day["temp"]["min"]),
            "temp_max": kelvin_to_celsius(day["temp"]["max"]),
            "humidity": day["humidity"],
            "wind_speed": day["wind_speed"],
            "is_current": False,
            "summary": day.get("summary", weather_info["description"]),
            "pop": day.get("pop"),  # 降水概率
            "snow": day.get("snow"),
            "rain": day.get("rain"),
            "timezone": tz_name,
        })

    return events

def _timezone_from_name(name: str | None) -> timezone:
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def create_ical_event(weather: dict) -> Event:
    """创建 iCalendar 事件"""
    event = Event()

    # 生成唯一 UID（基于日期）
    uid = hashlib.md5(f"weather-{weather['date']}".encode()).hexdigest()
    event.add("uid", f"{uid}@weather-calendar")

    # 全天事件
    event.add("dtstart", weather["date"])
    event.add("dtend", weather["date"] + timedelta(days=1))

    # 标题：emoji + 温度范围
    if weather["temp_min"] is not None and weather["temp_max"] is not None:
        title = f"{weather['emoji']} {weather['temp_min']:.0f}°~{weather['temp_max']:.0f}°C"
    else:
        title = f"{weather['emoji']} {weather['temp']:.0f}°C"
    event.add("summary", title)

    # 详细描述
    desc_lines = [
        f"天气: {weather['description']}",
        f"温度: {weather['temp']:.1f}°C",
        f"体感: {weather['feels_like']:.1f}°C",
    ]

    if weather["temp_min"] is not None:
        desc_lines.append(f"最低/最高: {weather['temp_min']:.1f}°C / {weather['temp_max']:.1f}°C")

    desc_lines.extend([
        f"湿度: {weather['humidity']}%",
        f"风速: {weather['wind_speed']} m/s",
    ])

    if weather["pop"] is not None:
        desc_lines.append(f"降水概率: {weather['pop'] * 100:.0f}%")

    if weather["snow"]:
        desc_lines.append(f"降雪量: {weather['snow']} mm")

    if weather["rain"]:
        desc_lines.append(f"降雨量: {weather['rain']} mm")

    desc_lines.append(f"\n{weather['summary']}")
    tz_name = weather.get("timezone") or "UTC"
    added_at = datetime.now(_timezone_from_name(weather.get("timezone")))
    desc_lines.append(f"添加时间: {added_at.strftime('%Y-%m-%d %H:%M:%S')} ({tz_name})")

    event.add("description", "\n".join(desc_lines))
    event.add("dtstamp", datetime.now())

    # Apple Calendar can apply per-calendar default alerts even if no VALARM
    # exists. This "disabled" alarm pattern suppresses those defaults.
    alarm = Alarm()
    alarm.add("action", "NONE")
    alarm.add("trigger", datetime(1976, 4, 1, 0, 55, 45, tzinfo=timezone.utc))
    alarm.add("x-apple-default-alarm", "TRUE")
    alarm.add("x-apple-local-default-alarm", "TRUE")
    event.add_component(alarm)

    return event

def _extract_event_date(ical_event) -> date | None:
    dtstart = ical_event.get("dtstart")
    if not dtstart:
        return None
    if isinstance(dtstart, datetime):
        return dtstart.date()
    if isinstance(dtstart, date):
        return dtstart
    try:
        dt_value = dtstart.dt
    except Exception:
        dt_value = None
    else:
        if isinstance(dt_value, datetime):
            return dt_value.date()
        if isinstance(dt_value, date):
            return dt_value
    try:
        raw = dtstart.to_ical()
    except Exception:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    raw = raw.strip()
    if not raw:
        return None
    try:
        date_part = raw.split("T", 1)[0]
        return datetime.strptime(date_part, "%Y%m%d").date()
    except Exception:
        return None

def sync_to_caldav(events: list[dict], log_lines: list[str]):
    """同步天气事件到 CalDAV 日历"""
    def log(message: str):
        log_lines.append(message)

    # 连接 CalDAV 服务器
    client = caldav.DAVClient(
        url=CALDAV_URL,
        username=CALDAV_USERNAME,
        password=CALDAV_PASSWORD,
    )

    principal = client.principal()

    # 查找或创建日历
    calendar = None
    for cal in principal.calendars():
        if cal.name == CALENDAR_NAME:
            calendar = cal
            break

    if calendar is None:
        log(f"创建日历: {CALENDAR_NAME}")
        calendar = principal.make_calendar(name=CALENDAR_NAME)

    log(f"使用日历: {calendar.name}")

    # 删除旧的天气事件（基于 UID 前缀与日期范围）
    today = min((e["date"] for e in events), default=datetime.now().date())
    keep_since = today - timedelta(days=KEEP_PAST_DAYS)

    existing_events = calendar.events()
    for ev in existing_events:
        try:
            ical = ev.icalendar_component
            uid = str(ical.get("uid", ""))
            if uid.endswith("@weather-calendar"):
                ev_date = _extract_event_date(ical)
                if ev_date is None:
                    log(f"跳过未知日期事件: {ical.get('summary', 'Unknown')}")
                    continue

                if ev_date < keep_since:
                    log(f"删除过期事件: {ev_date} - {ical.get('summary', 'Unknown')}")
                    ev.delete()
                elif ev_date >= today:
                    log(f"更新事件(先删除): {ev_date} - {ical.get('summary', 'Unknown')}")
                    ev.delete()
                else:
                    log(f"保留历史事件: {ev_date} - {ical.get('summary', 'Unknown')}")
        except Exception as e:
            log(f"处理事件时出错: {e}")

    # 创建新事件
    for weather in events:
        event = create_ical_event(weather)

        cal = Calendar()
        cal.add("prodid", "-//Weather Calendar//weather-sync//CN")
        cal.add("version", "2.0")
        cal.add_component(event)

        calendar.save_event(cal.to_ical().decode("utf-8"))
        log(f"已添加: {weather['date']} - {weather['emoji']} {weather['description']}")


def main():
    log_lines: list[str] = []

    def log(message: str):
        log_lines.append(message)

    data = _items[0]["json"]
    # 提取天气数据
    events = parse_weather_data(data)

    log("=" * 50)
    log("提取到的天气数据:")
    log("=" * 50)
    for e in events:
        if e["temp_min"] is not None:
            log(f"{e['date']} {e['emoji']} {e['description']}: {e['temp_min']:.0f}°~{e['temp_max']:.0f}°C")
        else:
            log(f"{e['date']} {e['emoji']} {e['description']}: {e['temp']:.0f}°C (当前)")
    log("=" * 50)

    # 同步到 CalDAV
    sync_to_caldav(events, log_lines)

    log("✅ 天气数据已同步到日历!")

    return log_lines

logs = main()
return [{"log": logs}]

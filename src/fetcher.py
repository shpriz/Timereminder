import httpx

BASE_URL = "https://ruz.narfu.ru/"


async def fetch_schedule_html(group_id: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(BASE_URL, params={"timetable": "", "group": group_id})
        resp.raise_for_status()
        return resp.text

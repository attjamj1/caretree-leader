import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
    return _client


BOT_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")


def _to_wa(number: str) -> str:
    if not number.startswith("whatsapp:"):
        return f"whatsapp:{number}"
    return number


async def send_text(to: str, body: str):
    get_client().messages.create(
        to=_to_wa(to),
        from_=BOT_NUMBER,
        body=body,
    )


async def send_image(to: str, image_url: str, caption: str = ""):
    get_client().messages.create(
        to=_to_wa(to),
        from_=BOT_NUMBER,
        media_url=[image_url],
        body=caption,
    )


async def send_gps(to: str, lat: float, lng: float, label: str = ""):
    """Send a WhatsApp location pin."""
    get_client().messages.create(
        to=_to_wa(to),
        from_=BOT_NUMBER,
        persistent_action=[f"geo:{lat},{lng}|{label}"],
        body=f"📍 Navigate to this location.\n\n{label}",
    )


async def send_video(to: str, video_url: str, caption: str = ""):
    get_client().messages.create(
        to=_to_wa(to),
        from_=BOT_NUMBER,
        media_url=[video_url],
        body=caption,
    )


async def send_station(to: str, station, project):
    """Send the appropriate mission message for any station type."""
    footer = (
        "\n\nReply with your answer.\n"
        "Type */hint* for a clue (-{hint_cost} pts)\n"
        "Type */answer* to reveal it (-{answer_cost} pts)\n"
        "Type */status* to see your score"
    ).format(hint_cost=station.hint_cost, answer_cost=station.answer_cost)

    header = f"📍 *Station {station.station_code} — {station.name}*\n\n"
    photo_footer = "\n\n📸 *Send a photo to complete this station.*"
    gps_footer   = "\n\n📍 *Send your live location to complete this station.*"
    text_footer  = (
        "\n\nReply with your answer.\n"
        "Type */hint* for a clue (-{hint_cost} pts)\n"
        "Type */answer* to reveal it (-{answer_cost} pts)\n"
        "Type */status* to see your score"
    ).format(hint_cost=station.hint_cost, answer_cost=station.answer_cost)

    if station.mission_type == "text":
        await send_text(to, header + station.clue_text + text_footer)

    elif station.mission_type == "image":
        # Team submits a photo — bot sends the clue text and asks for a photo
        await send_text(to, header + station.clue_text + photo_footer)

    elif station.mission_type == "gps":
        await send_gps(to, station.gps_lat, station.gps_lng, station.name)
        await send_text(to, header + station.clue_text + gps_footer)

    if station.photo_required and station.mission_type != "image":
        await send_text(
            to,
            "📸 *Photo required!*\n"
            "Send a photo of your team at this station before submitting your answer."
        )


async def send_to_all_members(team, message: str):
    """Send a message to every member of a team."""
    numbers = list(team.member_numbers or [])
    if team.group_number and team.group_number not in numbers:
        numbers.insert(0, team.group_number)
    for number in numbers:
        if number:
            await send_text(number, message)


async def send_leaderboard(to: str, teams: list, project):
    """Send a live leaderboard snapshot to a number."""
    lines = [f"🏆 *{project.name} — Live Rankings*\n"]
    medals = ["🥇", "🥈", "🥉"]
    sorted_teams = sorted(teams, key=lambda t: (-t.stages_done, t.penalty_mins))

    for i, team in enumerate(sorted_teams):
        medal = medals[i] if i < 3 else f"#{i+1}"
        lines.append(
            f"{medal} *{team.name}*\n"
            f"   Stations: {team.stages_done} | "
            f"Wrong: {team.wrong_count} | "
            f"Penalty: +{team.penalty_mins}min"
        )

    await send_text(to, "\n".join(lines))
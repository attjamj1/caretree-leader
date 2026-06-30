import math
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.answer_checker import check_answer
from core.station_router import (
    get_next_station,
    get_or_create_progress,
    get_team_by_number,
)
from core import whatsapp as wa
from models.models import EventLog, Team, Project


# ─── Haversine helper ────────────────────────────────────────────────────────

def _is_close_enough(
    team_lat: float, team_lng: float,
    target_lat: float, target_lng: float,
    radius_meters: int = 50,
) -> bool:
    R = 6371000
    lat1 = math.radians(team_lat)
    lat2 = math.radians(target_lat)
    dlat = math.radians(target_lat - team_lat)
    dlng = math.radians(target_lng - team_lng)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c <= radius_meters


# ─── Entry point ─────────────────────────────────────────────────────────────

async def handle_incoming(
    from_number: str,
    body: str,
    media_url: str | None,
    latitude: float | None,
    longitude: float | None,
    db: Session,
):
    """
    Called by the webhook for every incoming WhatsApp message.
    Resolves team → dispatches to correct handler.
    """
    team = get_team_by_number(from_number, db)
    if not team:
        return
    project = team.project

    # Handle GPS location submission
    if latitude and longitude:
        await _handle_location(team, project, latitude, longitude, db)
        return

    if team.status == "waiting":
        await wa.send_text(
            team.group_number,
            "⏳ The race hasn't started yet. Sit tight!"
        )
        return

    if team.status == "finished":
        await wa.send_text(
            team.group_number,
            f"🏁 Your team has already finished! "
            f"Final score: {_calc_score(team, project)} pts"
        )
        return

    body_clean = body.strip().lower()

    # ── Commands ──────────────────────────────────────────────────────────────
    if body_clean == "/hint":
        await _handle_hint(team, project, db)
    elif body_clean == "/answer":
        await _handle_reveal(team, project, db)
    elif body_clean == "/status":
        await _handle_status(team, project, db)
    elif body_clean == "/leaderboard":
        await wa.send_leaderboard(team.group_number, project.teams, project)
    elif media_url:
        await _handle_photo(team, project, media_url, db)
    else:
        await _handle_answer(team, project, body_clean, db)


# ─── GPS location ────────────────────────────────────────────────────────────

async def _handle_location(team, project, lat: float, lng: float, db: Session):
    station = get_next_station(team, db)
    if not station or station.mission_type != "gps":
        await wa.send_text(
            team.group_number,
            "📍 Location received! But this station doesn't need a location check."
        )
        return

    if not station.gps_lat or not station.gps_lng:
        await wa.send_text(
            team.group_number,
            "📍 Location received! Now send your text answer."
        )
        return

    radius = getattr(station, 'gps_radius', None) or 50

    if _is_close_enough(lat, lng, station.gps_lat, station.gps_lng, radius_meters=radius):
        prog = get_or_create_progress(team, station, db)
        prog.completed = True
        prog.completed_at = datetime.now(timezone.utc)
        db.commit()

        _log(team, project, "correct", station.station_code,
             f"Location verified at Station {station.station_code}", 0, 0, db)

        next_station = get_next_station(team, db)
        await wa.send_text(
            team.group_number,
            f"📍 *Location verified!* ✅\n"
            f"You are at Station {station.station_code}!\n\n"
            + ("Here comes your next mission 👇" if next_station else "🏁 All done!")
        )
        if next_station:
            await wa.send_station(team.group_number, next_station, project)
        else:
            await _finish_team(team, project, db)
    else:
        _log(team, project, "wrong", station.station_code,
             f"Wrong location at Station {station.station_code}",
             -project.scoring_wrong_pts, project.scoring_wrong_time, db)

        await wa.send_text(
            team.group_number,
            f"📍 *Wrong location!*\n"
            f"You are not close enough to Station {station.station_code}.\n"
            f"-{project.scoring_wrong_pts} pts · +{project.scoring_wrong_time} min penalty\n\n"
            f"Keep looking! 🔍"
        )


# ─── Answer ───────────────────────────────────────────────────────────────────

async def _handle_answer(team: Team, project: Project, body: str, db: Session):
    station = get_next_station(team, db)
    if not station:
        await _finish_team(team, project, db)
        return

    prog = get_or_create_progress(team, station, db)

    # If team is in phase 2 of a chain station, text answers aren't accepted
    if prog.awaiting_chain:
        await wa.send_text(
            team.group_number,
            "📸 *You're on the second part of this mission!*\n"
            "Send your photo to complete this station."
        )
        return

    if station.photo_required and not prog.photo_submitted:
        await wa.send_text(
            team.group_number,
            "📸 Please send your team photo at this station before answering!"
        )
        return

    if check_answer(body, station.answer):
        # ✅ Correct

        # Chain mission — phase 1 done, reveal phase 2 clue
        if station.chain_clue:
            prog.awaiting_chain = True
            db.commit()
            _log(team, project, "correct", station.station_code,
                 f"Phase 1 complete at Station {station.station_code}", 0, 0, db)
            hint_note = f"\n\nType */hint* for a clue (-{station.hint_cost} pts)" if station.chain_hint else ""
            photo_note = "\n\n📸 *Send your photo to complete this station.*" if station.chain_photo_required else ""
            body = f"✅ *Correct!*\n\n{station.chain_clue}{hint_note}{photo_note}"
            if station.chain_media_url:
                try:
                    await wa.send_image(team.group_number, station.chain_media_url, body)
                except Exception as e:
                    # Never let a broken/missing image silently swallow the whole message —
                    # the team has already been advanced to phase 2 in the DB, so they MUST
                    # get the clue text one way or another.
                    print(f"[chain image send failed, falling back to text] {e}")
                    await wa.send_text(team.group_number, body)
            else:
                await wa.send_text(team.group_number, body)
            return

        # Normal completion
        prog.completed = True
        prog.completed_at = datetime.now(timezone.utc)
        db.commit()

        _log(team, project, "correct", station.station_code,
             f"Correct answer at Station {station.station_code}", 0, 0, db)

        next_station = get_next_station(team, db)
        if next_station:
            await wa.send_text(
                team.group_number,
                f"✅ *Correct!* Station {station.station_code} cleared!\n"
                f"Stages done: {team.stages_done} / {len(project.stations)}\n\n"
                f"Here comes your next mission 👇"
            )
            await wa.send_station(team.group_number, next_station, project)
        else:
            await _finish_team(team, project, db)
    else:
        # ❌ Wrong
        prog.wrong_answers += 1
        db.commit()

        penalty_time = project.scoring_wrong_time
        penalty_pts = project.scoring_wrong_pts
        _log(team, project, "wrong", station.station_code,
             f"Wrong answer at Station {station.station_code}",
             -penalty_pts, penalty_time, db)

        await wa.send_text(
            team.group_number,
            f"❌ *Wrong answer!*\n"
            f"-{penalty_pts} pts · +{penalty_time} min penalty added\n"
            f"Total wrong: {team.wrong_count}\n\n"
            f"Try again, or type */hint* (-{station.hint_cost} pts)"
        )


# ─── Hint ─────────────────────────────────────────────────────────────────────

async def _handle_hint(team: Team, project: Project, db: Session):
    station = get_next_station(team, db)
    if not station:
        await wa.send_text(team.group_number, "No hint available.")
        return

    prog = get_or_create_progress(team, station, db)

    # If in chain phase, use the chain hint
    if prog.awaiting_chain:
        hint = station.chain_hint
        if not hint:
            await wa.send_text(team.group_number, "No hint available for this part.")
            return
        prog.hints_used += 1
        db.commit()
        _log(team, project, "hint", station.station_code,
             f"Chain hint used at Station {station.station_code}",
             -station.hint_cost, 0, db)
        await wa.send_text(
            team.group_number,
            f"💡 *Hint*\n(-{station.hint_cost} pts deducted)\n\n{hint}"
        )
        return

    if not station.hint_text:
        await wa.send_text(team.group_number, "No hint available for this station.")
        return

    prog.hints_used += 1
    db.commit()

    _log(team, project, "hint", station.station_code,
         f"Hint used at Station {station.station_code}",
         -station.hint_cost, 0, db)

    hint_body = (
        f"💡 *Hint for Station {station.station_code}*\n"
        f"(-{station.hint_cost} pts deducted)\n\n"
        f"{station.hint_text}"
    )
    if station.hint_media_url:
        try:
            await wa.send_image(team.group_number, station.hint_media_url, hint_body)
        except Exception as e:
            print(f"[hint image send failed, falling back to text] {e}")
            await wa.send_text(team.group_number, hint_body)
    else:
        await wa.send_text(team.group_number, hint_body)


# ─── Reveal answer ────────────────────────────────────────────────────────────

async def _handle_reveal(team: Team, project: Project, db: Session):
    station = get_next_station(team, db)
    if not station:
        return

    prog = get_or_create_progress(team, station, db)
    prog.answer_revealed = True
    prog.completed = True
    prog.completed_at = datetime.now(timezone.utc)
    db.commit()

    _log(team, project, "answer_reveal", station.station_code,
         f"Answer revealed at Station {station.station_code}",
         -station.answer_cost, 0, db)

    next_station = get_next_station(team, db)
    await wa.send_text(
        team.group_number,
        f"📖 *Answer for Station {station.station_code}*\n"
        f"(-{station.answer_cost} pts deducted)\n\n"
        f"The answer was: *{station.answer}*\n\n"
        + ("Here comes your next mission 👇"
           if next_station else "That was the last station!")
    )
    if next_station:
        await wa.send_station(team.group_number, next_station, project)
    else:
        await _finish_team(team, project, db)


# ─── Photo submission ─────────────────────────────────────────────────────────

async def _handle_photo(team: Team, project: Project, media_url: str, db: Session):
    station = get_next_station(team, db)
    if not station:
        await wa.send_text(team.group_number, "📸 Photo received!")
        return

    prog = get_or_create_progress(team, station, db)

    # ── Chain phase 2: selfie completes the station ───────────────────────────
    if prog.awaiting_chain and station.chain_photo_required:
        prog.completed = True
        prog.completed_at = datetime.now(timezone.utc)
        prog.awaiting_chain = False
        prog.photo_submitted = True
        prog.photo_url = media_url
        db.commit()

        _log(team, project, "correct", station.station_code,
             f"Chain selfie at Station {station.station_code}", 0, 0, db)

        next_station = get_next_station(team, db)
        await wa.send_text(
            team.group_number,
            f"📸 *Selfie received!* ✅\n"
            f"Station {station.station_code} cleared!\n\n"
            + ("Here comes your next mission 👇" if next_station else "🏁 All done!")
        )
        if next_station:
            await wa.send_station(team.group_number, next_station, project)
        else:
            await _finish_team(team, project, db)
        return

    # Image-type station: photo IS the answer — mark complete and advance
    if station.mission_type == "image":
        prog.completed = True
        prog.completed_at = datetime.now(timezone.utc)
        prog.photo_submitted = True
        prog.photo_url = media_url
        db.commit()

        _log(team, project, "correct", station.station_code,
             f"Photo submitted at Station {station.station_code}", 0, 0, db)

        next_station = get_next_station(team, db)
        await wa.send_text(
            team.group_number,
            f"📸 *Photo received!* ✅\n"
            f"Station {station.station_code} cleared!\n\n"
            + ("Here comes your next mission 👇" if next_station else "🏁 All done!")
        )
        if next_station:
            await wa.send_station(team.group_number, next_station, project)
        else:
            await _finish_team(team, project, db)
        return

    # Other station types: photo is a prerequisite, not the answer
    if not station.photo_required:
        await wa.send_text(
            team.group_number,
            "📸 Photo received! You can now submit your answer."
        )
        return

    prog.photo_submitted = True
    prog.photo_url = media_url
    db.commit()

    _log(team, project, "photo", station.station_code,
         f"Photo submitted at Station {station.station_code}", 0, 0, db)

    await wa.send_text(
        team.group_number,
        f"📸 *Photo received!* ✅\n"
        f"Now send your answer for Station {station.station_code}."
    )


# ─── Status ───────────────────────────────────────────────────────────────────

async def _handle_status(team: Team, project: Project, db: Session):
    station = get_next_station(team, db)
    score = _calc_score(team, project)

    msg = (
        f"📊 *{team.name} — Status*\n\n"
        f"Stations done: {team.stages_done} / {len(project.stations)}\n"
        f"Wrong answers: {team.wrong_count}\n"
        f"Hints used: {team.hints_used}\n"
        f"Penalty time: +{team.penalty_mins} min\n"
        f"Current score: {score} pts\n\n"
        f"Current station: "
        f"*{station.station_code if station else 'All done!'}*"
    )
    await wa.send_text(team.group_number, msg)


# ─── Finish ───────────────────────────────────────────────────────────────────

async def _finish_team(team: Team, project: Project, db: Session):
    team.status = "finished"
    team.end_time = datetime.now(timezone.utc)
    db.commit()

    score = _calc_score(team, project)
    duration = ""
    if team.start_time and team.end_time:
        delta = team.end_time - team.start_time
        mins = int(delta.total_seconds() // 60)
        secs = int(delta.total_seconds() % 60)
        duration = f"{mins}m {secs}s"

    _log(team, project, "finish", "",
         f"{team.name} finished the race", 0, 0, db)

    custom = (project.finish_message or "").strip()
    closing = f"\n\n{custom}" if custom else "\n\nWell done! Wait for the final leaderboard."
    await wa.send_text(
        team.group_number,
        f"🏁 *{team.name} — Race Complete!*\n\n"
        f"Stations: {team.stages_done} / {len(project.stations)}\n"
        f"Wrong answers: {team.wrong_count}\n"
        f"Hints used: {team.hints_used}\n"
        f"Penalty: +{team.penalty_mins} min\n"
        f"Total time: {duration}\n\n"
        f"*Final score: {score} pts* 🎉"
        f"{closing}"
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _calc_score(team: Team, project: Project) -> int:
    score = team.stages_done * project.scoring_stage_pts
    score -= team.wrong_count * project.scoring_wrong_pts
    score -= team.hints_used * project.scoring_hint_pts
    for prog in team.progress:
        if prog.answer_revealed:
            score -= prog.station.answer_cost
    return max(0, score)


def _log(team, project, event_type, station_code,
         message, pts, time_added, db):
    log = EventLog(
        team_id=team.id,
        project_id=project.id,
        event_type=event_type,
        station_code=station_code,
        message=message,
        pts_change=pts,
        time_added=time_added,
    )
    db.add(log)
    db.commit()
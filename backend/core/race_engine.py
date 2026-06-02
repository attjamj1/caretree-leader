from datetime import datetime, timezone
from sqlalchemy.orm import Session

from core.answer_checker import check_answer
from core.station_router import (
    get_next_station,
    get_or_create_progress,
    get_team_by_number,
    get_active_project,
)
from core import whatsapp as wa
from models.models import EventLog, Team, Project


# ─── Entry point ─────────────────────────────────────────────────────────────

async def handle_incoming(
    from_number: str,
    body: str,
    media_url: str | None,
    db: Session,
):
    """
    Called by the webhook for every incoming WhatsApp message.
    Resolves team → dispatches to correct handler.
    """
    project = get_active_project(db)
    if not project:
        return

    team = get_team_by_number(from_number, project.id, db)
    if not team:
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


# ─── Answer ───────────────────────────────────────────────────────────────────

async def _handle_answer(team: Team, project: Project, body: str, db: Session):
    station = get_next_station(team, db)
    if not station:
        await _finish_team(team, project, db)
        return

    prog = get_or_create_progress(team, station, db)

    if station.photo_required and not prog.photo_submitted:
        await wa.send_text(
            team.group_number,
            "📸 Please send your team photo at this station before answering!"
        )
        return

    if check_answer(body, station.answer):
        # ✅ Correct
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
    if not station or not station.hint_text:
        await wa.send_text(
            team.group_number,
            "No hint available for this station."
        )
        return

    prog = get_or_create_progress(team, station, db)
    prog.hints_used += 1
    db.commit()

    _log(team, project, "hint", station.station_code,
         f"Hint used at Station {station.station_code}",
         -station.hint_cost, 0, db)

    await wa.send_text(
        team.group_number,
        f"💡 *Hint for Station {station.station_code}*\n"
        f"(-{station.hint_cost} pts deducted)\n\n"
        f"{station.hint_text}"
    )


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
    if not station or not station.photo_required:
        await wa.send_text(
            team.group_number,
            "📸 Photo received! You can now submit your answer."
        )
        return

    prog = get_or_create_progress(team, station, db)
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

    await wa.send_text(
        team.group_number,
        f"🏁 *{team.name} — Race Complete!*\n\n"
        f"Stations: {team.stages_done} / {len(project.stations)}\n"
        f"Wrong answers: {team.wrong_count}\n"
        f"Hints used: {team.hints_used}\n"
        f"Penalty: +{team.penalty_mins} min\n"
        f"Total time: {duration}\n\n"
        f"*Final score: {score} pts* 🎉\n\n"
        f"Well done! Wait for the final leaderboard."
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
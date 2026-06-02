from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.database import get_db
from models.models import Project

router = APIRouter()


@router.get("/live")
def get_live(db: Session = Depends(get_db)):
    """
    Public endpoint — no auth needed.
    Returns only safe, non-sensitive data for the public leaderboard.
    """
    project = db.query(Project).filter_by(status="live").first()
    if not project:
        done = (
            db.query(Project)
            .filter_by(status="done")
            .order_by(Project.created_at.desc())
            .first()
        )
        if done:
            project = done
        else:
            return {"status": "no_race", "teams": []}

    sorted_teams = sorted(
        project.teams,
        key=lambda t: (-t.stages_done, t.penalty_mins)
    )

    return {
        "race_name": project.name,
        "org": project.org,
        "status": project.status,
        "total_stations": len(project.stations),
        "teams": [
            {
                "name": t.name,
                "leader": t.leader_name,
                "rank": i + 1,
                "stages_done": t.stages_done,
                "total_stations": len(project.stations),
                "wrong_count": t.wrong_count,
                "hints_used": t.hints_used,
                "penalty_mins": t.penalty_mins,
                "status": t.status,
                "route": t.route,
                "current_station": _current_station(t),
            }
            for i, t in enumerate(sorted_teams)
        ],
    }


def _current_station(team):
    completed = {
        p.station.station_code
        for p in team.progress
        if p.completed
    }
    for code in (team.route or []):
        if code not in completed:
            return code
    return None
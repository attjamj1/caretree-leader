from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.database import get_db
from models.models import Project

router = APIRouter()


def _project_data(project):
    sorted_teams = sorted(
        project.teams,
        key=lambda t: (-t.stages_done, t.penalty_mins)
    )
    return {
        "project_id": project.id,
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


@router.get("/live/{project_id}")
def get_live_project(project_id: str, db: Session = Depends(get_db)):
    """Per-project live leaderboard — no auth needed."""
    project = db.query(Project).filter_by(id=project_id).first()
    if not project:
        raise HTTPException(404, "Race not found")
    return _project_data(project)


@router.get("/live")
def get_live(db: Session = Depends(get_db)):
    """Fallback — returns first live project."""
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

    return _project_data(project)


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
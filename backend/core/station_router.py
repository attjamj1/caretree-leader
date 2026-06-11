import random
from models.models import Team, Station, Progress
from sqlalchemy.orm import Session


def get_next_station(team: Team, db: Session) -> Station | None:
    """
    Returns the next incomplete station in this team's route.
    Route is stored as a list of station_codes e.g. ["C","A","E","B"]
    """
    if not team.route:
        return None

    completed_codes = {
        p.station.station_code
        for p in team.progress
        if p.completed
    }

    for code in team.route:
        if code not in completed_codes:
            return (
                db.query(Station)
                .filter_by(project_id=team.project_id, station_code=code)
                .first()
            )

    return None  # all stations done


def get_or_create_progress(team: Team, station: Station, db: Session) -> Progress:
    prog = (
        db.query(Progress)
        .filter_by(team_id=team.id, station_id=station.id)
        .first()
    )
    if not prog:
        prog = Progress(team_id=team.id, station_id=station.id)
        db.add(prog)
        db.commit()
        db.refresh(prog)
    return prog


def assign_routes(project, db: Session):
    """
    Called when race starts — shuffles station order uniquely per team
    so they never crowd the same station simultaneously.
    """
    station_codes = [s.station_code for s in project.stations]

    for i, team in enumerate(project.teams):
        shuffled = station_codes.copy()
        random.shuffle(shuffled)

        # rotate so each team starts at a different station
        if i < len(shuffled):
            shuffled = shuffled[i:] + shuffled[:i]

        team.route = shuffled

    db.commit()
    return True


def get_team_by_number(mobile: str, project_id: str, db: Session) -> Team | None:
    """Find team by their WhatsApp number across a project."""
    cleaned = mobile.replace("whatsapp:", "").strip()
    return (
        db.query(Team)
        .filter(
            Team.project_id == project_id,
            Team.group_number.contains(cleaned)
        )
        .first()
    )


def get_active_project(db: Session):
    """Returns the currently live project, if any."""
    from models.models import Project
    return db.query(Project).filter_by(status="live").first()
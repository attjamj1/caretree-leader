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
    Stations marked is_final are always appended at the end, in order_index order.
    """
    final_codes  = [s.station_code for s in sorted(project.stations, key=lambda s: s.order_index) if s.is_final]
    normal_codes = [s.station_code for s in project.stations if not s.is_final]

    for i, team in enumerate(project.teams):
        shuffled = normal_codes.copy()
        random.shuffle(shuffled)

        # rotate so each team starts at a different station
        if i < len(shuffled):
            shuffled = shuffled[i:] + shuffled[:i]

        team.route = shuffled + final_codes

    db.commit()
    return True


def get_team_by_number(mobile: str, db: Session) -> Team | None:
    """
    Find a team by their WhatsApp number, scoped to whichever LIVE project
    that team actually belongs to. We don't pre-guess a single global
    "active project" — that breaks if an old/forgotten project elsewhere
    is still flagged status="live" (e.g. left over from earlier testing
    under a different account or never explicitly ended). Instead we go
    straight from the phone number to the matching team + its own live
    project, so stray live projects can never hijack the wrong team's
    messages. If a number somehow matches teams in more than one live
    project, the most recently created project wins.
    """
    from models.models import Project
    cleaned = mobile.replace("whatsapp:", "").strip()
    return (
        db.query(Team)
        .join(Project, Team.project_id == Project.id)
        .filter(
            Team.group_number.contains(cleaned),
            Project.status == "live",
        )
        .order_by(Project.created_at.desc())
        .first()
    )


def get_active_project(db: Session):
    """Returns the currently live project, if any."""
    from models.models import Project
    return db.query(Project).filter_by(status="live").first()
from sqlalchemy import (
    Column, String, Integer, Boolean, Float,
    DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from db.database import Base


def gen_id():
    return str(uuid.uuid4())


# ─── User ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id           = Column(String, primary_key=True, default=gen_id)
    username     = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at   = Column(DateTime, server_default=func.now())


# ─── Project ────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id          = Column(String, primary_key=True, default=gen_id)
    user_id     = Column(String, nullable=True)
    name        = Column(String, nullable=False)
    org         = Column(String, default="")
    event_date  = Column(String, default="")
    status      = Column(String, default="draft")  # draft | live | done
    live_token  = Column(String, nullable=True)    # unique token for /live/<token>
    created_at  = Column(DateTime, server_default=func.now())

    teams    = relationship("Team",    back_populates="project", cascade="all, delete")
    stations = relationship("Station", back_populates="project", cascade="all, delete", order_by="Station.order_index")

    scoring_wrong_pts   = Column(Integer, default=10)
    scoring_wrong_time  = Column(Integer, default=5)
    scoring_hint_pts    = Column(Integer, default=5)
    scoring_answer_pts  = Column(Integer, default=20)
    scoring_stage_pts   = Column(Integer, default=100)
    scoring_tiebreak    = Column(String, default="time")


# ─── Team ───────────────────────────────────────────────────────────────────

class Team(Base):
    __tablename__ = "teams"

    id             = Column(String, primary_key=True, default=gen_id)
    project_id     = Column(String, ForeignKey("projects.id"), nullable=False)
    name           = Column(String, nullable=False)
    leader_name    = Column(String, default="")
    mobile         = Column(String, default="")
    group_number   = Column(String, default="")   # primary WhatsApp number (leader)
    member_numbers = Column(JSON, default=list)   # all member numbers to notify
    route          = Column(JSON, default=list)
    start_time     = Column(DateTime, nullable=True)
    end_time       = Column(DateTime, nullable=True)
    status         = Column(String, default="waiting")

    project    = relationship("Project", back_populates="teams")
    progress   = relationship("Progress", back_populates="team", cascade="all, delete")
    event_logs = relationship("EventLog", back_populates="team", cascade="all, delete")

    @property
    def stages_done(self):
        return sum(1 for p in self.progress if p.completed)

    @property
    def wrong_count(self):
        return sum(p.wrong_answers for p in self.progress)

    @property
    def hints_used(self):
        return sum(p.hints_used for p in self.progress)

    @property
    def penalty_mins(self):
        return self.wrong_count * (self.project.scoring_wrong_time if self.project else 5)


# ─── Station ────────────────────────────────────────────────────────────────

class Station(Base):
    __tablename__ = "stations"

    id             = Column(String, primary_key=True, default=gen_id)
    project_id     = Column(String, ForeignKey("projects.id"), nullable=False)
    station_code   = Column(String, default="A")
    name           = Column(String, default="")
    order_index    = Column(Integer, default=0)
    mission_type   = Column(String, default="text")
    clue_text      = Column(Text, default="")
    clue_media_url = Column(String, default="")
    gps_lat        = Column(Float, nullable=True)
    gps_lng        = Column(Float, nullable=True)
    answer         = Column(String, nullable=False)
    hint_text      = Column(Text, default="")
    hint_cost      = Column(Integer, default=5)
    answer_cost    = Column(Integer, default=20)
    photo_required = Column(Boolean, default=False)

    project  = relationship("Project", back_populates="stations")
    progress = relationship("Progress", back_populates="station", cascade="all, delete")


# ─── Progress ────────────────────────────────────────────────────────────────

class Progress(Base):
    __tablename__ = "progress"

    id              = Column(String, primary_key=True, default=gen_id)
    team_id         = Column(String, ForeignKey("teams.id"), nullable=False)
    station_id      = Column(String, ForeignKey("stations.id"), nullable=False)
    completed       = Column(Boolean, default=False)
    completed_at    = Column(DateTime, nullable=True)
    wrong_answers   = Column(Integer, default=0)
    hints_used      = Column(Integer, default=0)
    answer_revealed = Column(Boolean, default=False)
    photo_submitted = Column(Boolean, default=False)
    photo_url       = Column(String, default="")

    team    = relationship("Team",    back_populates="progress")
    station = relationship("Station", back_populates="progress")


# ─── Event Log ───────────────────────────────────────────────────────────────

class EventLog(Base):
    __tablename__ = "event_logs"

    id           = Column(String, primary_key=True, default=gen_id)
    team_id      = Column(String, ForeignKey("teams.id"), nullable=False)
    project_id   = Column(String, nullable=False)
    event_type   = Column(String)
    station_code = Column(String, default="")
    message      = Column(Text, default="")
    pts_change   = Column(Integer, default=0)
    time_added   = Column(Integer, default=0)
    created_at   = Column(DateTime, server_default=func.now())

    team = relationship("Team", back_populates="event_logs")
from sqlalchemy import create_engine, Column, String, Text, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Meeting(Base):
    __tablename__ = "meetings"
    id = Column(String, primary_key=True)          # Attendee bot_id
    meeting_url = Column(String)
    bot_name = Column(String)
    status = Column(String)                         # joining/in_call/ended
    created_at = Column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"
    meeting_id = Column(String, primary_key=True)
    data = Column(JSON)                             # full structured JSON
    created_at = Column(DateTime, default=datetime.utcnow)


class Webhook(Base):
    __tablename__ = "webhooks"
    id = Column(String, primary_key=True)
    url = Column(String)
    event = Column(String)                          # bot.joined / insights.ready / etc
    secret = Column(String)


class SpeakerMap(Base):
    __tablename__ = "speaker_map"
    meeting_id = Column(String, primary_key=True)
    speaker_index = Column(String, primary_key=True)   # "0", "1", "2"
    name = Column(String)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)

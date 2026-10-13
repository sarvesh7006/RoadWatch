import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, String, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    pass
DATA = Path(os.getenv('DATA_DIR', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
MEDIA = DATA / 'media'
MEDIA.mkdir(exist_ok=True)
url = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "roadwatch.db"}')
engine = create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(engine)

class Base(DeclarativeBase):
    pass

class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    updated_at: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    gps_accuracy: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(12), index=True)
    status: Mapped[str] = mapped_column(String(20), default='open', index=True)
    confidence: Mapped[float] = mapped_column(Float)
    count: Mapped[int] = mapped_column(Integer)
    detections: Mapped[str] = mapped_column(Text)
    image: Mapped[str] = mapped_column(String(80))
    notes: Mapped[str] = mapped_column(Text, default='')
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    observations: Mapped[int] = mapped_column(Integer, default=1)


def now():
    return datetime.now(timezone.utc).isoformat()


def serialize(r):
    import json
    return {**{c.name: getattr(r, c.name) for c in Report.__table__.columns}, 'detections': json.loads(r.detections), 'image_url': f'/media/{r.image}'}

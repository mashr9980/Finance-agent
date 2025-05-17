# migration.py
from sqlalchemy import create_engine
from app.config import settings
from app.database import Base

# Import all models to ensure they're registered with SQLAlchemy
from app.models import ap_models, ar_models, gl_models, auth_models, currency_models

engine = create_engine(settings.DATABASE_URL)
Base.metadata.create_all(bind=engine)

print("Migration complete. New tables have been created.")
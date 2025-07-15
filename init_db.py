# run.py or a separate file
from app import db, app

with app.app_context():
    db.create_all()

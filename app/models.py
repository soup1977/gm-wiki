from app import db
from datetime import datetime

class Campaign(db.Model):
    __tablename__ = 'campaigns'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    system = db.Column(db.String(100))         # Free text — "D&D 5e", "ICRPG", whatever
    status = db.Column(db.String(50), default='active')   # active / on hiatus / complete
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Campaign {self.name}>'
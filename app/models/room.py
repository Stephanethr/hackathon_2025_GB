from app.extensions import db

class Room(db.Model):
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    equipment = db.Column(db.JSON, default=list) # e.g. ["projector", "whiteboard"]
    is_active = db.Column(db.Boolean, default=True)

    # Constraint to ensure capacity > 0 logic handled in application or simple check constraint in DB if supported
    # __table_args__ = (db.CheckConstraint('capacity > 0', name='check_capacity_positive'),)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'capacity': self.capacity,
            'equipment': self.equipment,
            'is_active': self.is_active
        }

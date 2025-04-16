from main import db, app, PublicRoom

with app.app_context():
    public_rooms = PublicRoom.query.all()
    for room in public_rooms:
        print(room.id, room.name, room.description, room.owner_id, room.public)

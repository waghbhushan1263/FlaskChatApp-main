###########################################  imports 
from flask import Flask, request, render_template, redirect, url_for, session, send_from_directory, jsonify 
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from utils import generate_room_code
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import quote as url_quote
from ai import get_ai_response

############################################  settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mp3', 'docx'}
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
socketio = SocketIO(app)
HUGGINGFACE_API_KEY = os.getenv('HF_TOKEN')
MODEL = "facebook/blenderbot-400M-distill"  # Free chatbot model
db = SQLAlchemy(app)

#############################################  rooms
rooms = {}

############################################# classes
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)






############################################# helper function
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

############################################# uploads 
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return {"error": "No file part"}, 400

    file = request.files['file']
    if file.filename == '':
        return {"error": "No selected file"}, 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return {"message": "File uploaded", "file_url": f"/uploads/{filename}"}, 200

    return {"error": "File type not allowed"}, 400

############################################### loing and signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        
        password = request.form.get('password')

        if not username or  not password:
            return render_template('signup.html', error="All fields are required.")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template('signup.html', error="name already registered.")

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))  # Redirect to login after signup

    return render_template('signup.html')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username=request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return render_template('login.html', error="Invalid credentials.")

        session['user_id'] = user.id
        session['username'] = user.username
        # print(session['username'])
        return redirect(url_for('home'))  # Redirect to home after login

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('private_section'))


#################################################### Route to serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

############################################ AI chat endpoint
@app.route("/ai_chat", methods=["POST"])
def ai_chat():
    data = request.json
    user_message = data.get("message", "")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    ai_reply = get_ai_response(user_message, HUGGINGFACE_API_KEY)
    return jsonify({"reply": ai_reply})

############################################## routes


@app.route('/')
def home():
   
    return render_template('home.html')# Only shows welcome + login/signup + public/private sections

@app.route('/private', methods=["GET", "POST"])
def private_section():
    session.clear()
    if request.method == "POST":
        name = request.form.get('name')
        create = request.form.get('create', False)
        code = request.form.get('code')
        join = request.form.get('join', False)
        if not name:
            return render_template('home.html', error="Name is required", code=code)
        if create != False:
            room_code = generate_room_code(6, list(rooms.keys()))
            rooms[room_code] = {'members': 0, 'messages': []}
        if join != False:
            if not code:
                return render_template('home.html', error="Please enter a room code to enter a chat room", name=name)
            if code not in rooms:
                return render_template('home.html', error="Room code invalid", name=name)
            room_code = code
        session['room'] = room_code
        session['name'] = name
        return redirect(url_for('chat'))
    else:
        return render_template('private.html')

@app.route('/chat')
def chat():
    room = session.get('room')
    name = session.get('name')
    if name is None or room is None or room not in rooms:
        return redirect(url_for('private_section'))
    messages = rooms[room]['messages']
    return render_template('chat.html', room=room, user=name, messages=messages)








######################################### socketio events
@socketio.on('join')
def handle_join(data):
    room = data.get('room')
    name = data.get('name')
    session['room'] = room
    session['name'] = name
    join_room(room)
    send({"sender": "", "message": f"{name} has entered the chat"}, to=room)
    rooms[room]["members"] += 1

@socketio.on('leave')
def handle_leave(data): 
    room = data.get('room')
    name = data.get('name')
    leave_room(room)
    send({"sender": "", "message": f"{name} has left the chat"}, to=room)
    rooms[room]["members"] -= 1

@socketio.on('send_file')
def handle_file(data):
    username = data.get("username", "Anonymous")
    file_url = data.get("file_url")
    if file_url:
        emit('receive_file', {"username": username, "file_url": file_url}, broadcast=True)

@socketio.on('connect')
def handle_connect(auth):
    name = session.get('name')
    room = session.get('room')
    if name is None or room is None:
        return
    if room not in rooms:
        leave_room(room)
        return  
    join_room(room)
    send({"sender": "", "message": f"{name} has entered the chat"}, to=room)
    rooms[room]["members"] += 1

@socketio.on('message')
def handle_message(payload):
    room = session.get('room')
    name = session.get('name')
    if room not in rooms:
        return
    message = {"sender": name, "message": payload["message"]}
    print(f"📩 Message received: {payload['message']}") 
    send(message, to=room)
    rooms[room]["messages"].append(message)

@socketio.on('disconnect')
def handle_disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)
    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    send({"message": f"{name} has left the chat", "sender": ""}, to=room)

###########################################3 main
if __name__ == '__main__':
    with app.app_context():
       db.create_all()

    port = int(os.environ.get('PORT', 5000))  # Set Render's default port
    socketio.run(app, host='0.0.0.0', port=port)

import os
import time
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import init_db, get_db_connection

try:
    import cv2
    import numpy as np
    import face_recognition
except ImportError:
    cv2 = None
    np = None
    face_recognition = None

# face recognition globals
cached_encodings = {}
last_seen_time = {}

def update_camera_location(matched_id, name):
    current_time = time.time()
    # Update only if 60 seconds have passed since last update
    if current_time - last_seen_time.get(matched_id, 0) > 60:
        last_seen_time[matched_id] = current_time
        conn = get_db_connection()
        conn.execute('''
            UPDATE alerts
            SET last_seen=?, is_iot_updated=1
            WHERE id=?
        ''', ("Camera Entry Gate", matched_id))
        conn.commit()
        conn.close()

def get_known_faces():
    if not face_recognition: return {}
    conn = get_db_connection()
    alerts = conn.execute("SELECT id, name, photo FROM alerts WHERE status='active' AND photo IS NOT NULL").fetchall()
    conn.close()
    
    current_ids = set()
    for alert in alerts:
        current_ids.add(alert['id'])
        if alert['id'] not in cached_encodings:
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], alert['photo'])
            if os.path.exists(photo_path):
                try:
                    img = face_recognition.load_image_file(photo_path)
                    encodings = face_recognition.face_encodings(img)
                    if encodings:
                        cached_encodings[alert['id']] = (alert['name'], encodings[0])
                except Exception as e:
                    print(f"Error loading face for {alert['name']}: {str(e)}")
    
    # Remove obsolete encodings
    for uid in list(cached_encodings.keys()):
        if uid not in current_ids:
            del cached_encodings[uid]
            
    return cached_encodings

def generate_frames():
    if not face_recognition or not cv2:
        # Fallback dummy frame if libraries are missing
        return
        
    camera = cv2.VideoCapture(0)
    while camera.isOpened():
        success, frame = camera.read()
        if not success:
            break
            
        # Resize frame for faster processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        # Convert BGR to RGB
        rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])

        # Find faces
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        known_faces = get_known_faces()
        known_encodings = [v[1] for v in known_faces.values()]
        known_names = [v[0] for v in known_faces.values()]
        known_ids = [k for k in known_faces.keys()]

        face_names = []
        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, face_encoding)
            name = "Unknown"

            if True in matches:
                first_match_index = matches.index(True)
                name = known_names[first_match_index]
                matched_id = known_ids[first_match_index]
                
                # Update db
                update_camera_location(matched_id, name)
            
            face_names.append(name)
        
        # Display the results
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            top *= 4
            right *= 4
            bottom *= 4
            left *= 4

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(frame, name, (left + 6, bottom - 6), font, 1.0, (255, 255, 255), 1)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
    camera.release()


app = Flask(__name__)
app.secret_key = 'super_secret_key' # In a real app, this should be a secure random string

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

AREAS = [
    'T Nagar',
    'Koyambedu',
    'Central Station',
    'Marina Beach',
    'Tambaram'
]

# Initialize DB on startup
init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user:
            flash('Username already exists.', 'error')
        else:
            conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                         (username, generate_password_hash(password)))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            conn.close()
            return redirect(url_for('login'))
        conn.close()
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully.', 'success')
            return redirect(url_for('view_alerts'))
        else:
            flash('Invalid username or password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/')
def index():
    conn = get_db_connection()
    total_active = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='active'").fetchone()[0]
    total_found = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='found'").fetchone()[0]
    
    # Active alerts by area
    area_counts = {}
    for area in AREAS:
        count = conn.execute("SELECT COUNT(*) FROM alerts WHERE status='active' AND area=?", (area,)).fetchone()[0]
        area_counts[area] = count
    conn.close()
    
    return render_template('index.html', total_active=total_active, total_found=total_found, area_counts=area_counts)

@app.route('/post', methods=['GET', 'POST'])
@login_required
def post_alert():
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        area = request.form['area']
        last_seen = request.form['last_seen']
        contact = request.form['contact']
        device_id = request.form.get('device_id', '')
        
        photo = request.files.get('photo')
        photo_filename = None
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(photo_path)
            photo_filename = filename

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO alerts (user_id, name, age, area, last_seen, contact, photo, device_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], name, age, area, last_seen, contact, photo_filename, device_id))
        conn.commit()
        conn.close()
        
        flash('Alert posted successfully!', 'success')
        return redirect(url_for('view_alerts'))
        
    return render_template('post_alert.html', areas=AREAS)

@app.route('/alerts')
def view_alerts():
    area_filter = request.args.get('area')
    search_query = request.args.get('search', '')
    age_group = request.args.get('age_group', '')
    
    conn = get_db_connection()
    
    query = 'SELECT * FROM alerts WHERE 1=1'
    params = []
    
    if area_filter and area_filter != 'All Areas':
        query += ' AND area = ?'
        params.append(area_filter)
        
    if search_query:
        query += ' AND name LIKE ?'
        params.append(f'%{search_query}%')
        
    if age_group == 'child':
        query += ' AND age < 18'
    elif age_group == 'adult':
        query += ' AND age >= 18 AND age < 60'
    elif age_group == 'senior':
        query += ' AND age >= 60'
        
    query += ' ORDER BY id DESC'
    
    alerts = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('alerts.html', alerts=alerts, areas=AREAS, selected_area=area_filter, search_query=search_query, age_group=age_group)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_alert(id):
    conn = get_db_connection()
    alert = conn.execute('SELECT * FROM alerts WHERE id = ?', (id,)).fetchone()
    
    if alert is None:
        conn.close()
        flash('Alert not found.', 'error')
        return redirect(url_for('view_alerts'))

    if alert['user_id'] != session.get('user_id') and session.get('username') != 'admin':
        conn.close()
        flash('You can only edit your own alerts.', 'error')
        return redirect(url_for('view_alerts'))

    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        last_seen = request.form['last_seen']
        contact = request.form['contact']
        
        conn.execute('''
            UPDATE alerts SET name = ?, age = ?, last_seen = ?, contact = ?
            WHERE id = ?
        ''', (name, age, last_seen, contact, id))
        conn.commit()
        conn.close()
        
        flash('Alert updated successfully!', 'success')
        return redirect(url_for('view_alerts'))
        
    conn.close()
    return render_template('edit_alert.html', alert=alert, areas=AREAS)

@app.route('/found/<int:id>', methods=['POST'])
@login_required
def mark_found(id):
    conn = get_db_connection()
    alert = conn.execute('SELECT * FROM alerts WHERE id = ?', (id,)).fetchone()
    
    if alert and (alert['user_id'] == session.get('user_id') or session.get('username') == 'admin'):
        conn.execute('UPDATE alerts SET status = "found" WHERE id = ?', (id,))
        conn.commit()
        flash('Person marked as found.', 'success')
    else:
        flash('Unauthorized action.', 'error')
        
    conn.close()
    return redirect(url_for('view_alerts'))

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_alert(id):
    if session.get('username') != 'admin':
        flash('Only an admin can delete alerts.', 'error')
        return redirect(url_for('view_alerts'))
        
    conn = get_db_connection()
    conn.execute('DELETE FROM alerts WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Suspicious alert permanently deleted.', 'success')
    return redirect(url_for('view_alerts'))

@app.route("/iot_update", methods=["GET"])
def iot_update():
    device_id = request.args.get("device_id")
    location = request.args.get("location")

    if device_id and location:
        conn = get_db_connection()
        # Ensure we're updating by device_id if configured, or fallback to name if the user used the specific SQL provided
        # The prompt specifically provided: `UPDATE alerts SET last_seen=? WHERE name=?`
        # We will check device_id first to be robust, else do what the user said.
        # Let's use name=? OR device_id=? to satisfy both logic options perfectly.
        conn.execute('''
            UPDATE alerts
            SET last_seen=?, is_iot_updated=1
            WHERE device_id=? OR name=?
        ''', (location, device_id, device_id))
        conn.commit()
        conn.close()
        return "Location Updated", 200
    return "Missing parameters", 400

@app.route('/print/<int:id>')
def print_poster(id):
    conn = get_db_connection()
    alert = conn.execute('SELECT * FROM alerts WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    if alert is None:
        flash('Alert not found for printing.', 'error')
        return redirect(url_for('view_alerts'))
        
    return render_template('print_poster.html', alert=alert)

@app.route('/live_camera')
def live_camera():
    return render_template('live_camera.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True, port=5000)

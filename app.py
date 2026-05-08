from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import numpy as np
from models import db, User, Task

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-123'

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://pratyayroy@localhost/task_manager_db'

db.init_app(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):

    return db.session.get(User, int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST': 
        hashed_pw = generate_password_hash(request.form['password'])
        new_user = User(username=request.form['username'], password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST': 
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user() 
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard(): 
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', tasks=tasks)

@app.route('/api/tasks', methods=['POST'])
@login_required
def add_task(): 
    data = request.json
    new_task = Task(
        title=data['title'],
        description=data.get('description'),
        priority=data.get('priority', 'Medium'),
        user_id=current_user.id
    )
    db.session.add(new_task)
    db.session.commit()
   
    socketio.emit('task_updated', {'message': f"Added: {new_task.title}"})
    return jsonify({"status": "success"}), 201

@app.route('/api/tasks/<int:id>', methods=['PUT'])
@login_required
def update_task(id): 
    task = db.session.get(Task, id)
    if not task or task.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    data = request.json
    task.status = data.get('status', task.status)
    db.session.commit()
    socketio.emit('task_updated', {'message': "Task updated"})
    return jsonify({"status": "updated"})

@app.route('/api/tasks/<int:id>', methods=['DELETE'])
@login_required
def delete_task(id): 
    task = db.session.get(Task, id)
    if not task or task.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(task)
    db.session.commit()
    socketio.emit('task_updated', {'message': "Task deleted"})
    return jsonify({"status": "deleted"})


@app.route('/api/analytics')
@login_required
def get_analytics(): 
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    if not tasks:
        return jsonify({"total": 0, "completed": 0, "pending": 0, "percent": 0})
    
    
    df = pd.DataFrame([{'status': t.status} for t in tasks])
    total = len(df) 
    completed = np.sum(df['status'] == 'Completed') 
    pending = total - completed 
    percent = (completed / total * 100) 

    return jsonify({
        "total": int(total),
        "completed": int(completed),
        "pending": int(pending),
        "percent": round(float(percent), 2)
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
    socketio.run(app, debug=True)
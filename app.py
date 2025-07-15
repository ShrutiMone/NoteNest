from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tracker.db'  # for testing purpose
db_path = os.path.join('/mnt/data', 'tracker.db')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

APP_PASSWORD = os.getenv("APP_PASSWORD")
app.secret_key = os.getenv("SECRET_KEY", "dev")  # Add a secure key in .env too

# Models
class Habit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    checks = db.relationship('HabitCheck', backref='habit', cascade='all, delete-orphan')

class HabitCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_index = db.Column(db.Integer)  # 0 to 6 (Mon to Sun)
    checked = db.Column(db.Boolean, default=False)
    habit_id = db.Column(db.Integer, db.ForeignKey('habit.id'))

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    target = db.Column(db.Integer)
    habit_name = db.Column(db.String(100))  # reference by name
    progress = db.Column(db.Integer, default=0)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    content = db.Column(db.Text, default="")
    color = db.Column(db.String(20))
    pos_x = db.Column(db.Integer, default=0)
    pos_y = db.Column(db.Integer, default=0)
    width = db.Column(db.Integer, default=200)
    height = db.Column(db.Integer, default=200)

class LongTermGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(20), nullable=False)  # 'monthly' or 'yearly'
    completed = db.Column(db.Boolean, default=False)
    milestones = db.Column(db.Integer, default=1)  # total milestone points
    progress = db.Column(db.Integer, default=0)    # number of completed points
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        entered_password = request.form['password']
        if entered_password == APP_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('home'))
        else:
            flash('Incorrect password.', 'danger')
    return render_template('login.html', show_navbar=False)

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))

@app.route('/')
def home():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    habits = Habit.query.all()
    habit_data = {
        habit.name: [c.checked for c in sorted(habit.checks, key=lambda x: x.day_index)]
        for habit in habits
    }

    # Just fetch goals as-is from the DB. DO NOT overwrite progress.
    goals = Goal.query.all()

    return render_template(
        'home.html',
        # habits=[h.name for h in habits],
        habits=habits,
        days=days,
        habit_data=habit_data,
        goals=goals
    )

@app.route('/add_habit', methods=['POST'])
def add_habit():
    name = request.form['habit'].strip()
    if name and not Habit.query.filter_by(name=name).first():
        new_habit = Habit(name=name)
        db.session.add(new_habit)
        db.session.commit()
        for i in range(7):
            db.session.add(HabitCheck(day_index=i, habit=new_habit))
        db.session.commit()
    return redirect(url_for('home'))

# @app.route('/delete_habit/<name>')
# def delete_habit(name):
#     habit = Habit.query.filter_by(name=name).first()
#     if habit:
#         db.session.delete(habit)
#         db.session.commit()
#     return redirect(url_for('home'))

@app.route('/delete_habit/<int:id>')
def delete_habit(id):
    habit = Habit.query.get(id)
    if habit:
        db.session.delete(habit)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/toggle_checkbox', methods=['POST'])
def toggle_checkbox():
    data = request.get_json()
    habit = Habit.query.filter_by(name=data['habit']).first()
    if habit:
        check = HabitCheck.query.filter_by(habit_id=habit.id, day_index=data['index']).first()
        if check and check.checked != data['value']:
            check.checked = data['value']
            db.session.commit()

            # Adjust progress
            goals = Goal.query.filter_by(habit_name=habit.name).all()
            for goal in goals:
                if data['value']:  # checking
                    goal.progress += 1
                else:  # unchecking
                    goal.progress = max(goal.progress - 1, 0)
            db.session.commit()
    return jsonify(success=True)


@app.route('/uncheck_all')
def uncheck_all():
    checks = HabitCheck.query.all()
    for check in checks:
        check.checked = False
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/add_goal', methods=['POST'])
def add_goal():
    name = request.form['goal_name']
    habit_name = request.form['goal_habit']
    target = int(request.form['target_count'])
    new_goal = Goal(name=name, habit_name=habit_name, target=target)
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/delete_goal/<name>')
def delete_goal(name):
    goal = Goal.query.filter_by(name=name).first()
    if goal:
        db.session.delete(goal)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/todos')
def todos():
    notes = Note.query.all()
    return render_template('todos.html', notes=notes)

@app.route('/add_note', methods=['POST'])
def add_note():
    title = request.form['title']
    color = request.form['color']
    new_note = Note(title=title, color=color)
    db.session.add(new_note)
    db.session.commit()
    return redirect(url_for('todos'))

@app.route('/update_note/<int:note_id>', methods=['POST'])
def update_note(note_id):
    note = Note.query.get(note_id)
    if note:
        note.content = request.form['content']
        db.session.commit()
    return '', 204

@app.route('/update_note_position/<int:note_id>', methods=['POST'])
def update_note_position(note_id):
    note = Note.query.get(note_id)
    if note:
        data = request.get_json()
        note.pos_x = data['x']
        note.pos_y = data['y']
        note.width = data['width']
        note.height = data['height']
        db.session.commit()
    return jsonify(success=True)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    note = Note.query.get(note_id)
    if note:
        db.session.delete(note)
        db.session.commit()
    return '', 204

@app.route('/longterm')
def longterm():
    goals = LongTermGoal.query.order_by(LongTermGoal.created_at.desc()).all()
    return render_template('longterm.html', goals=goals)

@app.route('/add_longterm', methods=['POST'])
def add_longterm():
    title = request.form['title']
    goal_type = request.form['type']
    description = request.form.get('description', '')
    milestones_input = request.form.get('milestones')

    # ✅ Auto-set to 1 if left blank or invalid
    try:
        milestones = int(milestones_input)
        if milestones < 1:
            milestones = 1
    except (ValueError, TypeError):
        milestones = 1

    new_goal = LongTermGoal(
        title=title,
        type=goal_type,
        description=description,
        milestones=milestones
    )
    db.session.add(new_goal)
    db.session.commit()
    return redirect(url_for('longterm'))


@app.route('/toggle_longterm/<int:goal_id>', methods=['POST'])
def toggle_longterm(goal_id):
    goal = LongTermGoal.query.get(goal_id)
    if goal:
        goal.completed = not goal.completed
        db.session.commit()
    return '', 204

@app.route('/update_progress/<int:goal_id>', methods=['POST'])
def update_progress(goal_id):
    goal = LongTermGoal.query.get(goal_id)
    if goal:
        action = request.json.get('action')
        if action == 'inc' and goal.progress < goal.milestones:
            goal.progress += 1
        elif action == 'dec' and goal.progress > 0:
            goal.progress -= 1
        db.session.commit()
    return jsonify(success=True)

@app.route('/delete_longterm/<int:goal_id>', methods=['POST'])
def delete_longterm(goal_id):
    goal = LongTermGoal.query.get(goal_id)
    if goal:
        db.session.delete(goal)
        db.session.commit()
    return '', 204


if __name__ == '__main__':
    app.run(debug=True)

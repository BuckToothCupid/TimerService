import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

#Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

#调度器
scheduler = BackgroundScheduler()
scheduler.start()

#数据库
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    timers = db.relationship('Timer', backref='owner', lazy=True)

class Timer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timer_type = db.Column(db.String(20), nullable=False) # 'once' or 'daily'
    target_value = db.Column(db.String(50), nullable=False)
    callback_url = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#定时任务
def execute_callback(app_context, timer_id, callback_url, is_once):
    """到达定时时间后触发的回调函数"""
    with app_context:
        try:
            #模拟通知客户端
            payload = {"timer_id": timer_id, "message": "Timer Triggered!", "timestamp": str(datetime.now())}
            response = requests.post(callback_url, json=payload, timeout=5)
            status = 'Triggered (Success)' if response.status_code == 200 else f'Failed (HTTP {response.status_code})'
        except Exception as e:
            status = f'Failed ({str(e)})'
        
        #更新数据库状态
        timer = Timer.query.get(timer_id)
        if timer:
            timer.status = status
            db.session.commit()

#Web页面路由
@app.route('/')
@login_required
def dashboard():
    timers = Timer.query.filter_by(user_id=current_user.id).order_by(Timer.created_at.desc()).all()
    return render_template('dashboard.html', timers=timers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if action == 'register':
            if User.query.filter_by(username=username).first():
                flash('用户名已存在')
                return redirect(url_for('login'))
            new_user = User(username=username, password_hash=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('注册成功，请登录')
            return redirect(url_for('login'))
            
        elif action == 'login':
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(url_for('dashboard'))
            flash('用户名或密码错误')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

#RESTful API 路由
@app.route('/api/timers', methods=['POST'])
@login_required
def create_timer():
    data = request.json
    timer_type = data.get('type')
    target_value = data.get('value')
    callback_url = data.get('callback_url')

    if not all([timer_type, target_value, callback_url]):
        return jsonify({'error': 'Missing parameters'}), 400

    #验证
    if timer_type == 'once':
        try:
            delay_seconds = int(target_value)
            if not (1 <= delay_seconds <= 86400):
                return jsonify({'error': '一次性定时器时长必须在 1秒 到 24小时 之间'}), 400
        except ValueError:
            return jsonify({'error': '一次性定时器的值必须是整数秒'}), 400
    elif timer_type == 'daily':
        try:
            time_obj = datetime.strptime(target_value, '%H:%M')
        except ValueError:
            return jsonify({'error': '周期性定时器的时间格式必须为 HH:MM'}), 400
    else:
        return jsonify({'error': '不支持的定时器类型'}), 400

    #存入数据库
    new_timer = Timer(user_id=current_user.id, timer_type=timer_type, 
                      target_value=str(target_value), callback_url=callback_url)
    db.session.add(new_timer)
    db.session.commit()

    #注册到调度器
    app_context = app.app_context()
    if timer_type == 'once':
        run_date = datetime.now() + timedelta(seconds=int(target_value))
        scheduler.add_job(func=execute_callback, trigger='date', run_date=run_date,
                          args=[app_context, new_timer.id, callback_url, True])
    elif timer_type == 'daily':
        hour, minute = target_value.split(':')
        scheduler.add_job(func=execute_callback, trigger='cron', hour=int(hour), minute=int(minute),
                          args=[app_context, new_timer.id, callback_url, False])

    return jsonify({'message': '定时器创建成功', 'timer_id': new_timer.id}), 201

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, threaded=True, use_reloader=False)
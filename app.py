# app.py - 修正版（DBリセット時のセッションエラー対策済み）

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
import string

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'social-guillotine-secret-key-12345')

app.config['SESSION_COOKIE_NAME'] = 'social_guillotine_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social_guillotine.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key and api_key != "test_key_here":
        genai.configure(api_key=api_key)
except Exception as e:
    print(f"API キー設定エラー: {e}")


# --- データベースモデル ---
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(100))
    bio = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    stats = db.relationship('UserStats', uselist=False, back_populates='user')
    tasks = db.relationship('Task', back_populates='user')
    badges = db.relationship('Badge', back_populates='user')
    group_memberships = db.relationship('GroupMember', back_populates='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserStats(db.Model):
    __tablename__ = 'user_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    total_tasks = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    punished_tasks = db.Column(db.Integer, default=0)
    current_streak = db.Column(db.Integer, default=0)
    max_streak = db.Column(db.Integer, default=0)
    laziness_score = db.Column(db.Float, default=0.0)
    last_activity = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', back_populates='stats')
    
    def calculate_laziness_score(self):
        if self.total_tasks == 0:
            return 0.0
        laziness = (self.punished_tasks / self.total_tasks) * 100
        return min(laziness, 100.0)
    
    def to_dict(self):
        return {
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'punished_tasks': self.punished_tasks,
            'laziness_score': round(self.laziness_score, 1),
            'current_streak': self.current_streak,
            'max_streak': self.max_streak
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.DateTime)
    penalty_text = db.Column(db.String(500))
    is_punished = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime)
    
    user = db.relationship('User', back_populates='tasks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'penalty_text': self.penalty_text,
            'is_punished': self.is_punished,
            'is_completed': self.is_completed,
            'created_at': self.created_at.isoformat()
        }


class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    invite_code = db.Column(db.String(10), unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    members = db.relationship('GroupMember', back_populates='group')


class GroupMember(db.Model):
    __tablename__ = 'group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    joined_at = db.Column(db.DateTime, default=datetime.now)
    
    group = db.relationship('Group', back_populates='members')
    user = db.relationship('User', back_populates='group_memberships')


class Badge(db.Model):
    __tablename__ = 'badges'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    badge_type = db.Column(db.String(50), nullable=False)
    badge_name = db.Column(db.String(100), nullable=False)
    badge_icon = db.Column(db.String(50))
    unlocked_at = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', back_populates='badges')


# --- ヘルパー関数 ---

# 【修正済み】ログイン必須デコレータ
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. セッションがない場合
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # 2. セッションはあるがDBにユーザーがいない場合（DBリセット時対策）
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            flash('セッションが無効です。再度ログインしてください。', 'error')
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

def get_user_stats(user_id):
    stats = UserStats.query.filter_by(user_id=user_id).first()
    if not stats:
        stats = UserStats(user_id=user_id)
        db.session.add(stats)
        db.session.commit()
    return stats

def update_user_stats(user_id):
    try:
        stats = get_user_stats(user_id)
        all_tasks = Task.query.filter_by(user_id=user_id).all()
        
        stats.total_tasks = len(all_tasks)
        stats.completed_tasks = len([t for t in all_tasks if t.is_completed])
        stats.punished_tasks = len([t for t in all_tasks if t.is_punished])
        stats.laziness_score = stats.calculate_laziness_score()
        stats.last_activity = datetime.now()
        
        db.session.commit()
        user = User.query.get(user_id)
        check_and_unlock_badges(user, stats)
        return stats
    except Exception as e:
        print(f"統計更新エラー: {e}")
        db.session.rollback()
        return get_user_stats(user_id)

def check_and_unlock_badges(user, stats):
    if not user:
        return
        
    badges_to_unlock = []
    
    if stats.current_streak >= 7:
        if not Badge.query.filter_by(user_id=user.id, badge_type='streak_7').first():
            badges_to_unlock.append(('streak_7', '7日連続達成者', '🔥'))
    
    if stats.completed_tasks >= 10:
        if not Badge.query.filter_by(user_id=user.id, badge_type='completion_10').first():
            badges_to_unlock.append(('completion_10', '10個完了達成者', '✨'))
    
    if stats.total_tasks >= 5 and stats.punished_tasks == 0:
        if not Badge.query.filter_by(user_id=user.id, badge_type='perfect').first():
            badges_to_unlock.append(('perfect', '完璧主義者', '👑'))
    
    for badge_type, badge_name, badge_icon in badges_to_unlock:
        badge = Badge(
            user_id=user.id,
            badge_type=badge_type,
            badge_name=badge_name,
            badge_icon=badge_icon
        )
        db.session.add(badge)
        flash(f"🎖️ バッジ解除: {badge_icon} {badge_name}", 'success')
    
    if badges_to_unlock:
        db.session.commit()

def generate_invite_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Group.query.filter_by(invite_code=code).first():
            return code

def generate_backup_praise_message():
    messages = [
        "素晴らしい！完璧な仕事ぶりですね！😄",
        "やりましたね！この調子で行きましょう！💪",
        "見事です！あなたは思慮とは無縁ですね。✨",
        "お疲れ様でした。早期完了、さすがです！🎉"
    ]
    return random.choice(messages)

def generate_praise_with_ai(task_title):
    try:
        if not os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") == "test_key_here":
            return generate_backup_praise_message()
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"「{task_title}」を実行したことを褒めてください。日本語で、絵文字を交えて、2～3文程度。"
        response = model.generate_content(prompt, timeout=10)
        return response.text.strip() if response.text else generate_backup_praise_message()
    except Exception as e:
        print(f"Google AI APIエラー: {e}")
        return generate_backup_praise_message()

def send_discord_punishment(task_title, penalty_text):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or webhook_url == "https://discordapp.com/api/webhooks/dummy/dummy":
        return False

    data = {
        "username": "Social
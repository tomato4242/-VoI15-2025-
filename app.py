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
app.secret_key = os.getenv('SECRET_KEY', 'social-keeper-secret-key-12345')

app.config['SESSION_COOKIE_NAME'] = 'social_keeper_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social_keeper.db'
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
        prompt = f"「{task_title}」を褒めてください。日本語で、絵文字を交えて、2～3文程度。"
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
        "username": "Social Guillotine 執行人",
        "embeds": [{
            "title": "☠️ 社会的制裁が執行されました",
            "color": 15158332,
            "fields": [
                {"name": "破られた誓い", "value": f"「{task_title}」", "inline": False},
                {"name": "執行された罰", "value": f"**{penalty_text}**", "inline": False}
            ]
        }]
    }

    try:
        response = requests.post(webhook_url, json=data, timeout=10)
        return response.status_code == 204
    except Exception as e:
        print(f"Discord通信エラー: {e}")
        return False

def check_deadlines():
    try:
        with app.app_context():
            now = datetime.now()
            expired_tasks = Task.query.filter(
                Task.deadline < now,
                Task.is_punished == False,
                Task.is_completed == False
            ).all()

            for task in expired_tasks:
                task.is_punished = True
                send_discord_punishment(task.title, task.penalty_text)

            if expired_tasks:
                db.session.commit()
                for task in expired_tasks:
                    stats = UserStats.query.filter_by(user_id=task.user_id).first()
                    if stats:
                        stats.laziness_score = stats.calculate_laziness_score()
                db.session.commit()
    except Exception as e:
        print(f"check_deadlines エラー: {e}")
        db.session.rollback()

def init_db():
    with app.app_context():
        db.create_all()
        print("✅ データベースを初期化しました")


# --- 認証ルート ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash('ログインしました！💀', 'success')
            return redirect(url_for('index'))
        else:
            flash('ユーザー名かパスワードが間違っています。', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        display_name = request.form.get('display_name')
        
        if User.query.filter_by(username=username).first():
            flash('そのユーザー名は既に使用されています。', 'error')
            return redirect(url_for('register'))
        
        new_user = User(username=username, display_name=display_name)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        stats = UserStats(user_id=new_user.id)
        db.session.add(stats)
        db.session.commit()

        session['user_id'] = new_user.id
        flash('アカウント登録完了！地獄へようこそ。', 'success')
        return redirect(url_for('index'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('ログアウトしました。', 'info')
    return redirect(url_for('login'))


# --- メインルート (Login Required) ---

@app.route('/')
@login_required
def index():
    user = get_current_user()
    tasks = Task.query.filter_by(user_id=user.id, is_completed=False).order_by(Task.created_at.desc()).all()
    stats = get_user_stats(user.id)
    update_user_stats(user.id)
    badges = Badge.query.filter_by(user_id=user.id).all()
    groups = [gm.group for gm in GroupMember.query.filter_by(user_id=user.id).all()]
    
    tasks_dict = [t.to_dict() for t in tasks]
    return render_template('index.html', tasks=tasks_dict, stats=stats, badges=badges, user=user, groups=groups)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()
    if request.method == 'POST':
        user.display_name = request.form.get('display_name', '').strip()
        user.bio = request.form.get('bio', '').strip()
        db.session.commit()
        flash('プロフィールを更新しました！', 'success')
        return redirect(url_for('profile'))
    
    stats = get_user_stats(user.id)
    return render_template('profile.html', user=user, stats=stats)

@app.route('/api/tasks', methods=['GET'])
@login_required
def api_tasks():
    user = get_current_user()
    tasks = Task.query.filter_by(user_id=user.id, is_completed=False).order_by(Task.created_at.desc()).all()
    return jsonify([t.to_dict() for t in tasks]), 200

@app.route('/api/stats', methods=['GET'])
@login_required
def api_stats():
    user = get_current_user()
    stats = get_user_stats(user.id)
    return jsonify(stats.to_dict()), 200

@app.route('/api/rankings', methods=['GET'])
@login_required
def api_rankings():
    all_stats = UserStats.query.all()
    rankings = []
    for stat in sorted(all_stats, key=lambda x: x.laziness_score, reverse=True):
        user = User.query.get(stat.user_id)
        if user:
            rankings.append({
                'rank': len(rankings) + 1,
                'username': user.display_name or user.username,
                'laziness_score': stat.laziness_score,
                'completed_tasks': stat.completed_tasks,
                'punished_tasks': stat.punished_tasks
            })
    return jsonify(rankings), 200

@app.route('/api/badges', methods=['GET'])
@login_required
def api_badges():
    user = get_current_user()
    badges = Badge.query.filter_by(user_id=user.id).all()
    return jsonify([{
        'name': b.badge_name,
        'icon': b.badge_icon,
        'unlocked_at': b.unlocked_at.isoformat()
    } for b in badges]), 200

@app.route('/api/groups', methods=['GET'])
@login_required
def api_groups():
    user = get_current_user()
    group_members = GroupMember.query.filter_by(user_id=user.id).all()
    groups = []
    for gm in group_members:
        groups.append({
            'id': gm.group_id,
            'name': gm.group.name,
            'invite_code': gm.group.invite_code,
            'created_at': gm.group.created_at.isoformat()
        })
    return jsonify(groups), 200

@app.route('/api/group-rankings/<int:group_id>', methods=['GET'])
@login_required
def get_group_rankings(group_id):
    group = Group.query.get(group_id)
    if not group:
        return jsonify({'error': 'Group not found'}), 404
    
    members = GroupMember.query.filter_by(group_id=group_id).all()
    rankings = []
    for member in members:
        user = User.query.get(member.user_id)
        stats = UserStats.query.filter_by(user_id=member.user_id).first()
        if user and stats:
            rankings.append({
                'username': user.display_name or user.username,
                'laziness_score': stats.laziness_score,
                'completed_tasks': stats.completed_tasks,
                'punished_tasks': stats.punished_tasks
            })
    
    rankings.sort(key=lambda x: x['laziness_score'], reverse=True)
    for i, ranking in enumerate(rankings):
        ranking['rank'] = i + 1
    
    return jsonify(rankings), 200

@app.route('/check_punishments', methods=['GET'])
@login_required
def check_punishments():
    user = get_current_user()
    recent_cutoff = datetime.now() - timedelta(seconds=15)
    punished = Task.query.filter(
        Task.user_id == user.id,
        Task.is_punished == True,
        Task.created_at > recent_cutoff
    ).all()
    return jsonify([{'id': t.id, 'title': t.title, 'penalty_text': t.penalty_text} for t in punished]), 200

@app.route('/add', methods=['POST'])
@login_required
def add_task():
    user = get_current_user()
    title = request.form.get('task_title', '').strip()
    deadline_str = request.form.get('deadline')
    penalty_text = request.form.get('penalty_text', '').strip()

    if not title:
        flash('タスク名を入力してください', 'error')
        return redirect(url_for('index'))

    deadline_dt = None
    if deadline_str:
        try:
            deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('期限の形式が不正です', 'error')
            return redirect(url_for('index'))

    new_task = Task(
        user_id=user.id,
        title=title,
        deadline=deadline_dt,
        penalty_text=penalty_text
    )
    db.session.add(new_task)
    db.session.commit()
    update_user_stats(user.id)
    
    flash(f'タスク「{title}」を追加しました', 'success')
    return redirect(url_for('index'))

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    
    if not task:
        flash('タスクが見つかりません', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form.get('task_title', '').strip()
        deadline_str = request.form.get('deadline')
        penalty_text = request.form.get('penalty_text', '').strip()
        
        deadline_dt = None
        if deadline_str:
            try:
                deadline_dt = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        task.title = title
        task.deadline = deadline_dt
        task.penalty_text = penalty_text
        db.session.commit()
        update_user_stats(user.id)
        
        flash(f'タスク「{title}」を更新しました', 'success')
        return redirect(url_for('index'))
    
    return render_template('edit_task.html', task=task)

@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    user = get_current_user()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    
    if not task:
        flash('タスクが見つかりません', 'error')
        return redirect(url_for('index'))

    if task.deadline and task.deadline > datetime.now() and not task.is_punished:
        message = generate_praise_with_ai(task.title)
        flash(message, 'success')

    task.is_completed = True
    task.completed_at = datetime.now()
    db.session.commit()
    update_user_stats(user.id)
    
    return redirect(url_for('index'))

@app.route('/group/create', methods=['POST'])
@login_required
def create_group():
    user = get_current_user()
    group_name = request.form.get('group_name', '').strip()
    
    if not group_name:
        flash('グループ名を入力してください', 'error')
        return redirect(url_for('index'))
    
    invite_code = generate_invite_code()
    group = Group(name=group_name, invite_code=invite_code, created_by=user.id)
    db.session.add(group)
    db.session.commit()
    
    member = GroupMember(group_id=group.id, user_id=user.id)
    db.session.add(member)
    db.session.commit()
    
    flash(f'✅ グループ「{group_name}」を作成しました。招待コード: {invite_code}', 'success')
    return redirect(url_for('index'))

@app.route('/group/join', methods=['POST'])
@login_required
def join_group():
    user = get_current_user()
    invite_code = request.form.get('invite_code', '').strip().upper()
    
    group = Group.query.filter_by(invite_code=invite_code).first()
    if not group:
        flash('❌ 招待コードが見つかりません', 'error')
        return redirect(url_for('index'))
    
    if GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first():
        flash('⚠️ このグループには既に参加しています', 'error')
        return redirect(url_for('index'))
    
    member = GroupMember(group_id=group.id, user_id=user.id)
    db.session.add(member)
    db.session.commit()
    
    flash(f'✅ グループ「{group.name}」に参加しました', 'success')
    return redirect(url_for('index'))

@app.route('/group/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    user = get_current_user()
    member = GroupMember.query.filter_by(group_id=group_id, user_id=user.id).first()
    if member:
        db.session.delete(member)
        db.session.commit()
        flash('グループから脱退しました', 'success')
    return redirect(url_for('index'))


scheduler = APScheduler()
scheduler.init_app(app)
scheduler.add_job(id='deadline_check_job', func=check_deadlines, trigger='interval', seconds=10)
scheduler.start()

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 Social Guillotine を起動しています...")
    print("=" * 60)
    print("🌐 http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, use_reloader=False)
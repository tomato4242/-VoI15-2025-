# app.py - セッションベース マルチユーザー対応版

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_apscheduler import APScheduler
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv
import google.generativeai as genai
import requests
import string

# --- 初期設定 ---
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'social-guillotine-secret-key-12345')

# --- セッション設定 ---
app.config['SESSION_COOKIE_NAME'] = 'social_guillotine_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# --- データベース設定 ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social_guillotine.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Google Gemini APIキー設定 ---
try:
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key and api_key != "test_key_here":
        genai.configure(api_key=api_key)
except Exception as e:
    print(f"【APIキー設定エラー】: {e}")


# --- データベースモデル ---
class User(db.Model):
    """ユーザー情報"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    stats = db.relationship('UserStats', uselist=False, back_populates='user')
    tasks = db.relationship('Task', back_populates='user')
    badges = db.relationship('Badge', back_populates='user')
    group_memberships = db.relationship('GroupMember', back_populates='user')


class UserStats(db.Model):
    """ユーザーの統計情報（ゲーミフィケーション用）"""
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
    """タスク情報"""
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
    """グループ情報"""
    __tablename__ = 'groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    invite_code = db.Column(db.String(10), unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    members = db.relationship('GroupMember', back_populates='group')


class GroupMember(db.Model):
    """グループメンバーシップ"""
    __tablename__ = 'group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    joined_at = db.Column(db.DateTime, default=datetime.now)
    
    group = db.relationship('Group', back_populates='members')
    user = db.relationship('User', back_populates='group_memberships')


class Badge(db.Model):
    """バッジ（実績）"""
    __tablename__ = 'badges'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    badge_type = db.Column(db.String(50), nullable=False)
    badge_name = db.Column(db.String(100), nullable=False)
    badge_icon = db.Column(db.String(50))
    unlocked_at = db.Column(db.DateTime, default=datetime.now)
    
    user = db.relationship('User', back_populates='badges')


# --- ✅ セッションベースのマルチユーザー管理 ---
def get_current_user():
    """✅ セッションから現在のユーザーを取得（タブごとに異なるユーザーが作成される）"""
    if 'user_id' not in session:
        # 新しいユーザーを自動作成
        random_num = random.randint(1000, 9999)
        new_user = User(
            username=f'user_{random_num}',
            display_name=f'ユーザー{random_num}'
        )
        db.session.add(new_user)
        db.session.commit()
        session['user_id'] = new_user.id
        print(f"✅ 新規ユーザーを作成しました: {new_user.display_name} (ID: {new_user.id})")
    
    user = User.query.get(session['user_id'])
    if not user:
        # セッションが無効な場合は新規作成
        session.clear()
        return get_current_user()
    
    return user


def get_user_stats():
    """ユーザー統計を取得"""
    user = get_current_user()
    stats = UserStats.query.filter_by(user_id=user.id).first()
    if not stats:
        stats = UserStats(user_id=user.id)
        db.session.add(stats)
        db.session.commit()
    return stats


def update_user_stats():
    """ユーザー統計を更新"""
    try:
        user = get_current_user()
        stats = get_user_stats()
        all_tasks = Task.query.filter_by(user_id=user.id).all()
        
        stats.total_tasks = len(all_tasks)
        stats.completed_tasks = len([t for t in all_tasks if t.is_completed])
        stats.punished_tasks = len([t for t in all_tasks if t.is_punished])
        stats.laziness_score = stats.calculate_laziness_score()
        stats.last_activity = datetime.now()
        
        db.session.commit()
        check_and_unlock_badges(user, stats)
        return stats
    except Exception as e:
        print(f"【統計更新エラー】: {e}")
        db.session.rollback()
        return get_user_stats()


def check_and_unlock_badges(user, stats):
    """バッジ解除条件をチェック"""
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
    """招待コードを生成"""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Group.query.filter_by(invite_code=code).first():
            return code


def generate_backup_praise_message():
    messages = [
        "素晴らしい！完璧な仕事ぶりですね！😄",
        "やりましたね！この調子でいきましょう！💪",
        "見事です！あなたは怠惰とは無縁ですね。✨",
        "お疲れ様でした。早期完了、さすがです！🎉",
        "完璧です！あなたは本当に素晴らしい！👏"
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
        print(f"【Google AI APIエラー】: {e}")
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
        print(f"【Discord通信エラー】: {e}")
        return False


def check_deadlines():
    """期限超過を検出"""
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
        print(f"【check_deadlines エラー】: {e}")
        db.session.rollback()


def init_db():
    """データベース初期化"""
    with app.app_context():
        db.create_all()
        print("✅ データベースを初期化しました")


# --- ルーティング ---
@app.route('/')
def index():
    try:
        user = get_current_user()
        tasks = Task.query.filter_by(user_id=user.id).order_by(Task.created_at.desc()).all()
        stats = get_user_stats()
        update_user_stats()
        badges = Badge.query.filter_by(user_id=user.id).all()
        
        tasks_dict = [t.to_dict() for t in tasks]
        return render_template('index.html', tasks=tasks_dict, stats=stats, badges=badges, user=user)
    except Exception as e:
        print(f"【index エラー】: {e}")
        return render_template('index.html', tasks=[], stats=get_user_stats(), badges=[], user=get_current_user())


@app.route('/api/tasks', methods=['GET'])
def api_tasks():
    try:
        user = get_current_user()
        tasks = Task.query.filter_by(user_id=user.id).order_by(Task.created_at.desc()).all()
        return jsonify([t.to_dict() for t in tasks]), 200
    except Exception as e:
        print(f"【api_tasks エラー】: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        stats = get_user_stats()
        return jsonify(stats.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/rankings', methods=['GET'])
def api_rankings():
    """全体ランキングを取得"""
    try:
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
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/badges', methods=['GET'])
def api_badges():
    try:
        user = get_current_user()
        badges = Badge.query.filter_by(user_id=user.id).all()
        return jsonify([{
            'name': b.badge_name,
            'icon': b.badge_icon,
            'unlocked_at': b.unlocked_at.isoformat()
        } for b in badges]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/check_punishments', methods=['GET'])
def check_punishments():
    try:
        user = get_current_user()
        recent_cutoff = datetime.now() - timedelta(seconds=15)
        punished = Task.query.filter(
            Task.user_id == user.id,
            Task.is_punished == True,
            Task.created_at > recent_cutoff
        ).all()
        return jsonify([{'id': t.id, 'title': t.title, 'penalty_text': t.penalty_text} for t in punished]), 200
    except Exception as e:
        return jsonify([]), 200


@app.route('/health', methods=['GET'])
def health_check():
    try:
        Task.query.limit(1).all()
        return jsonify({'status': 'ok', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'error'}), 500


@app.route('/add', methods=['POST'])
def add_task():
    try:
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
                if deadline_dt < datetime.now():
                    flash('期限は現在時刻より後に設定してください', 'error')
                    return redirect(url_for('index'))
            except ValueError:
                flash('期限の形式が不正です', 'error')
                return redirect(url_for('index'))

        if not penalty_text:
            flash('罰則内容を入力してください', 'error')
            return redirect(url_for('index'))

        new_task = Task(
            user_id=user.id,
            title=title,
            deadline=deadline_dt,
            penalty_text=penalty_text
        )
        db.session.add(new_task)
        db.session.commit()
        update_user_stats()
        
        flash(f'タスク「{title}」を追加しました', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"【add_task エラー】: {e}")
        flash(f'エラー: {str(e)[:100]}', 'error')
        return redirect(url_for('index'))


@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    try:
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
        db.session.delete(task)
        db.session.commit()
        update_user_stats()
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"【delete_task エラー】: {e}")
        flash(f'エラー: {str(e)[:100]}', 'error')
        return redirect(url_for('index'))


@app.route('/group/create', methods=['POST'])
def create_group():
    """グループ作成"""
    try:
        user = get_current_user()
        group_name = request.form.get('group_name', '').strip()
        
        if not group_name:
            flash('グループ名を入力してください', 'error')
            return redirect(url_for('index'))
        
        invite_code = generate_invite_code()
        group = Group(
            name=group_name,
            invite_code=invite_code,
            created_by=user.id
        )
        db.session.add(group)
        db.session.commit()
        
        member = GroupMember(group_id=group.id, user_id=user.id)
        db.session.add(member)
        db.session.commit()
        
        flash(f'✅ グループ「{group_name}」を作成しました。招待コード: {invite_code}', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"【create_group エラー】: {e}")
        flash(f'エラー: {str(e)[:100]}', 'error')
        return redirect(url_for('index'))


@app.route('/group/join', methods=['POST'])
def join_group():
    """グループに参加"""
    try:
        user = get_current_user()
        invite_code = request.form.get('invite_code', '').strip().upper()
        
        group = Group.query.filter_by(invite_code=invite_code).first()
        if not group:
            flash('❌ 招待コードが見つかりません', 'error')
            return redirect(url_for('index'))
        
        if GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first():
            flash('⚠️ このグループにはすでに参加しています', 'error')
            return redirect(url_for('index'))
        
        member = GroupMember(group_id=group.id, user_id=user.id)
        db.session.add(member)
        db.session.commit()
        
        flash(f'✅ グループ「{group.name}」に参加しました', 'success')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"【join_group エラー】: {e}")
        flash(f'エラー: {str(e)[:100]}', 'error')
        return redirect(url_for('index'))


@app.route('/api/group-rankings/<int:group_id>', methods=['GET'])
def get_group_rankings(group_id):
    """グループ内のランキングを取得"""
    try:
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
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- スケジューラー設定 ---
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.add_job(
    id='deadline_check_job',
    func=check_deadlines,
    trigger='interval',
    seconds=10,
    max_instances=1
)
scheduler.start()


# --- エラーハンドラ ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


# --- アプリケーション起動 ---
if __name__ == '__main__':
    init_db()
    print("=" * 60)
    print("🚀 Social Guillotine を起動しています...")
    print("=" * 60)
    print("🌐 http://localhost:5000")
    print("複数タブを開くと別のユーザーが自動作成されます")
    print("=" * 60)
    app.run(debug=True, use_reloader=False)
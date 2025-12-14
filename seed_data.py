from app import app, db, User, Task, UserStats, Group, GroupMember, Badge
from datetime import datetime, timedelta
import sys

def seed_database():
    """データベースにテストデータを投入"""
    with app.app_context():
        # 確認プロンプト
        print("=" * 60)
        print("⚠️  警告: 既存のデータがすべて削除されます")
        print("=" * 60)
        
        # コマンドライン引数で -y が指定されていない場合は確認
        if '-y' not in sys.argv:
            response = input("続行しますか？ (y/N): ")
            if response.lower() != 'y':
                print("❌ キャンセルしました")
                return
        
        print("\n🗑️  既存データを削除中...")
        db.drop_all()
        db.create_all()
        print("✅ データベースを初期化しました\n")
        
        print("🌱 テストデータを投入中...")
        
        # ========================================
        # 1. ユーザー作成
        # ========================================
        print("👤 ユーザーを作成中...")
        users_data = [
            {
                "username": "lazy_student",
                "display_name": "怠惰な太郎",
                "bio": "一限には絶対起きられない大学3年生。毎日「明日こそは」と誓うが守れたことがない。"
            },
            {
                "username": "diligent_student",
                "display_name": "真面目な花子",
                "bio": "完璧主義者の大学2年生。タスクは必ず期限内に完了するが、時々やりすぎて疲れる。"
            },
            {
                "username": "procrastinator",
                "display_name": "先延ばし次郎",
                "bio": "「後でやる」が口癖の大学4年生。卒論がやばい。"
            },
            {
                "username": "demo_user",
                "display_name": "デモユーザー",
                "bio": "審査員用のデモアカウントです。自由に使ってください！"
            }
        ]
        
        users = []
        for user_data in users_data:
            user = User(
                username=user_data["username"],
                display_name=user_data["display_name"],
                bio=user_data["bio"]
            )
            user.set_password("password123")
            db.session.add(user)
            users.append(user)
        
        db.session.commit()
        print(f"  ✅ {len(users)}人のユーザーを作成しました")
        
        # ========================================
        # 2. ユーザー統計
        # ========================================
        print("📊 統計データを作成中...")
        stats_data = [
            {"user_id": users[0].id, "total_tasks": 15, "completed_tasks": 8, "punished_tasks": 5, "current_streak": 0, "max_streak": 3, "laziness_score": 33.3},
            {"user_id": users[1].id, "total_tasks": 20, "completed_tasks": 20, "punished_tasks": 0, "current_streak": 12, "max_streak": 12, "laziness_score": 0.0},
            {"user_id": users[2].id, "total_tasks": 10, "completed_tasks": 3, "punished_tasks": 6, "current_streak": 0, "max_streak": 1, "laziness_score": 60.0},
            {"user_id": users[3].id, "total_tasks": 5, "completed_tasks": 3, "punished_tasks": 1, "current_streak": 2, "max_streak": 3, "laziness_score": 20.0}
        ]
        
        for stat_data in stats_data:
            stats = UserStats(**stat_data)
            stats.last_activity = datetime.now()
            db.session.add(stats)
        
        db.session.commit()
        print(f"  ✅ {len(stats_data)}件の統計を作成しました")
        
        # ========================================
        # 3. タスク作成
        # ========================================
        print("📋 タスクを作成中...")
        
        # 怠惰な太郎のタスク（未完了）
        tasks = [
            # 期限が近いタスク（緊迫感）
            Task(
                user_id=users[0].id,
                title="明日の1限に出席する",
                deadline=datetime.now() + timedelta(hours=8),
                penalty_text="今日も一限に起きられませんでした。山田にラーメン奢ります。明日こそは起きます（多分）。",
                is_completed=False,
                is_punished=False
            ),
            Task(
                user_id=users[0].id,
                title="情報工学のレポート提出",
                deadline=datetime.now() + timedelta(hours=24),
                penalty_text="レポート間に合いませんでした。教授に土下座します。来週は絶対出します（たぶん）。",
                is_completed=False,
                is_punished=False
            ),
            Task(
                user_id=users[0].id,
                title="英語の予習（Unit 5）",
                deadline=datetime.now() + timedelta(days=2),
                penalty_text="英語の予習サボりました。次回の授業で当てられたらどうしよう...。隣の席の人、答え教えて下さい。",
                is_completed=False,
                is_punished=False
            ),
            
            # 既に処刑されたタスク（デモ用）
            Task(
                user_id=users[0].id,
                title="数学の課題提出",
                deadline=datetime.now() - timedelta(hours=2),
                penalty_text="数学の課題出すの忘れました。反省してます（次もたぶん忘れる）。",
                is_completed=False,
                is_punished=True,
                created_at=datetime.now() - timedelta(days=1)
            ),
            Task(
                user_id=users[0].id,
                title="ゼミ発表の準備",
                deadline=datetime.now() - timedelta(days=1),
                penalty_text="ゼミ発表ぶっつけ本番でやりました。教授ごめんなさい。単位ください。",
                is_completed=False,
                is_punished=True,
                created_at=datetime.now() - timedelta(days=3)
            ),
            
            # 真面目な花子のタスク（期限に余裕）
            Task(
                user_id=users[1].id,
                title="卒業研究の中間報告準備",
                deadline=datetime.now() + timedelta(days=7),
                penalty_text="中間報告の準備が間に合いませんでした。研究室のメンバーに迷惑をかけてしまいます。",
                is_completed=False,
                is_punished=False
            ),
            Task(
                user_id=users[1].id,
                title="アルバイトのシフト提出",
                deadline=datetime.now() + timedelta(days=5),
                penalty_text="シフト提出忘れました。店長に怒られます。次は忘れません。",
                is_completed=False,
                is_punished=False
            ),
            
            # 先延ばし次郎のタスク（危機的状況）
            Task(
                user_id=users[2].id,
                title="卒論の第3章執筆",
                deadline=datetime.now() + timedelta(hours=48),
                penalty_text="卒論まだ書けてません。教授、提出期限延ばしてください。本当にすみません。",
                is_completed=False,
                is_punished=False
            ),
            Task(
                user_id=users[2].id,
                title="就活のES提出",
                deadline=datetime.now() + timedelta(hours=36),
                penalty_text="ES出し忘れました。この企業諦めます。来年も就活します。",
                is_completed=False,
                is_punished=False
            ),
            
            # デモユーザーのタスク（審査員が触りやすい）
            Task(
                user_id=users[3].id,
                title="このアプリの機能を全部試す",
                deadline=datetime.now() + timedelta(hours=12),
                penalty_text="審査サボりました。優秀賞は他の人にあげます。",
                is_completed=False,
                is_punished=False
            ),
        ]
        
        for task in tasks:
            db.session.add(task)
        
        db.session.commit()
        print(f"  ✅ {len(tasks)}件のタスクを作成しました")
        
        # ========================================
        # 4. グループ作成
        # ========================================
        print("👥 グループを作成中...")
        groups_data = [
            {
                "name": "情報学部 怠惰是正部",
                "invite_code": "INFO24",
                "created_by": users[0].id
            },
            {
                "name": "早起き修行会",
                "invite_code": "WAKE01",
                "created_by": users[1].id
            },
            {
                "name": "卒論地獄サバイバーズ",
                "invite_code": "GRAD99",
                "created_by": users[2].id
            }
        ]
        
        groups = []
        for group_data in groups_data:
            group = Group(**group_data)
            db.session.add(group)
            groups.append(group)
        
        db.session.commit()
        print(f"  ✅ {len(groups)}個のグループを作成しました")
        
        # ========================================
        # 5. グループメンバー追加
        # ========================================
        print("🤝 グループメンバーを追加中...")
        
        # 情報学部 怠惰是正部：全員参加
        for user in users:
            member = GroupMember(group_id=groups[0].id, user_id=user.id)
            db.session.add(member)
        
        # 早起き修行会：真面目な花子とデモユーザー
        for user in [users[1], users[3]]:
            member = GroupMember(group_id=groups[1].id, user_id=user.id)
            db.session.add(member)
        
        # 卒論地獄サバイバーズ：先延ばし次郎と怠惰な太郎
        for user in [users[2], users[0]]:
            member = GroupMember(group_id=groups[2].id, user_id=user.id)
            db.session.add(member)
        
        db.session.commit()
        print(f"  ✅ グループメンバーを追加しました")
        
        # ========================================
        # 6. バッジ作成
        # ========================================
        print("🎖️  バッジを作成中...")
        badges_data = [
            # 真面目な花子のバッジ（全部達成）
            {"user_id": users[1].id, "badge_type": "streak_7", "badge_name": "7日連続達成者", "badge_icon": "🔥"},
            {"user_id": users[1].id, "badge_type": "completion_10", "badge_name": "10個完了達成者", "badge_icon": "✨"},
            {"user_id": users[1].id, "badge_type": "perfect", "badge_name": "完璧主義者", "badge_icon": "👑"},
            
            # 怠惰な太郎のバッジ（少しだけ）
            {"user_id": users[0].id, "badge_type": "completion_10", "badge_name": "10個完了達成者", "badge_icon": "✨"},
            
            # デモユーザーのバッジ
            {"user_id": users[3].id, "badge_type": "streak_7", "badge_name": "7日連続達成者", "badge_icon": "🔥"},
        ]
        
        for badge_data in badges_data:
            badge = Badge(**badge_data)
            badge.unlocked_at = datetime.now() - timedelta(days=1)
            db.session.add(badge)
        
        db.session.commit()
        print(f"  ✅ {len(badges_data)}個のバッジを作成しました")
        
        # ========================================
        # 完了メッセージ
        # ========================================
        print("\n" + "=" * 60)
        print("✅ テストデータ投入完了！")
        print("=" * 60)
        print("\n📝 ログイン情報（審査員向け）:")
        print("-" * 60)
        print("【推奨】デモユーザー")
        print("  ユーザー名: demo_user")
        print("  パスワード: password123")
        print("  特徴: 審査員が自由に使えるアカウント")
        print()
        print("【キャラ1】怠惰な太郎（処刑経験あり）")
        print("  ユーザー名: lazy_student")
        print("  パスワード: password123")
        print("  特徴: 怠惰度33.3%、処刑されたタスクあり")
        print()
        print("【キャラ2】真面目な花子（完璧主義）")
        print("  ユーザー名: diligent_student")
        print("  パスワード: password123")
        print("  特徴: 怠惰度0%、バッジ全獲得、12日連続")
        print()
        print("【キャラ3】先延ばし次郎（危機的状況）")
        print("  ユーザー名: procrastinator")
        print("  パスワード: password123")
        print("  特徴: 怠惰度60%、卒論がやばい")
        print("-" * 60)
        print("\n🚀 アプリを起動してください:")
        print("  python app.py")
        print()
        print("🌐 ブラウザでアクセス:")
        print("  http://localhost:5000")
        print("=" * 60)

if __name__ == '__main__':
    try:
        seed_database()
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        print("解決方法:")
        print("1. app.pyが正しく配置されているか確認")
        print("2. 必要なパッケージがインストールされているか確認")
        print("3. 既存のDBファイルを削除してから再実行")
        sys.exit(1)
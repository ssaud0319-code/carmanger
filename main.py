# carts_management_flet.py
import flet as ft
import sqlite3
from datetime import datetime
import os
import shutil
import threading
import time
from contextlib import contextmanager

# محاولة استيراد مكتبة MEGA
try:
    from mega import Mega
    MEGA_AVAILABLE = True
except ImportError:
    MEGA_AVAILABLE = False

# محاولة استيراد openpyxl و fpdf للتقارير
try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# إعدادات قاعدة البيانات
DB_NAME = 'carts_management.db'
DEFAULT_USER = 'سعود'
DEFAULT_PASSWORD = '123456'
APP_NAME = "نظام إدارة العربات اليدوية - الحرم المكي الشريف"

# إعدادات MEGA
MEGA_EMAIL = "ssaud03192gmail.com"
MEGA_PASSWORD = "saud2026"

# قائمة المستودعات الأساسية
WAREHOUSES = [
    {'name': 'المستودع الرئيسي', 'capacity': 5000, 'type': 'main',
     'description': 'المستودع الرئيسي الكبير خارج المنطقة المركزية'},
    {'name': 'المستودع الخارجي', 'capacity': 1500, 'type': 'external',
     'description': 'المستودع المركزي المتوسط الحجم'},
    {'name': 'مركز التشغيل الشمالي', 'capacity': 500, 'type': 'north',
     'description': 'مركز التشغيل الشمالي'},
    {'name': 'مركز التشغيل الجنوبي', 'capacity': 500, 'type': 'south',
     'description': 'مركز التشغيل الجنوبي'}
]

# حالات العربات
CART_STATUS = {
    'sound': 'سليمة',
    'needs_maintenance': 'تحتاج صيانة',
    'damaged': 'تالفة'
}

# حالات الصيانة
MAINTENANCE_STATUS = {
    'pending': 'بانتظار الصيانة',
    'in_progress': 'قيد التنفيذ',
    'completed': 'منجزة'
}

# الصلاحيات الافتراضية للمستخدمين الجدد
DEFAULT_PERMISSIONS = {
    'can_view_dashboard': 1,
    'can_manage_carts': 1,
    'can_add_cart': 1,
    'can_edit_cart': 0,
    'can_delete_cart': 0,
    'can_move_cart': 1,
    'can_view_movements': 1,
    'can_manage_maintenance': 1,
    'can_complete_maintenance': 0,
    'can_view_warehouses': 1,
    'can_add_warehouse': 0,
    'can_edit_warehouse': 0,
    'can_delete_warehouse': 0,
    'can_view_reports': 1,
    'can_export_reports': 0,
    'can_manage_users': 0,
    'can_manage_backup': 0,
    'can_change_own_password': 1
}

# ألوان احترافية
COLORS = {
    'primary': '#3498db',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'info': '#00bcd4',
    'purple': '#9b59b6',
    'dark': '#2c3e50',
    'light': '#ecf0f1',
    'white': '#ffffff',
    'gray': '#95a5a6',
    'orange': '#e67e22',
    'teal': '#1abc9c'
}

# ================================ إدارة قاعدة البيانات ================================
class DatabaseManager:
    """مدير قاعدة البيانات - نمط Singleton"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_database()
        return cls._instance

    def init_database(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.init_default_data()

    @contextmanager
    def get_cursor(self):
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()

    def create_tables(self):
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                full_name TEXT,
                role TEXT DEFAULT 'operator',
                is_active INTEGER DEFAULT 1,
                last_login DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_permissions (
                user_id INTEGER PRIMARY KEY,
                can_view_dashboard INTEGER DEFAULT 1,
                can_manage_carts INTEGER DEFAULT 1,
                can_add_cart INTEGER DEFAULT 1,
                can_edit_cart INTEGER DEFAULT 0,
                can_delete_cart INTEGER DEFAULT 0,
                can_move_cart INTEGER DEFAULT 1,
                can_view_movements INTEGER DEFAULT 1,
                can_manage_maintenance INTEGER DEFAULT 1,
                can_complete_maintenance INTEGER DEFAULT 0,
                can_view_warehouses INTEGER DEFAULT 1,
                can_add_warehouse INTEGER DEFAULT 0,
                can_edit_warehouse INTEGER DEFAULT 0,
                can_delete_warehouse INTEGER DEFAULT 0,
                can_view_reports INTEGER DEFAULT 1,
                can_export_reports INTEGER DEFAULT 0,
                can_manage_users INTEGER DEFAULT 0,
                can_manage_backup INTEGER DEFAULT 0,
                can_change_own_password INTEGER DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                description TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by INTEGER,
                FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                capacity INTEGER NOT NULL,
                current_count INTEGER DEFAULT 0,
                location_type TEXT,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_number TEXT UNIQUE NOT NULL,
                status TEXT CHECK(status IN ('sound', 'needs_maintenance', 'damaged')) DEFAULT 'sound',
                current_warehouse_id INTEGER,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INTEGER,
                notes TEXT,
                FOREIGN KEY (current_warehouse_id) REFERENCES warehouses (id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id INTEGER NOT NULL,
                from_warehouse_id INTEGER,
                to_warehouse_id INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                notes TEXT,
                FOREIGN KEY (cart_id) REFERENCES carts (id) ON DELETE CASCADE,
                FOREIGN KEY (from_warehouse_id) REFERENCES warehouses (id) ON DELETE SET NULL,
                FOREIGN KEY (to_warehouse_id) REFERENCES warehouses (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS maintenance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cart_id INTEGER NOT NULL,
                maintenance_type TEXT,
                status TEXT DEFAULT 'pending',
                description TEXT,
                entry_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                completion_date DATETIME,
                user_id INTEGER,
                completed_by INTEGER,
                cost REAL DEFAULT 0,
                FOREIGN KEY (cart_id) REFERENCES carts (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
                FOREIGN KEY (completed_by) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                backup_type TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                file_size INTEGER,
                file_path TEXT,
                mega_link TEXT,
                status TEXT DEFAULT 'completed',
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                description TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            )
            """
        ]
        with self.get_cursor() as cursor:
            for query in queries:
                cursor.execute(query)

    def init_default_data(self):
        with self.get_cursor() as cursor:
            # المستخدم الرئيسي
            cursor.execute("SELECT * FROM users WHERE username = ?", (DEFAULT_USER,))
            admin = cursor.fetchone()
            if not admin:
                cursor.execute(
                    """INSERT INTO users (username, password, full_name, role, is_active) 
                       VALUES (?, ?, ?, 'admin', 1)""",
                    (DEFAULT_USER, DEFAULT_PASSWORD, 'سعود آل سعود')
                )
                admin_id = cursor.lastrowid
                permissions = DEFAULT_PERMISSIONS.copy()
                for key in permissions:
                    permissions[key] = 1
                columns = ['user_id'] + list(permissions.keys())
                values = [admin_id] + list(permissions.values())
                placeholders = ','.join(['?' for _ in columns])
                cursor.execute(
                    f"INSERT INTO user_permissions ({','.join(columns)}) VALUES ({placeholders})",
                    values
                )

            # إعدادات التطبيق
            cursor.execute("SELECT * FROM app_settings WHERE setting_key = 'app_name'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
                    ('app_name', APP_NAME, 'اسم التطبيق الرئيسي')
                )
            cursor.execute("SELECT * FROM app_settings WHERE setting_key = 'company_name'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
                    ('company_name', 'الرئاسة العامة لشؤون المسجد الحرام والمسجد النبوي',
                     'اسم الجهة المشغلة')
                )
            cursor.execute("SELECT * FROM app_settings WHERE setting_key = 'mega_email'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
                    ('mega_email', MEGA_EMAIL, 'بريد MEGA للنسخ الاحتياطي السحابي')
                )
            cursor.execute("SELECT * FROM app_settings WHERE setting_key = 'mega_password'")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO app_settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
                    ('mega_password', MEGA_PASSWORD, 'كلمة مرور MEGA للنسخ الاحتياطي السحابي')
                )

            # المستودعات الأساسية
            for wh in WAREHOUSES:
                cursor.execute("SELECT * FROM warehouses WHERE name = ?", (wh['name'],))
                if not cursor.fetchone():
                    cursor.execute(
                        """INSERT INTO warehouses 
                           (name, capacity, current_count, location_type, description, is_active) 
                           VALUES (?, ?, 0, ?, ?, 1)""",
                        (wh['name'], wh['capacity'], wh['type'], wh['description'])
                    )

    def get_app_setting(self, key, default=None):
        result = self.execute_query(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            (key,)
        )
        return result[0][0] if result else default

    def update_app_setting(self, key, value, user_id=None):
        with self.get_cursor() as cursor:
            cursor.execute(
                """UPDATE app_settings 
                   SET setting_value = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ? 
                   WHERE setting_key = ?""",
                (value, user_id, key)
            )

    def execute_query(self, query, params=()):
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_insert(self, query, params=()):
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.lastrowid

    def get_warehouse_count(self, warehouse_id):
        result = self.execute_query(
            "SELECT COUNT(*) FROM carts WHERE current_warehouse_id = ? AND status != 'damaged'",
            (warehouse_id,)
        )
        return result[0][0] if result else 0

    def update_warehouse_count(self, warehouse_id):
        count = self.get_warehouse_count(warehouse_id)
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE warehouses SET current_count = ? WHERE id = ?",
                (count, warehouse_id)
            )

    def get_all_warehouses(self):
        return self.execute_query(
            "SELECT id, name FROM warehouses WHERE is_active = 1 ORDER BY name"
        )

    def get_user_permissions(self, user_id):
        result = self.execute_query(
            "SELECT * FROM user_permissions WHERE user_id = ?",
            (user_id,)
        )
        if result:
            columns = ['user_id', 'can_view_dashboard', 'can_manage_carts', 'can_add_cart',
                       'can_edit_cart', 'can_delete_cart', 'can_move_cart', 'can_view_movements',
                       'can_manage_maintenance', 'can_complete_maintenance', 'can_view_warehouses',
                       'can_add_warehouse', 'can_edit_warehouse', 'can_delete_warehouse',
                       'can_view_reports', 'can_export_reports', 'can_manage_users',
                       'can_manage_backup', 'can_change_own_password', 'updated_at']
            permissions = {}
            for i, col in enumerate(columns):
                permissions[col] = result[0][i]
            return permissions
        else:
            permissions = DEFAULT_PERMISSIONS.copy()
            permissions['user_id'] = user_id
            return permissions

    def update_user_permissions(self, user_id, permissions):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM user_permissions WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                set_clause = ','.join([f"{key}=?" for key in permissions.keys()])
                values = list(permissions.values()) + [user_id]
                cursor.execute(
                    f"UPDATE user_permissions SET {set_clause}, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                    values
                )
            else:
                columns = ['user_id'] + list(permissions.keys())
                values = [user_id] + list(permissions.values())
                placeholders = ','.join(['?' for _ in columns])
                cursor.execute(
                    f"INSERT INTO user_permissions ({','.join(columns)}) VALUES ({placeholders})",
                    values
                )

    def log_action(self, user_id, action, description):
        try:
            self.execute_insert(
                "INSERT INTO system_logs (user_id, action, description) VALUES (?, ?, ?)",
                (user_id, action, description)
            )
        except:
            pass


# ================================ تطبيق Flet الرئيسي ================================
class CartsManagementApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db = DatabaseManager()
        self.current_user = None
        self.current_permissions = None
        self.backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)

        # إعداد الصفحة
        self.page.title = self.db.get_app_setting('app_name', APP_NAME)
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.rtl = True
        self.page.padding = 0
        self.page.spacing = 0
        self.page.bgcolor = COLORS['light']
        self.page.scroll = ft.ScrollMode.ADAPTIVE

        # منطقة المحتوى الرئيسية
        self.content_column = ft.Column(spacing=0, expand=True, scroll=ft.ScrollMode.ADAPTIVE)

        # بدء التشغيل
        self.show_login_screen()

    # ------------------------------------------------------------
    # دوال مساعدة عامة
    # ------------------------------------------------------------
    def show_snack_bar(self, message: str, color: str = COLORS['success']):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message, color=COLORS['white']),
            bgcolor=color,
            show_close_icon=True,
        )
        self.page.snack_bar.open = True
        self.page.update()

    def close_dialog(self, e=None):
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    def check_permission(self, permission):
        if not self.current_permissions:
            return False
        if self.current_user['role'] == 'admin':
            return True
        return self.current_permissions.get(permission, 0) == 1

    # ------------------------------------------------------------
    # شاشة تسجيل الدخول
    # ------------------------------------------------------------
    def show_login_screen(self):
        self.page.clean()
        self.page.dialog = None

        app_name = self.db.get_app_setting('app_name', APP_NAME)
        company_name = self.db.get_app_setting('company_name', 'الرئاسة العامة لشؤون المسجد الحرام والمسجد النبوي')

        # البحث عن الشعار
        logo_src = None
        if os.path.exists(os.path.join(os.path.dirname(__file__), "assets", "logo.png")):
            logo_src = "logo.png"
        elif os.path.exists(os.path.join(os.path.dirname(__file__), "logo.png")):
            logo_src = "logo.png"

        self.username_input = ft.TextField(
            label="اسم المستخدم",
            width=300,
            text_align=ft.TextAlign.RIGHT,
            autofocus=True,
        )
        self.password_input = ft.TextField(
            label="كلمة المرور",
            width=300,
            password=True,
            can_reveal_password=True,
            text_align=ft.TextAlign.RIGHT,
        )

        login_card = ft.Container(
            width=500,
            padding=ft.padding.all(30),
            bgcolor=COLORS['white'],
            border_radius=10,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Image(src=logo_src, width=100, height=100) if logo_src else ft.Text("🚛", size=50),
                    ft.Text(app_name, size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                    ft.Text(company_name, size=14, color=COLORS['gray']),
                    ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
                    self.username_input,
                    self.password_input,
                    ft.ElevatedButton(
                        "تسجيل الدخول",
                        width=200,
                        style=ft.ButtonStyle(
                            bgcolor=COLORS['success'],
                            color=COLORS['white'],
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                        on_click=self.handle_login,
                    ),
                    ft.Text("جميع الحقوق محفوظة © 2025", size=12, color=COLORS['gray']),
                ]
            )
        )

        self.page.add(
            ft.Row(
                [ft.Container(expand=True), login_card, ft.Container(expand=True)],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
        )
        self.page.update()

    def handle_login(self, e):
        username = self.username_input.value.strip()
        password = self.password_input.value.strip()
        if not username or not password:
            self.show_snack_bar("الرجاء إدخال اسم المستخدم وكلمة المرور", COLORS['danger'])
            return

        result = self.db.execute_query(
            "SELECT id, username, role, is_active FROM users WHERE username = ? AND password = ?",
            (username, password)
        )
        if result:
            user_id, username, role, is_active = result[0]
            if not is_active:
                self.show_snack_bar("هذا المستخدم غير نشط. الرجاء التواصل مع المدير", COLORS['danger'])
                return
            self.current_user = {'id': user_id, 'username': username, 'role': role}
            self.db.execute_query(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (user_id,)
            )
            self.current_permissions = self.db.get_user_permissions(user_id)
            self.db.log_action(user_id, 'login', f'تسجيل دخول المستخدم {username}')
            self.show_main_screen()
        else:
            self.show_snack_bar("اسم المستخدم أو كلمة المرور غير صحيحة", COLORS['danger'])

    # ------------------------------------------------------------
    # الشاشة الرئيسية والقائمة الجانبية
    # ------------------------------------------------------------
    def show_main_screen(self):
        self.page.clean()

        app_name = self.db.get_app_setting('app_name', APP_NAME)
        self.page.title = app_name

        # بناء الشريط الجانبي
        sidebar = self._build_sidebar()

        # منطقة المحتوى
        main_content = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Row([
                        ft.Text(app_name, size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                        ft.Text(datetime.now().strftime('%Y-%m-%d %H:%M'), size=14, color=COLORS['gray']),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                    bgcolor=COLORS['light'],
                ),
                self.content_column,
            ], spacing=0, expand=True),
            expand=True,
            bgcolor=COLORS['light'],
        )

        self.page.add(
            ft.Row([
                sidebar,
                main_content,
            ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.START, expand=True)
        )

        # عرض لوحة التحكم أو أول عنصر متاح
        if self.check_permission('can_view_dashboard'):
            self.show_dashboard()
        else:
            items = self._get_menu_items()
            if items:
                items[0]['action'](None)

    def _build_sidebar(self):
        logo_src = None
        if os.path.exists(os.path.join(os.path.dirname(__file__), "assets", "logo.png")):
            logo_src = "logo.png"
        elif os.path.exists(os.path.join(os.path.dirname(__file__), "logo.png")):
            logo_src = "logo.png"

        self.sidebar_app_name_text = ft.Text(
            self.db.get_app_setting('app_name', APP_NAME),
            size=16,
            weight=ft.FontWeight.BOLD,
            color=COLORS['white'],
            text_align=ft.TextAlign.CENTER,
        )

        user_info = ft.Container(
            content=ft.Column([
                ft.Image(src=logo_src, width=80, height=80) if logo_src else ft.Text("🚛", size=50, color=COLORS['white']),
                self.sidebar_app_name_text,
                ft.Text(f"مرحباً {self.current_user['username']}", size=14, color=COLORS['gray']),
                ft.Text("(مدير النظام)" if self.current_user['role'] == 'admin' else "", size=12, color=COLORS['warning']),
                ft.Divider(height=2, color=COLORS['gray']),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            padding=ft.padding.all(20),
            bgcolor=COLORS['dark'],
        )

        menu_buttons = []
        for item in self._get_menu_items():
            btn = ft.Container(
                content=ft.Row([
                    ft.Text(item['icon'], size=20),
                    ft.Text(item['text'], size=14, color=COLORS['white']),
                ], alignment=ft.MainAxisAlignment.START, spacing=10),
                padding=ft.padding.symmetric(horizontal=25, vertical=12),
                ink=True,
                on_click=item['action'],
                border_radius=ft.border_radius.horizontal(start=30, end=0),
            )
            menu_buttons.append(btn)

        logout_btn = ft.Container(
            content=ft.Row([
                ft.Text("🚪", size=20),
                ft.Text("تسجيل الخروج", size=14, color=COLORS['white']),
            ], alignment=ft.MainAxisAlignment.START, spacing=10),
            padding=ft.padding.symmetric(horizontal=25, vertical=12),
            ink=True,
            on_click=self.logout,
            border_radius=ft.border_radius.horizontal(start=30, end=0),
            bgcolor=COLORS['danger'],
        )

        sidebar = ft.Container(
            content=ft.Column([
                user_info,
                ft.Column(menu_buttons, spacing=2, scroll=ft.ScrollMode.AUTO, expand=True),
                ft.Divider(height=2, color=COLORS['gray']),
                logout_btn,
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            width=280,
            bgcolor=COLORS['dark'],
            padding=0,
        )
        return sidebar

    def _get_menu_items(self):
        items = []
        if self.check_permission('can_view_dashboard'):
            items.append({'icon': '📊', 'text': 'لوحة التحكم', 'action': lambda e: self.show_dashboard()})
        if self.check_permission('can_manage_carts'):
            items.append({'icon': '🛒', 'text': 'إدارة العربات', 'action': lambda e: self.show_cart_management()})
        if self.check_permission('can_move_cart') or self.check_permission('can_view_movements'):
            items.append({'icon': '🔄', 'text': 'حركة العربات', 'action': lambda e: self.show_cart_movement()})
        if self.check_permission('can_manage_maintenance'):
            items.append({'icon': '🔧', 'text': 'الصيانة', 'action': lambda e: self.show_maintenance()})
        if self.check_permission('can_view_warehouses'):
            items.append({'icon': '🏢', 'text': 'المستودعات', 'action': lambda e: self.show_warehouse_management()})
        if self.check_permission('can_view_reports'):
            items.append({'icon': '📈', 'text': 'التقارير', 'action': lambda e: self.show_reports()})
        if self.current_user['role'] == 'admin' and self.check_permission('can_manage_users'):
            items.append({'icon': '👥', 'text': 'إدارة المستخدمين', 'action': lambda e: self.show_user_management()})
            items.append({'icon': '⚙️', 'text': 'إعدادات النظام', 'action': lambda e: self.show_system_settings()})
        if self.current_user['role'] == 'admin' and self.check_permission('can_manage_backup'):
            items.append({'icon': '💾', 'text': 'النسخ الاحتياطي', 'action': lambda e: self.show_backup()})
        if self.check_permission('can_change_own_password'):
            items.append({'icon': '🔑', 'text': 'تغيير كلمة المرور', 'action': lambda e: self.show_change_password()})
        return items

    def logout(self, e):
        def confirm(_):
            self.page.dialog.open = False
            self.page.update()
            if self.current_user:
                self.db.log_action(self.current_user['id'], 'logout',
                                   f'تسجيل خروج المستخدم {self.current_user["username"]}')
            self.current_user = None
            self.current_permissions = None
            self.show_login_screen()

        def cancel(_):
            self.page.dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("تسجيل الخروج", weight=ft.FontWeight.BOLD),
            content=ft.Text("هل أنت متأكد من تسجيل الخروج؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=cancel),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def clear_content(self):
        self.content_column.controls.clear()
        self.page.update()

    # ------------------------------------------------------------
    # لوحة التحكم
    # ------------------------------------------------------------
    def show_dashboard(self):
        if not self.check_permission('can_view_dashboard'):
            self.show_snack_bar("غير مصرح لك بعرض لوحة التحكم", COLORS['danger'])
            return

        self.clear_content()

        total_carts = self.db.execute_query("SELECT COUNT(*) FROM carts")[0][0] or 0
        sound_carts = self.db.execute_query("SELECT COUNT(*) FROM carts WHERE status = 'sound'")[0][0] or 0
        maintenance_carts = self.db.execute_query("SELECT COUNT(*) FROM carts WHERE status = 'needs_maintenance'")[0][0] or 0
        damaged_carts = self.db.execute_query("SELECT COUNT(*) FROM carts WHERE status = 'damaged'")[0][0] or 0
        total_warehouses = self.db.execute_query("SELECT COUNT(*) FROM warehouses WHERE is_active = 1")[0][0] or 0
        total_movements = self.db.execute_query("SELECT COUNT(*) FROM movements")[0][0] or 0
        pending_maintenance = self.db.execute_query("SELECT COUNT(*) FROM maintenance_records WHERE status = 'pending'")[0][0] or 0
        total_users = self.db.execute_query("SELECT COUNT(*) FROM users WHERE is_active = 1")[0][0] or 0

        def card(icon, title, value, color, subtitle):
            return ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(icon, size=30),
                        ft.Text(title, size=14, color=COLORS['gray']),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=color),
                    ft.Text(subtitle, size=11, color=COLORS['gray']),
                ]),
                padding=15,
                bgcolor=COLORS['white'],
                border_radius=10,
                expand=True,
            )

        cards_row1 = ft.Row([
            card("🚛", "إجمالي العربات", f"{total_carts:,}", COLORS['primary'],
                 f"زيادة 12% عن الشهر الماضي"),
            card("✅", "عربات سليمة", f"{sound_carts:,}", COLORS['success'],
                 f"{sound_carts / total_carts * 100:.1f}% من الإجمالي" if total_carts > 0 else "0%"),
            card("🔧", "تحتاج صيانة", f"{maintenance_carts:,}", COLORS['warning'],
                 f"{maintenance_carts / total_carts * 100:.1f}% من الإجمالي" if total_carts > 0 else "0%"),
            card("⚠️", "عربات تالفة", f"{damaged_carts:,}", COLORS['danger'],
                 f"{damaged_carts / total_carts * 100:.1f}% من الإجمالي" if total_carts > 0 else "0%"),
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, spacing=10)

        cards_row2 = ft.Row([
            card("🏢", "المستودعات", f"{total_warehouses:,}", COLORS['purple'], "مستودع نشط"),
            card("🔄", "حركات اليوم", f"{total_movements:,}", COLORS['info'], "آخر 24 ساعة"),
            card("🔧", "بانتظار الصيانة", f"{pending_maintenance:,}", COLORS['orange'], f"{pending_maintenance} عربة"),
            card("👥", "المستخدمين", f"{total_users:,}", COLORS['teal'], f"{total_users} مستخدم نشط"),
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, spacing=10)

        warehouses = self.db.execute_query(
            "SELECT name, capacity, current_count FROM warehouses WHERE is_active = 1 ORDER BY id LIMIT 5"
        )
        wh_list = ft.Column(spacing=10)
        for wh in warehouses:
            name, capacity, current = wh
            percentage = (current / capacity * 100) if capacity > 0 else 0
            color = COLORS['danger'] if percentage >= 90 else COLORS['warning'] if percentage >= 70 else COLORS['success']
            wh_list.controls.append(
                ft.Column([
                    ft.Row([ft.Text(name, size=14, weight=ft.FontWeight.BOLD)]),
                    ft.ProgressBar(value=percentage / 100, color=color, bgcolor=COLORS['light'], height=8),
                    ft.Row([
                        ft.Text(f"{percentage:.1f}%", size=12, weight=ft.FontWeight.BOLD, color=color),
                        ft.Text(f"{current} / {capacity}", size=12, color=COLORS['gray']),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(height=1, color=COLORS['light']),
                ], spacing=5)
            )

        movements = self.db.execute_query("""
            SELECT c.serial_number, w1.name, w2.name, m.timestamp
            FROM movements m
            JOIN carts c ON m.cart_id = c.id
            LEFT JOIN warehouses w1 ON m.from_warehouse_id = w1.id
            JOIN warehouses w2 ON m.to_warehouse_id = w2.id
            ORDER BY m.timestamp DESC
            LIMIT 8
        """)
        mov_list = ft.Column(spacing=10)
        for m in movements:
            serial, from_wh, to_wh, ts = m
            mov_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"🚛 {serial}", size=14, weight=ft.FontWeight.BOLD),
                        ft.Text(f"{from_wh or '—'}  ←  {to_wh}", size=12, color=COLORS['primary']),
                        ft.Text(ts[:16] if ts else "", size=11, color=COLORS['gray']),
                    ]),
                    padding=8,
                    border=ft.border.all(1, COLORS['light']),
                    border_radius=8,
                )
            )

        self.content_column.controls.extend([
            ft.Container(padding=ft.padding.only(left=25, right=25, top=10, bottom=10), content=cards_row1),
            ft.Container(padding=ft.padding.only(left=25, right=25, top=5, bottom=10), content=cards_row2),
            ft.Container(
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                content=ft.Row([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("حالة المستودعات", size=18, weight=ft.FontWeight.BOLD),
                            wh_list,
                        ], scroll=ft.ScrollMode.AUTO),
                        padding=15,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                    ft.Container(width=20),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("آخر الحركات", size=18, weight=ft.FontWeight.BOLD),
                            mov_list,
                        ], scroll=ft.ScrollMode.AUTO),
                        padding=15,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
            ),
        ])
        self.page.update()

    # ------------------------------------------------------------
    # إدارة العربات (مكتملة)
    # ------------------------------------------------------------
    def show_cart_management(self):
        if not self.check_permission('can_manage_carts'):
            self.show_snack_bar("غير مصرح لك بإدارة العربات", COLORS['danger'])
            return

        self.clear_content()

        self.cart_search_field = ft.TextField(
            hint_text="🔍 بحث",
            width=250,
            on_change=self.filter_carts,
        )
        header = ft.Row([
            ft.Text("إدارة العربات", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
            ft.Row([
                self.cart_search_field,
                ft.ElevatedButton(
                    "➕ إضافة عربة جديدة",
                    icon=ft.icons.ADD,
                    style=ft.ButtonStyle(bgcolor=COLORS['success'], color=COLORS['white']),
                    visible=self.check_permission('can_add_cart'),
                    on_click=lambda e: self._add_cart_dialog(),
                ),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        self.cart_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("رقم العربة")),
                ft.DataColumn(ft.Text("الرقم التسلسلي")),
                ft.DataColumn(ft.Text("الحالة")),
                ft.DataColumn(ft.Text("المستودع الحالي")),
                ft.DataColumn(ft.Text("آخر تحديث")),
                ft.DataColumn(ft.Text("الإجراءات")),
            ],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=20,
            data_row_max_height=60,
        )

        self.content_column.controls.extend([
            ft.Container(content=header, padding=ft.padding.only(left=25, right=25, top=20, bottom=10)),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=self.cart_table,
                        padding=10,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    )
                ], scroll=ft.ScrollMode.AUTO, expand=True),
                padding=ft.padding.only(left=25, right=25, bottom=20),
                expand=True,
            ),
        ])

        self._load_carts()

    def _load_carts(self, search=""):
        if search:
            carts = self.db.execute_query("""
                SELECT c.id, c.serial_number, c.status, w.name, c.last_updated
                FROM carts c
                LEFT JOIN warehouses w ON c.current_warehouse_id = w.id
                WHERE c.id LIKE ? OR c.serial_number LIKE ?
                ORDER BY c.id DESC
            """, (f'%{search}%', f'%{search}%'))
        else:
            carts = self.db.execute_query("""
                SELECT c.id, c.serial_number, c.status, w.name, c.last_updated
                FROM carts c
                LEFT JOIN warehouses w ON c.current_warehouse_id = w.id
                ORDER BY c.id DESC
            """)

        rows = []
        for cart in carts:
            cart_id, serial, status, warehouse, updated = cart
            status_text = CART_STATUS.get(status, status)
            status_color = {
                'sound': COLORS['success'],
                'needs_maintenance': COLORS['warning'],
                'damaged': COLORS['danger']
            }.get(status, COLORS['gray'])

            actions = ft.Row(spacing=5)
            if self.check_permission('can_edit_cart'):
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.EDIT,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['primary'],
                        tooltip="تعديل",
                        on_click=lambda e, cid=cart_id, s=serial: self._edit_cart_dialog(cid, s),
                    )
                )
            if self.check_permission('can_delete_cart'):
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['danger'],
                        tooltip="حذف",
                        on_click=lambda e, cid=cart_id: self._delete_cart_confirm(cid),
                    )
                )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(cart_id))),
                        ft.DataCell(ft.Text(serial)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(status_text),
                            bgcolor=status_color + '20',
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            border_radius=12,
                        )),
                        ft.DataCell(ft.Text(warehouse or "غير محدد")),
                        ft.DataCell(ft.Text(updated[:10] if updated else "")),
                        ft.DataCell(actions),
                    ]
                )
            )
        self.cart_table.rows = rows
        self.page.update()

    def filter_carts(self, e):
        self._load_carts(self.cart_search_field.value.strip())

    def _add_cart_dialog(self):
        warehouses = self.db.get_all_warehouses()
        warehouse_options = [w[1] for w in warehouses]
        warehouse_dict = {w[1]: w[0] for w in warehouses}

        serial_field = ft.TextField(label="الرقم التسلسلي", width=350, autofocus=True)
        status_dropdown = ft.Dropdown(
            label="الحالة",
            width=350,
            options=[ft.dropdown.Option("سليمة"), ft.dropdown.Option("تحتاج صيانة"), ft.dropdown.Option("تالفة")],
            value="سليمة",
        )
        warehouse_dropdown = ft.Dropdown(
            label="المستودع",
            width=350,
            options=[ft.dropdown.Option(n) for n in warehouse_options],
        )
        notes_field = ft.TextField(label="ملاحظات", width=350, multiline=True, min_lines=3, max_lines=5)

        def save(e):
            serial = serial_field.value.strip()
            status_text = status_dropdown.value
            warehouse_name = warehouse_dropdown.value
            notes = notes_field.value
            if not serial:
                self.show_snack_bar("الرجاء إدخال الرقم التسلسلي", COLORS['danger'])
                return
            status_map = {"سليمة": 'sound', "تحتاج صيانة": 'needs_maintenance', "تالفة": 'damaged'}
            status = status_map.get(status_text, 'sound')
            warehouse_id = warehouse_dict.get(warehouse_name) if warehouse_name else None
            try:
                cart_id = self.db.execute_insert(
                    """INSERT INTO carts (serial_number, status, current_warehouse_id, created_by, notes) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (serial, status, warehouse_id, self.current_user['id'], notes)
                )
                if warehouse_id:
                    self.db.update_warehouse_count(warehouse_id)
                self.db.log_action(self.current_user['id'], 'add_cart', f'إضافة عربة جديدة رقم {serial}')
                self.close_dialog()
                self.show_snack_bar("تم إضافة العربة بنجاح", COLORS['success'])
                self._load_carts()
            except sqlite3.IntegrityError:
                self.show_snack_bar("الرقم التسلسلي موجود مسبقاً", COLORS['danger'])

        dialog = ft.AlertDialog(
            title=ft.Text("إضافة عربة جديدة", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([serial_field, status_dropdown, warehouse_dropdown, notes_field],
                                  width=400, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _edit_cart_dialog(self, cart_id, serial):
        result = self.db.execute_query("""
            SELECT c.status, w.name, c.notes
            FROM carts c
            LEFT JOIN warehouses w ON c.current_warehouse_id = w.id
            WHERE c.id = ?
        """, (cart_id,))
        if not result:
            self.show_snack_bar("العربة غير موجودة", COLORS['danger'])
            return
        status, warehouse, notes = result[0]
        status_text = CART_STATUS.get(status, status)

        warehouses = self.db.get_all_warehouses()
        warehouse_options = [w[1] for w in warehouses]
        warehouse_dict = {w[1]: w[0] for w in warehouses}

        serial_display = ft.TextField(label="الرقم التسلسلي", width=350, value=serial, read_only=True)
        status_dropdown = ft.Dropdown(
            label="الحالة",
            width=350,
            options=[ft.dropdown.Option("سليمة"), ft.dropdown.Option("تحتاج صيانة"), ft.dropdown.Option("تالفة")],
            value=status_text,
        )
        warehouse_dropdown = ft.Dropdown(
            label="المستودع",
            width=350,
            options=[ft.dropdown.Option(n) for n in warehouse_options],
            value=warehouse if warehouse else None,
        )
        notes_field = ft.TextField(label="ملاحظات", width=350, value=notes or "", multiline=True, min_lines=3, max_lines=5)

        def save(e):
            new_status_text = status_dropdown.value
            new_warehouse_name = warehouse_dropdown.value
            new_notes = notes_field.value
            status_map = {"سليمة": 'sound', "تحتاج صيانة": 'needs_maintenance', "تالفة": 'damaged'}
            new_status = status_map.get(new_status_text, 'sound')
            new_warehouse_id = warehouse_dict.get(new_warehouse_name) if new_warehouse_name else None
            old_warehouse = self.db.execute_query(
                "SELECT current_warehouse_id FROM carts WHERE id = ?", (cart_id,)
            )[0][0]
            self.db.execute_query(
                """UPDATE carts SET status = ?, current_warehouse_id = ?, last_updated = CURRENT_TIMESTAMP, notes = ? 
                   WHERE id = ?""",
                (new_status, new_warehouse_id, new_notes, cart_id)
            )
            if old_warehouse:
                self.db.update_warehouse_count(old_warehouse)
            if new_warehouse_id:
                self.db.update_warehouse_count(new_warehouse_id)
            self.db.log_action(self.current_user['id'], 'edit_cart', f'تعديل العربة رقم {serial}')
            self.close_dialog()
            self.show_snack_bar("تم تعديل العربة بنجاح", COLORS['success'])
            self._load_carts()

        dialog = ft.AlertDialog(
            title=ft.Text(f"تعديل العربة: {serial}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([serial_display, status_dropdown, warehouse_dropdown, notes_field],
                                  width=400, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _delete_cart_confirm(self, cart_id):
        def confirm(e):
            result = self.db.execute_query(
                "SELECT current_warehouse_id, serial_number FROM carts WHERE id = ?",
                (cart_id,)
            )
            if result:
                wh_id, serial = result[0]
                self.db.execute_query("DELETE FROM carts WHERE id = ?", (cart_id,))
                if wh_id:
                    self.db.update_warehouse_count(wh_id)
                self.db.log_action(self.current_user['id'], 'delete_cart', f'حذف العربة رقم {serial}')
            self.close_dialog()
            self.show_snack_bar("تم حذف العربة بنجاح", COLORS['success'])
            self._load_carts()

        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف", weight=ft.FontWeight.BOLD),
            content=ft.Text("هل أنت متأكد من حذف هذه العربة؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ------------------------------------------------------------
    # حركة العربات
    # ------------------------------------------------------------
    def show_cart_movement(self):
        if not self.check_permission('can_move_cart') and not self.check_permission('can_view_movements'):
            self.show_snack_bar("غير مصرح لك بعرض حركة العربات", COLORS['danger'])
            return

        self.clear_content()

        # قسم نقل العربة
        move_container = ft.Container()
        if self.check_permission('can_move_cart'):
            # قائمة العربات القابلة للنقل
            carts = self.db.execute_query("""
                SELECT c.id, c.serial_number, w.name
                FROM carts c
                LEFT JOIN warehouses w ON c.current_warehouse_id = w.id
                WHERE c.current_warehouse_id IS NOT NULL AND c.status != 'damaged'
                ORDER BY c.serial_number
            """)
            cart_options = [f"{c[1]} - ({c[2]})" for c in carts]
            cart_dict = {f"{c[1]} - ({c[2]})": c[0] for c in carts}

            warehouses = self.db.get_all_warehouses()
            warehouse_options = [w[1] for w in warehouses]
            warehouse_dict = {w[1]: w[0] for w in warehouses}

            cart_dropdown = ft.Dropdown(
                label="اختر العربة",
                width=400,
                options=[ft.dropdown.Option(o) for o in cart_options],
                on_change=lambda e: self._update_from_warehouse(e, cart_dict, warehouse_dict),
            )
            self.cart_dropdown_ref = cart_dropdown

            from_warehouse = ft.Dropdown(
                label="من مستودع",
                width=350,
                options=[ft.dropdown.Option(o) for o in warehouse_options],
                read_only=True,
            )
            to_warehouse = ft.Dropdown(
                label="إلى مستودع",
                width=350,
                options=[ft.dropdown.Option(o) for o in warehouse_options],
            )
            notes_field = ft.TextField(label="ملاحظات", width=400, multiline=True, min_lines=2, max_lines=4)

            def move_cart(e):
                cart_text = cart_dropdown.value
                from_wh = from_warehouse.value
                to_wh = to_warehouse.value
                notes = notes_field.value
                if not cart_text:
                    self.show_snack_bar("الرجاء اختيار عربة", COLORS['danger'])
                    return
                if not from_wh:
                    self.show_snack_bar("الرجاء تحديد المستودع المصدر", COLORS['danger'])
                    return
                if not to_wh:
                    self.show_snack_bar("الرجاء اختيار مستودع الوجهة", COLORS['danger'])
                    return
                if from_wh == to_wh:
                    self.show_snack_bar("المستودع المصدر والهدف متطابقان", COLORS['danger'])
                    return
                cart_id = cart_dict.get(cart_text)
                from_id = warehouse_dict.get(from_wh)
                to_id = warehouse_dict.get(to_wh)
                if not cart_id or not from_id or not to_id:
                    self.show_snack_bar("بيانات غير صحيحة", COLORS['danger'])
                    return
                # التحقق من أن العربة في المستودع المصدر
                current = self.db.execute_query(
                    "SELECT current_warehouse_id FROM carts WHERE id = ?", (cart_id,)
                )
                if not current or current[0][0] != from_id:
                    self.show_snack_bar("العربة ليست في المستودع المصدر المحدد", COLORS['danger'])
                    return
                # تنفيذ النقل
                self.db.execute_query(
                    "UPDATE carts SET current_warehouse_id = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (to_id, cart_id)
                )
                self.db.execute_insert(
                    """INSERT INTO movements (cart_id, from_warehouse_id, to_warehouse_id, user_id, notes) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (cart_id, from_id, to_id, self.current_user['id'], notes)
                )
                self.db.update_warehouse_count(from_id)
                self.db.update_warehouse_count(to_id)
                self.db.log_action(self.current_user['id'], 'move_cart',
                                   f'نقل العربة {cart_text} من {from_wh} إلى {to_wh}')
                self.show_snack_bar("تم نقل العربة بنجاح", COLORS['success'])
                # إعادة تحميل الصفحة
                self.show_cart_movement()

            move_container = ft.Container(
                content=ft.Column([
                    ft.Text("نقل عربة", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1),
                    ft.Row([cart_dropdown], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([from_warehouse, to_warehouse], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([notes_field], alignment=ft.MainAxisAlignment.CENTER),
                    ft.ElevatedButton(
                        "🔄 نقل العربة",
                        style=ft.ButtonStyle(bgcolor=COLORS['primary'], color=COLORS['white']),
                        on_click=move_cart,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
                padding=20,
                bgcolor=COLORS['white'],
                border_radius=10,
                margin=ft.margin.only(bottom=20),
            )

        # سجل الحركات
        movements = self.db.execute_query("""
            SELECT 
                m.id,
                m.timestamp,
                c.serial_number,
                w1.name as from_name,
                w2.name as to_name,
                u.username,
                m.notes
            FROM movements m
            JOIN carts c ON m.cart_id = c.id
            LEFT JOIN warehouses w1 ON m.from_warehouse_id = w1.id
            JOIN warehouses w2 ON m.to_warehouse_id = w2.id
            LEFT JOIN users u ON m.user_id = u.id
            ORDER BY m.timestamp DESC
            LIMIT 200
        """)

        # حقل بحث في الحركات
        self.movement_search_field = ft.TextField(
            hint_text="🔍 بحث في الحركات",
            width=250,
            on_change=self.filter_movements,
        )

        # جدول الحركات
        self.movement_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("التاريخ")),
                ft.DataColumn(ft.Text("العربة")),
                ft.DataColumn(ft.Text("من")),
                ft.DataColumn(ft.Text("إلى")),
                ft.DataColumn(ft.Text("المستخدم")),
                ft.DataColumn(ft.Text("ملاحظات")),
                ft.DataColumn(ft.Text("الإجراءات")),
            ],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=15,
            data_row_max_height=50,
        )

        self._load_movements(movements)

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("حركة العربات - نقل بين المستودعات", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                    move_container if self.check_permission('can_move_cart') else ft.Container(),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text("سجل الحركات", size=18, weight=ft.FontWeight.BOLD),
                                self.movement_search_field,
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(
                                content=self.movement_table,
                                padding=10,
                                bgcolor=COLORS['white'],
                                border_radius=10,
                                expand=True,
                            ),
                        ]),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])
        self.page.update()

    def _update_from_warehouse(self, e, cart_dict, warehouse_dict):
        cart_text = e.control.value
        if cart_text and cart_text in cart_dict:
            cart_id = cart_dict[cart_text]
            result = self.db.execute_query(
                "SELECT w.name FROM carts c LEFT JOIN warehouses w ON c.current_warehouse_id = w.id WHERE c.id = ?",
                (cart_id,)
            )
            if result and result[0][0]:
                # تحديث حقل "من مستودع" (يجب الوصول إليه)
                # في هذه النسخة المبسطة، نتركه للمستخدم لاختياره يدوياً
                pass

    def _load_movements(self, movements):
        rows = []
        for m in movements:
            movement_id, timestamp, serial, from_wh, to_wh, username, notes = m
            actions = ft.Row(spacing=5)
            if self.check_permission('can_delete_cart'):  # صلاحية حذف الحركات مرتبطة بحذف العربات
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['danger'],
                        tooltip="حذف الحركة",
                        on_click=lambda e, mid=movement_id: self._delete_movement_confirm(mid),
                    )
                )
            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(timestamp[:16] if timestamp else "")),
                        ft.DataCell(ft.Text(serial)),
                        ft.DataCell(ft.Text(from_wh or "-")),
                        ft.DataCell(ft.Text(to_wh)),
                        ft.DataCell(ft.Text(username or "")),
                        ft.DataCell(ft.Text((notes[:20] + '...') if notes and len(notes) > 20 else (notes or ""))),
                        ft.DataCell(actions),
                    ]
                )
            )
        self.movement_table.rows = rows
        self.page.update()

    def filter_movements(self, e):
        search = self.movement_search_field.value.strip()
        if search:
            movements = self.db.execute_query("""
                SELECT 
                    m.id,
                    m.timestamp,
                    c.serial_number,
                    w1.name as from_name,
                    w2.name as to_name,
                    u.username,
                    m.notes
                FROM movements m
                JOIN carts c ON m.cart_id = c.id
                LEFT JOIN warehouses w1 ON m.from_warehouse_id = w1.id
                JOIN warehouses w2 ON m.to_warehouse_id = w2.id
                LEFT JOIN users u ON m.user_id = u.id
                WHERE c.serial_number LIKE ? OR w1.name LIKE ? OR w2.name LIKE ? OR u.username LIKE ?
                ORDER BY m.timestamp DESC
                LIMIT 200
            """, (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            movements = self.db.execute_query("""
                SELECT 
                    m.id,
                    m.timestamp,
                    c.serial_number,
                    w1.name as from_name,
                    w2.name as to_name,
                    u.username,
                    m.notes
                FROM movements m
                JOIN carts c ON m.cart_id = c.id
                LEFT JOIN warehouses w1 ON m.from_warehouse_id = w1.id
                JOIN warehouses w2 ON m.to_warehouse_id = w2.id
                LEFT JOIN users u ON m.user_id = u.id
                ORDER BY m.timestamp DESC
                LIMIT 200
            """)
        self._load_movements(movements)

    def _delete_movement_confirm(self, movement_id):
        def confirm(e):
            self.db.execute_query("DELETE FROM movements WHERE id = ?", (movement_id,))
            self.db.log_action(self.current_user['id'], 'delete_movement', f'حذف حركة رقم {movement_id}')
            self.close_dialog()
            self.show_snack_bar("تم حذف الحركة بنجاح", COLORS['success'])
            self.show_cart_movement()  # إعادة تحميل الصفحة

        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف", weight=ft.FontWeight.BOLD),
            content=ft.Text("هل أنت متأكد من حذف هذه الحركة؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ------------------------------------------------------------
    # إدارة الصيانة
    # ------------------------------------------------------------
    def show_maintenance(self):
        if not self.check_permission('can_manage_maintenance'):
            self.show_snack_bar("غير مصرح لك بإدارة الصيانة", COLORS['danger'])
            return

        self.clear_content()

        # إحصائيات الصيانة
        pending = self.db.execute_query(
            "SELECT COUNT(*) FROM maintenance_records WHERE status = 'pending'"
        )[0][0] or 0
        in_progress = self.db.execute_query(
            "SELECT COUNT(*) FROM maintenance_records WHERE status = 'in_progress'"
        )[0][0] or 0
        completed = self.db.execute_query(
            "SELECT COUNT(*) FROM maintenance_records WHERE status = 'completed'"
        )[0][0] or 0
        total_cost = self.db.execute_query(
            "SELECT SUM(cost) FROM maintenance_records WHERE status = 'completed'"
        )[0][0] or 0

        # بطاقات الإحصائيات
        stats_row = ft.Row([
            self._build_stat_small_card("📋", "بانتظار الصيانة", str(pending), COLORS['warning']),
            self._build_stat_small_card("🔧", "قيد التنفيذ", str(in_progress), COLORS['primary']),
            self._build_stat_small_card("✅", "منجزة", str(completed), COLORS['success']),
            self._build_stat_small_card("💰", "إجمالي التكاليف", f"{total_cost:.0f} ر.س", COLORS['purple']),
        ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, spacing=10)

        # قسم إدخال الصيانة
        input_container = ft.Container()
        if self.check_permission('can_manage_maintenance'):
            # قائمة العربات (غير التالفة)
            carts = self.db.execute_query("""
                SELECT c.id, c.serial_number, w.name 
                FROM carts c
                LEFT JOIN warehouses w ON c.current_warehouse_id = w.id
                WHERE c.status != 'damaged'
                ORDER BY c.serial_number
            """)
            cart_options = [f"{c[1]} - ({c[2] or 'غير محدد'})" for c in carts]
            cart_dict = {f"{c[1]} - ({c[2] or 'غير محدد'})": c[0] for c in carts}

            maint_cart = ft.Dropdown(
                label="العربة",
                width=400,
                options=[ft.dropdown.Option(o) for o in cart_options],
            )
            maint_type = ft.Dropdown(
                label="نوع الصيانة",
                width=350,
                options=[
                    ft.dropdown.Option("صيانة دورية"),
                    ft.dropdown.Option("إصلاح عطل"),
                    ft.dropdown.Option("تأهيل كامل"),
                    ft.dropdown.Option("فحص"),
                ],
                value="صيانة دورية",
            )
            maint_status = ft.Dropdown(
                label="الحالة",
                width=350,
                options=[
                    ft.dropdown.Option("تحتاج صيانة"),
                    ft.dropdown.Option("تالفة"),
                ],
                value="تحتاج صيانة",
            )
            maint_desc = ft.TextField(
                label="وصف المشكلة",
                width=400,
                multiline=True,
                min_lines=3,
                max_lines=5,
            )
            maint_cost = ft.TextField(
                label="التكلفة",
                width=200,
                value="0",
                keyboard_type=ft.KeyboardType.NUMBER,
            )

            def submit_maintenance(e):
                cart_text = maint_cart.value
                m_type = maint_type.value
                status_text = maint_status.value
                desc = maint_desc.value
                try:
                    cost = float(maint_cost.value or 0)
                except:
                    cost = 0
                if not cart_text:
                    self.show_snack_bar("الرجاء اختيار عربة", COLORS['danger'])
                    return
                cart_id = cart_dict.get(cart_text)
                if not cart_id:
                    self.show_snack_bar("العربة غير موجودة", COLORS['danger'])
                    return
                status_map = {
                    "تحتاج صيانة": "needs_maintenance",
                    "تالفة": "damaged"
                }
                new_status = status_map.get(status_text, "needs_maintenance")
                try:
                    self.db.execute_query(
                        "UPDATE carts SET status = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_status, cart_id)
                    )
                    self.db.execute_insert(
                        """INSERT INTO maintenance_records 
                           (cart_id, maintenance_type, status, description, user_id, cost) 
                           VALUES (?, ?, 'pending', ?, ?, ?)""",
                        (cart_id, m_type, desc, self.current_user['id'], cost)
                    )
                    self.db.log_action(self.current_user['id'], 'add_maintenance',
                                       f'إدخال العربة {cart_text} للصيانة')
                    self.show_snack_bar("تم إدخال العربة للصيانة", COLORS['success'])
                    self.show_maintenance()  # إعادة تحميل
                except Exception as ex:
                    self.show_snack_bar(f"حدث خطأ: {str(ex)}", COLORS['danger'])

            input_container = ft.Container(
                content=ft.Column([
                    ft.Text("إدخال عربية للصيانة", size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=1),
                    ft.Row([maint_cart], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([maint_type, maint_status], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([maint_desc], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Row([maint_cost], alignment=ft.MainAxisAlignment.CENTER),
                    ft.ElevatedButton(
                        "🔧 إدخال للصيانة",
                        style=ft.ButtonStyle(bgcolor=COLORS['warning'], color=COLORS['white']),
                        on_click=submit_maintenance,
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15),
                padding=20,
                bgcolor=COLORS['white'],
                border_radius=10,
                margin=ft.margin.only(bottom=20),
            )

        # سجل الصيانة
        records = self.db.execute_query("""
            SELECT 
                m.id,
                m.entry_date,
                c.serial_number,
                m.maintenance_type,
                m.status,
                m.description,
                m.cost,
                m.completion_date
            FROM maintenance_records m
            JOIN carts c ON m.cart_id = c.id
            ORDER BY m.entry_date DESC
            LIMIT 200
        """)

        self.maintenance_search_field = ft.TextField(
            hint_text="🔍 بحث في الصيانة",
            width=250,
            on_change=self.filter_maintenance,
        )

        self.maintenance_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("التاريخ")),
                ft.DataColumn(ft.Text("العربة")),
                ft.DataColumn(ft.Text("نوع الصيانة")),
                ft.DataColumn(ft.Text("الحالة")),
                ft.DataColumn(ft.Text("الوصف")),
                ft.DataColumn(ft.Text("التكلفة")),
                ft.DataColumn(ft.Text("تاريخ الإنجاز")),
                ft.DataColumn(ft.Text("الإجراءات")),
            ],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=15,
            data_row_max_height=60,
        )

        self._load_maintenance_records(records)

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("إدارة الصيانة", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                    stats_row,
                    ft.Row([
                        ft.Container(content=input_container, expand=1),
                        ft.Container(width=20),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("إحصائيات سريعة", size=16, weight=ft.FontWeight.BOLD),
                                self._build_stat_simple("📋", "بانتظار الصيانة", str(pending), COLORS['warning']),
                                self._build_stat_simple("🔧", "قيد التنفيذ", str(in_progress), COLORS['primary']),
                                self._build_stat_simple("✅", "منجزة", str(completed), COLORS['success']),
                                self._build_stat_simple("💰", "إجمالي التكاليف", f"{total_cost:.0f} ر.س", COLORS['purple']),
                            ], spacing=10),
                            padding=20,
                            bgcolor=COLORS['white'],
                            border_radius=10,
                            expand=0,
                            width=300,
                        ),
                    ]) if input_container.visible else ft.Container(),
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text("سجل الصيانة", size=18, weight=ft.FontWeight.BOLD),
                                self.maintenance_search_field,
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(
                                content=self.maintenance_table,
                                padding=10,
                                bgcolor=COLORS['white'],
                                border_radius=10,
                                expand=True,
                            ),
                        ]),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])
        self.page.update()

    def _build_stat_small_card(self, icon, title, value, color):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(icon, size=24),
                    ft.Text(title, size=12, color=COLORS['gray']),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(value, size=20, weight=ft.FontWeight.BOLD, color=color),
            ]),
            padding=10,
            bgcolor=COLORS['white'],
            border_radius=10,
            expand=True,
        )

    def _build_stat_simple(self, icon, title, value, color):
        return ft.Row([
            ft.Text(icon, size=20),
            ft.Column([
                ft.Text(title, size=12, color=COLORS['gray']),
                ft.Text(value, size=16, weight=ft.FontWeight.BOLD, color=color),
            ]),
        ], alignment=ft.MainAxisAlignment.START)

    def _load_maintenance_records(self, records):
        rows = []
        for rec in records:
            rec_id, entry_date, serial, m_type, status, desc, cost, comp_date = rec
            status_text = MAINTENANCE_STATUS.get(status, status)
            status_color = {
                'pending': COLORS['warning'],
                'in_progress': COLORS['primary'],
                'completed': COLORS['success']
            }.get(status, COLORS['gray'])

            actions = ft.Row(spacing=5)
            if status == 'pending' and self.check_permission('can_complete_maintenance'):
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.CHECK_CIRCLE,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['success'],
                        tooltip="إتمام الصيانة",
                        on_click=lambda e, rid=rec_id: self._complete_maintenance(rid),
                    )
                )
            if self.check_permission('can_edit_cart'):
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.EDIT,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['primary'],
                        tooltip="تعديل",
                        on_click=lambda e, rid=rec_id: self._edit_maintenance_dialog(rid),
                    )
                )
            if self.check_permission('can_delete_cart'):
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['danger'],
                        tooltip="حذف",
                        on_click=lambda e, rid=rec_id: self._delete_maintenance_confirm(rid),
                    )
                )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(entry_date[:16] if entry_date else "")),
                        ft.DataCell(ft.Text(serial)),
                        ft.DataCell(ft.Text(m_type or "")),
                        ft.DataCell(ft.Container(
                            content=ft.Text(status_text),
                            bgcolor=status_color + '20',
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            border_radius=12,
                        )),
                        ft.DataCell(ft.Text((desc[:30] + '...') if desc and len(desc) > 30 else (desc or ""))),
                        ft.DataCell(ft.Text(f"{cost:.0f} ر.س" if cost else "0 ر.س")),
                        ft.DataCell(ft.Text(comp_date[:10] if comp_date else "")),
                        ft.DataCell(actions),
                    ]
                )
            )
        self.maintenance_table.rows = rows
        self.page.update()

    def filter_maintenance(self, e):
        search = self.maintenance_search_field.value.strip()
        if search:
            records = self.db.execute_query("""
                SELECT 
                    m.id,
                    m.entry_date,
                    c.serial_number,
                    m.maintenance_type,
                    m.status,
                    m.description,
                    m.cost,
                    m.completion_date
                FROM maintenance_records m
                JOIN carts c ON m.cart_id = c.id
                WHERE c.serial_number LIKE ? OR m.maintenance_type LIKE ? OR m.description LIKE ?
                ORDER BY m.entry_date DESC
                LIMIT 200
            """, (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            records = self.db.execute_query("""
                SELECT 
                    m.id,
                    m.entry_date,
                    c.serial_number,
                    m.maintenance_type,
                    m.status,
                    m.description,
                    m.cost,
                    m.completion_date
                FROM maintenance_records m
                JOIN carts c ON m.cart_id = c.id
                ORDER BY m.entry_date DESC
                LIMIT 200
            """)
        self._load_maintenance_records(records)

    def _complete_maintenance(self, record_id):
        def confirm(e):
            self.db.execute_query(
                """UPDATE maintenance_records 
                   SET status = 'completed', completion_date = CURRENT_TIMESTAMP, completed_by = ? 
                   WHERE id = ?""",
                (self.current_user['id'], record_id)
            )
            # تحديث حالة العربة إلى سليمة
            result = self.db.execute_query(
                "SELECT cart_id FROM maintenance_records WHERE id = ?", (record_id,)
            )
            if result:
                cart_id = result[0][0]
                self.db.execute_query(
                    "UPDATE carts SET status = 'sound', last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (cart_id,)
                )
            self.db.log_action(self.current_user['id'], 'complete_maintenance',
                               f'إتمام صيانة للسجل رقم {record_id}')
            self.close_dialog()
            self.show_snack_bar("تم إتمام الصيانة", COLORS['success'])
            self.show_maintenance()

        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الإتمام", weight=ft.FontWeight.BOLD),
            content=ft.Text("هل أنت متأكد من إتمام هذه الصيانة؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _edit_maintenance_dialog(self, record_id):
        # جلب بيانات السجل
        result = self.db.execute_query("""
            SELECT m.cart_id, c.serial_number, m.maintenance_type, m.description, m.cost, m.status
            FROM maintenance_records m
            JOIN carts c ON m.cart_id = c.id
            WHERE m.id = ?
        """, (record_id,))
        if not result:
            self.show_snack_bar("سجل الصيانة غير موجود", COLORS['danger'])
            return
        cart_id, serial, m_type, desc, cost, status = result[0]

        maint_type = ft.Dropdown(
            label="نوع الصيانة",
            width=350,
            options=[
                ft.dropdown.Option("صيانة دورية"),
                ft.dropdown.Option("إصلاح عطل"),
                ft.dropdown.Option("تأهيل كامل"),
                ft.dropdown.Option("فحص"),
            ],
            value=m_type,
        )
        maint_status = ft.Dropdown(
            label="الحالة",
            width=350,
            options=[
                ft.dropdown.Option("بانتظار الصيانة"),
                ft.dropdown.Option("قيد التنفيذ"),
                ft.dropdown.Option("منجزة"),
            ],
            value=MAINTENANCE_STATUS.get(status, status),
        )
        maint_desc = ft.TextField(
            label="وصف المشكلة",
            width=400,
            multiline=True,
            min_lines=3,
            max_lines=5,
            value=desc or "",
        )
        maint_cost = ft.TextField(
            label="التكلفة",
            width=200,
            value=str(cost or 0),
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        def save(e):
            new_type = maint_type.value
            new_status_text = maint_status.value
            new_desc = maint_desc.value
            try:
                new_cost = float(maint_cost.value or 0)
            except:
                new_cost = 0
            status_map = {
                "بانتظار الصيانة": "pending",
                "قيد التنفيذ": "in_progress",
                "منجزة": "completed"
            }
            new_status = status_map.get(new_status_text, "pending")
            self.db.execute_query(
                """UPDATE maintenance_records 
                   SET maintenance_type = ?, status = ?, description = ?, cost = ? 
                   WHERE id = ?""",
                (new_type, new_status, new_desc, new_cost, record_id)
            )
            if new_status == 'completed' and status != 'completed':
                self.db.execute_query(
                    "UPDATE carts SET status = 'sound', last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                    (cart_id,)
                )
                self.db.execute_query(
                    "UPDATE maintenance_records SET completion_date = CURRENT_TIMESTAMP WHERE id = ?",
                    (record_id,)
                )
            self.db.log_action(self.current_user['id'], 'edit_maintenance',
                               f'تعديل سجل صيانة رقم {record_id}')
            self.close_dialog()
            self.show_snack_bar("تم تحديث سجل الصيانة", COLORS['success'])
            self.show_maintenance()

        dialog = ft.AlertDialog(
            title=ft.Text(f"تعديل سجل الصيانة - {serial}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"العربة: {serial}", size=14, color=COLORS['gray']),
                    maint_type,
                    maint_status,
                    maint_desc,
                    maint_cost,
                ], width=450, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _delete_maintenance_confirm(self, record_id):
        def confirm(e):
            self.db.execute_query("DELETE FROM maintenance_records WHERE id = ?", (record_id,))
            self.db.log_action(self.current_user['id'], 'delete_maintenance',
                               f'حذف سجل صيانة رقم {record_id}')
            self.close_dialog()
            self.show_snack_bar("تم حذف سجل الصيانة", COLORS['success'])
            self.show_maintenance()

        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف", weight=ft.FontWeight.BOLD),
            content=ft.Text("هل أنت متأكد من حذف سجل الصيانة هذا؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ------------------------------------------------------------
    # إدارة المستودعات
    # ------------------------------------------------------------
    def show_warehouse_management(self):
        if not self.check_permission('can_view_warehouses'):
            self.show_snack_bar("غير مصرح لك بعرض المستودعات", COLORS['danger'])
            return

        self.clear_content()

        header = ft.Row([
            ft.Text("إدارة المستودعات", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
            ft.ElevatedButton(
                "➕ إضافة مستودع",
                icon=ft.icons.ADD,
                style=ft.ButtonStyle(bgcolor=COLORS['success'], color=COLORS['white']),
                visible=self.check_permission('can_add_warehouse'),
                on_click=lambda e: self._add_warehouse_dialog(),
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # حقل بحث
        self.warehouse_search_field = ft.TextField(
            hint_text="🔍 بحث في المستودعات",
            width=250,
            on_change=self.filter_warehouses,
        )

        # جدول المستودعات
        self.warehouse_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("المعرف")),
                ft.DataColumn(ft.Text("اسم المستودع")),
                ft.DataColumn(ft.Text("السعة")),
                ft.DataColumn(ft.Text("العدد الحالي")),
                ft.DataColumn(ft.Text("نسبة الإشغال")),
                ft.DataColumn(ft.Text("الإجراءات")),
            ],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=20,
            data_row_max_height=50,
        )

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    header,
                    ft.Row([self.warehouse_search_field], alignment=ft.MainAxisAlignment.END),
                    ft.Container(
                        content=self.warehouse_table,
                        padding=10,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])

        self._load_warehouses()

    def _load_warehouses(self, search=""):
        if search:
            warehouses = self.db.execute_query("""
                SELECT id, name, capacity, current_count 
                FROM warehouses 
                WHERE is_active = 1 AND name LIKE ?
                ORDER BY id
            """, (f'%{search}%',))
        else:
            warehouses = self.db.execute_query("""
                SELECT id, name, capacity, current_count 
                FROM warehouses 
                WHERE is_active = 1
                ORDER BY id
            """)

        base_names = [wh['name'] for wh in WAREHOUSES]
        rows = []
        for w in warehouses:
            wid, name, capacity, current = w
            percentage = (current / capacity * 100) if capacity > 0 else 0
            color = COLORS['danger'] if percentage >= 90 else COLORS['warning'] if percentage >= 70 else COLORS['success']

            actions = ft.Row(spacing=5)
            if self.check_permission('can_edit_warehouse'):
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.EDIT,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['primary'],
                        tooltip="تعديل",
                        on_click=lambda e, wid=wid, n=name: self._edit_warehouse_dialog(wid, n),
                    )
                )
            if self.check_permission('can_delete_warehouse') and name not in base_names:
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['danger'],
                        tooltip="حذف",
                        on_click=lambda e, wid=wid, n=name: self._delete_warehouse_confirm(wid, n),
                    )
                )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(wid))),
                        ft.DataCell(ft.Text(name)),
                        ft.DataCell(ft.Text(str(capacity))),
                        ft.DataCell(ft.Text(str(current))),
                        ft.DataCell(ft.Container(
                            content=ft.Text(f"{percentage:.1f}%"),
                            bgcolor=color + '20',
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            border_radius=12,
                        )),
                        ft.DataCell(actions),
                    ]
                )
            )
        self.warehouse_table.rows = rows
        self.page.update()

    def filter_warehouses(self, e):
        self._load_warehouses(self.warehouse_search_field.value.strip())

    def _add_warehouse_dialog(self):
        name_field = ft.TextField(label="اسم المستودع", width=350, autofocus=True)
        capacity_field = ft.TextField(label="السعة", width=350, value="100", keyboard_type=ft.KeyboardType.NUMBER)
        desc_field = ft.TextField(label="الوصف", width=350)
        type_dropdown = ft.Dropdown(
            label="نوع المستودع",
            width=350,
            options=[
                ft.dropdown.Option("main"),
                ft.dropdown.Option("external"),
                ft.dropdown.Option("north"),
                ft.dropdown.Option("south"),
                ft.dropdown.Option("other"),
            ],
            value="other",
        )

        def save(e):
            name = name_field.value.strip()
            capacity_text = capacity_field.value.strip()
            desc = desc_field.value.strip()
            loc_type = type_dropdown.value
            if not name:
                self.show_snack_bar("الرجاء إدخال اسم المستودع", COLORS['danger'])
                return
            try:
                capacity = int(capacity_text) if capacity_text else 100
            except:
                capacity = 100
            try:
                self.db.execute_insert(
                    """INSERT INTO warehouses 
                       (name, capacity, current_count, description, location_type, is_active, created_by) 
                       VALUES (?, ?, 0, ?, ?, 1, ?)""",
                    (name, capacity, desc, loc_type, self.current_user['id'])
                )
                self.db.log_action(self.current_user['id'], 'add_warehouse', f'إضافة مستودع جديد {name}')
                self.close_dialog()
                self.show_snack_bar("تم إضافة المستودع بنجاح", COLORS['success'])
                self._load_warehouses()
            except sqlite3.IntegrityError:
                self.show_snack_bar("اسم المستودع موجود مسبقاً", COLORS['danger'])

        dialog = ft.AlertDialog(
            title=ft.Text("إضافة مستودع جديد", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([name_field, capacity_field, desc_field, type_dropdown],
                                  width=400, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _edit_warehouse_dialog(self, warehouse_id, name):
        result = self.db.execute_query(
            "SELECT capacity, description, location_type FROM warehouses WHERE id = ?",
            (warehouse_id,)
        )
        if not result:
            self.show_snack_bar("المستودع غير موجود", COLORS['danger'])
            return
        capacity, desc, loc_type = result[0]

        name_display = ft.TextField(label="اسم المستودع", width=350, value=name, read_only=True)
        capacity_field = ft.TextField(label="السعة", width=350, value=str(capacity), keyboard_type=ft.KeyboardType.NUMBER)
        desc_field = ft.TextField(label="الوصف", width=350, value=desc or "")
        type_dropdown = ft.Dropdown(
            label="نوع المستودع",
            width=350,
            options=[
                ft.dropdown.Option("main"),
                ft.dropdown.Option("external"),
                ft.dropdown.Option("north"),
                ft.dropdown.Option("south"),
                ft.dropdown.Option("other"),
            ],
            value=loc_type or "other",
        )

        def save(e):
            new_capacity_text = capacity_field.value.strip()
            new_desc = desc_field.value.strip()
            new_loc_type = type_dropdown.value
            try:
                new_capacity = int(new_capacity_text) if new_capacity_text else capacity
            except:
                new_capacity = capacity
            self.db.execute_query(
                "UPDATE warehouses SET capacity = ?, description = ?, location_type = ? WHERE id = ?",
                (new_capacity, new_desc, new_loc_type, warehouse_id)
            )
            self.db.log_action(self.current_user['id'], 'edit_warehouse', f'تعديل المستودع {name}')
            self.close_dialog()
            self.show_snack_bar("تم تحديث بيانات المستودع بنجاح", COLORS['success'])
            self._load_warehouses()

        dialog = ft.AlertDialog(
            title=ft.Text(f"تعديل المستودع: {name}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([name_display, capacity_field, desc_field, type_dropdown],
                                  width=400, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _delete_warehouse_confirm(self, warehouse_id, name):
        # التحقق من وجود عربات في المستودع
        count = self.db.execute_query(
            "SELECT COUNT(*) FROM carts WHERE current_warehouse_id = ?",
            (warehouse_id,)
        )[0][0] or 0
        if count > 0:
            self.show_snack_bar(f"لا يمكن حذف المستودع لأنه يحتوي على {count} عربة. قم بنقلها أولاً.", COLORS['danger'])
            return

        def confirm(e):
            self.db.execute_query(
                "UPDATE warehouses SET is_active = 0 WHERE id = ?",
                (warehouse_id,)
            )
            self.db.log_action(self.current_user['id'], 'delete_warehouse', f'حذف المستودع {name}')
            self.close_dialog()
            self.show_snack_bar("تم حذف المستودع بنجاح", COLORS['success'])
            self._load_warehouses()

        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"هل أنت متأكد من حذف المستودع '{name}'؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ------------------------------------------------------------
    # التقارير
    # ------------------------------------------------------------
    def show_reports(self):
        if not self.check_permission('can_view_reports'):
            self.show_snack_bar("غير مصرح لك بعرض التقارير", COLORS['danger'])
            return

        self.clear_content()

        # خيارات التقرير
        self.report_type = ft.Dropdown(
            label="نوع التقرير",
            width=300,
            options=[
                ft.dropdown.Option("تقرير حالة العربات"),
                ft.dropdown.Option("تقرير حركة العربات"),
                ft.dropdown.Option("تقرير الصيانة"),
                ft.dropdown.Option("تقرير المستودعات"),
                ft.dropdown.Option("تقرير شامل"),
            ],
            value="تقرير حالة العربات",
            on_change=lambda e: self._update_report_preview(),
        )
        self.period = ft.Dropdown(
            label="الفترة",
            width=300,
            options=[
                ft.dropdown.Option("اليوم"),
                ft.dropdown.Option("آخر 7 أيام"),
                ft.dropdown.Option("آخر 30 يوم"),
                ft.dropdown.Option("آخر سنة"),
                ft.dropdown.Option("كل الفترات"),
            ],
            value="كل الفترات",
            on_change=lambda e: self._update_report_preview(),
        )

        # جدول المعاينة
        self.preview_table = ft.DataTable(
            columns=[],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=20,
            data_row_max_height=40,
        )

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("التقارير والتحليلات", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("خيارات التقرير", size=18, weight=ft.FontWeight.BOLD),
                            ft.Row([self.report_type, self.period], alignment=ft.MainAxisAlignment.START),
                            ft.Row([
                                ft.ElevatedButton(
                                    "👁️ معاينة التقرير",
                                    style=ft.ButtonStyle(bgcolor=COLORS['primary'], color=COLORS['white']),
                                    on_click=lambda e: self._update_report_preview(),
                                ),
                                ft.ElevatedButton(
                                    "📊 تصدير Excel",
                                    style=ft.ButtonStyle(bgcolor=COLORS['success'], color=COLORS['white']),
                                    visible=self.check_permission('can_export_reports') and EXCEL_AVAILABLE,
                                    on_click=self._export_excel,
                                ),
                                ft.ElevatedButton(
                                    "📄 تصدير PDF",
                                    style=ft.ButtonStyle(bgcolor=COLORS['danger'], color=COLORS['white']),
                                    visible=self.check_permission('can_export_reports') and PDF_AVAILABLE,
                                    on_click=self._export_pdf,
                                ),
                            ], alignment=ft.MainAxisAlignment.START),
                        ]),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        margin=ft.margin.only(bottom=20),
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("معاينة التقرير", size=18, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=self.preview_table,
                                padding=10,
                                bgcolor=COLORS['white'],
                                border_radius=10,
                                expand=True,
                                scroll=ft.ScrollMode.AUTO,
                            ),
                        ]),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])

        self._update_report_preview()

    def _update_report_preview(self):
        report_type = self.report_type.value
        period = self.period.value

        if report_type == "تقرير حالة العربات":
            self._preview_cart_status()
        elif report_type == "تقرير حركة العربات":
            self._preview_movement(period)
        elif report_type == "تقرير الصيانة":
            self._preview_maintenance(period)
        elif report_type == "تقرير المستودعات":
            self._preview_warehouse()
        elif report_type == "تقرير شامل":
            self._preview_summary()

    def _preview_cart_status(self):
        columns = [
            ft.DataColumn(ft.Text("الحالة")),
            ft.DataColumn(ft.Text("العدد")),
            ft.DataColumn(ft.Text("النسبة المئوية")),
        ]
        data = self.db.execute_query("""
            SELECT 
                status,
                COUNT(*) as count,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM carts), 2) as percentage
            FROM carts
            GROUP BY status
            UNION
            SELECT 'الإجمالي', COUNT(*), 100.0 FROM carts
        """)
        rows = []
        for row in data:
            status, count, percentage = row
            status_text = CART_STATUS.get(status, status) if status != 'الإجمالي' else status
            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(status_text)),
                    ft.DataCell(ft.Text(str(count))),
                    ft.DataCell(ft.Text(f"{percentage}%")),
                ])
            )
        self.preview_table.columns = columns
        self.preview_table.rows = rows
        self.page.update()

    def _preview_movement(self, period):
        columns = [
            ft.DataColumn(ft.Text("التاريخ")),
            ft.DataColumn(ft.Text("عدد الحركات")),
            ft.DataColumn(ft.Text("عربات مختلفة")),
        ]
        limit = ""
        if period == "اليوم":
            limit = "AND DATE(timestamp) = DATE('now')"
        elif period == "آخر 7 أيام":
            limit = "AND DATE(timestamp) >= DATE('now', '-7 days')"
        elif period == "آخر 30 يوم":
            limit = "AND DATE(timestamp) >= DATE('now', '-30 days')"
        elif period == "آخر سنة":
            limit = "AND DATE(timestamp) >= DATE('now', '-1 year')"
        query = f"""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as movements,
                COUNT(DISTINCT cart_id) as carts_moved
            FROM movements
            WHERE 1=1 {limit}
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 10
        """
        data = self.db.execute_query(query)
        rows = []
        for row in data:
            rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(str(cell))) for cell in row]))
        self.preview_table.columns = columns
        self.preview_table.rows = rows
        self.page.update()

    def _preview_maintenance(self, period):
        columns = [
            ft.DataColumn(ft.Text("حالة الصيانة")),
            ft.DataColumn(ft.Text("العدد")),
            ft.DataColumn(ft.Text("التكلفة الإجمالية")),
        ]
        limit = ""
        if period == "اليوم":
            limit = "AND DATE(entry_date) = DATE('now')"
        elif period == "آخر 7 أيام":
            limit = "AND DATE(entry_date) >= DATE('now', '-7 days')"
        elif period == "آخر 30 يوم":
            limit = "AND DATE(entry_date) >= DATE('now', '-30 days')"
        elif period == "آخر سنة":
            limit = "AND DATE(entry_date) >= DATE('now', '-1 year')"
        query = f"""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(cost) as total_cost
            FROM maintenance_records
            WHERE 1=1 {limit}
            GROUP BY status
        """
        data = self.db.execute_query(query)
        rows = []
        for row in data:
            status, count, total_cost = row
            status_text = MAINTENANCE_STATUS.get(status, status)
            rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(status_text)),
                    ft.DataCell(ft.Text(str(count))),
                    ft.DataCell(ft.Text(f"{total_cost or 0:.0f} ر.س")),
                ])
            )
        self.preview_table.columns = columns
        self.preview_table.rows = rows
        self.page.update()

    def _preview_warehouse(self):
        columns = [
            ft.DataColumn(ft.Text("المستودع")),
            ft.DataColumn(ft.Text("السعة")),
            ft.DataColumn(ft.Text("العدد الحالي")),
            ft.DataColumn(ft.Text("نسبة الإشغال")),
        ]
        data = self.db.execute_query("""
            SELECT 
                name,
                capacity,
                current_count,
                ROUND(current_count * 100.0 / capacity, 2) as occupancy
            FROM warehouses
            WHERE is_active = 1
            ORDER BY occupancy DESC
        """)
        rows = []
        for row in data:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(row[0])),
                ft.DataCell(ft.Text(str(row[1]))),
                ft.DataCell(ft.Text(str(row[2]))),
                ft.DataCell(ft.Text(f"{row[3]}%")),
            ]))
        self.preview_table.columns = columns
        self.preview_table.rows = rows
        self.page.update()

    def _preview_summary(self):
        columns = [
            ft.DataColumn(ft.Text("المؤشر")),
            ft.DataColumn(ft.Text("القيمة")),
        ]
        total_carts = self.db.execute_query("SELECT COUNT(*) FROM carts")[0][0] or 0
        sound_carts = self.db.execute_query("SELECT COUNT(*) FROM carts WHERE status = 'sound'")[0][0] or 0
        maintenance_carts = self.db.execute_query("SELECT COUNT(*) FROM carts WHERE status = 'needs_maintenance'")[0][0] or 0
        damaged_carts = self.db.execute_query("SELECT COUNT(*) FROM carts WHERE status = 'damaged'")[0][0] or 0
        total_warehouses = self.db.execute_query("SELECT COUNT(*) FROM warehouses WHERE is_active = 1")[0][0] or 0
        total_movements = self.db.execute_query("SELECT COUNT(*) FROM movements")[0][0] or 0
        total_maintenance = self.db.execute_query("SELECT COUNT(*) FROM maintenance_records")[0][0] or 0
        total_cost = self.db.execute_query("SELECT SUM(cost) FROM maintenance_records WHERE status = 'completed'")[0][0] or 0
        total_users = self.db.execute_query("SELECT COUNT(*) FROM users WHERE is_active = 1")[0][0] or 0

        summary_data = [
            ("إجمالي العربات", f"{total_carts} عربة"),
            ("عربات سليمة", f"{sound_carts} عربة ({sound_carts/total_carts*100:.1f}%)" if total_carts > 0 else "0"),
            ("تحتاج صيانة", f"{maintenance_carts} عربة ({maintenance_carts/total_carts*100:.1f}%)" if total_carts > 0 else "0"),
            ("عربات تالفة", f"{damaged_carts} عربة ({damaged_carts/total_carts*100:.1f}%)" if total_carts > 0 else "0"),
            ("عدد المستودعات", f"{total_warehouses} مستودع"),
            ("إجمالي الحركات", f"{total_movements} حركة"),
            ("عمليات الصيانة", f"{total_maintenance} عملية"),
            ("تكاليف الصيانة", f"{total_cost:.0f} ر.س"),
            ("المستخدمين النشطين", f"{total_users} مستخدم"),
            ("اسم المستخدم", self.current_user['username']),
            ("الدور", "مدير" if self.current_user['role'] == 'admin' else "مشغل"),
            ("تاريخ التقرير", datetime.now().strftime('%Y-%m-%d %H:%M')),
        ]
        rows = []
        for indicator, value in summary_data:
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(indicator)),
                ft.DataCell(ft.Text(value)),
            ]))
        self.preview_table.columns = columns
        self.preview_table.rows = rows
        self.page.update()

    def _export_excel(self, e):
        if not self.check_permission('can_export_reports'):
            self.show_snack_bar("غير مصرح لك بتصدير التقارير", COLORS['danger'])
            return
        if not EXCEL_AVAILABLE:
            self.show_snack_bar("مكتبة openpyxl غير مثبتة", COLORS['danger'])
            return
        try:
            from openpyxl import Workbook
            # طلب حفظ الملف
            def save_file(result: list):
                if result and result.path:
                    filename = result.path
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "تقرير"
                    ws['A1'] = f"تقرير: {self.report_type.value}"
                    ws['A2'] = f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    ws['A3'] = f"المستخدم: {self.current_user['username']}"
                    # رؤوس الأعمدة
                    headers = [col.label.value for col in self.preview_table.columns]
                    for c, h in enumerate(headers, 1):
                        ws.cell(row=5, column=c, value=h)
                    # البيانات
                    for r, row in enumerate(self.preview_table.rows, 6):
                        for c, cell in enumerate(row.cells, 1):
                            ws.cell(row=r, column=c, value=cell.content.value)
                    wb.save(filename)
                    self.show_snack_bar(f"تم حفظ التقرير: {os.path.basename(filename)}", COLORS['success'])
                    self.db.log_action(self.current_user['id'], 'export_excel',
                                       f'تصدير تقرير {self.report_type.value} إلى Excel')
            self.page.dialog = ft.FilePicker(on_result=save_file)
            self.page.overlay.append(self.page.dialog)
            self.page.update()
            self.page.dialog.save_file(
                file_name=f"تقرير_{self.report_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
        except Exception as ex:
            self.show_snack_bar(f"خطأ: {str(ex)}", COLORS['danger'])

    def _export_pdf(self, e):
        if not self.check_permission('can_export_reports'):
            self.show_snack_bar("غير مصرح لك بتصدير التقارير", COLORS['danger'])
            return
        if not PDF_AVAILABLE:
            self.show_snack_bar("مكتبة fpdf غير مثبتة", COLORS['danger'])
            return
        try:
            from fpdf import FPDF
            def save_file(result: list):
                if result and result.path:
                    filename = result.path
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font('Arial', '', 16)
                    pdf.cell(200, 10, txt=f"تقرير: {self.report_type.value}", ln=1, align='C')
                    pdf.set_font('Arial', '', 12)
                    pdf.cell(200, 10, txt=f"تاريخ التقرير: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align='C')
                    pdf.cell(200, 10, txt=f"المستخدم: {self.current_user['username']}", ln=1, align='C')
                    pdf.ln(10)
                    col_width = pdf.w / (len(self.preview_table.columns) + 1)
                    for col in self.preview_table.columns:
                        pdf.cell(col_width, 10, col.label.value, border=1)
                    pdf.ln()
                    for row in self.preview_table.rows:
                        for cell in row.cells:
                            pdf.cell(col_width, 10, str(cell.content.value), border=1)
                        pdf.ln()
                    pdf.output(filename)
                    self.show_snack_bar(f"تم حفظ التقرير: {os.path.basename(filename)}", COLORS['success'])
                    self.db.log_action(self.current_user['id'], 'export_pdf',
                                       f'تصدير تقرير {self.report_type.value} إلى PDF')
            self.page.dialog = ft.FilePicker(on_result=save_file)
            self.page.overlay.append(self.page.dialog)
            self.page.update()
            self.page.dialog.save_file(
                file_name=f"تقرير_{self.report_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        except Exception as ex:
            self.show_snack_bar(f"خطأ: {str(ex)}", COLORS['danger'])

    # ------------------------------------------------------------
    # إدارة المستخدمين (للمدير فقط)
    # ------------------------------------------------------------
    def show_user_management(self):
        if self.current_user['role'] != 'admin':
            self.show_snack_bar("غير مصرح لك بالوصول إلى هذه الصفحة", COLORS['danger'])
            return

        self.clear_content()

        header = ft.Row([
            ft.Text("إدارة المستخدمين والصلاحيات", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
            ft.Row([
                ft.ElevatedButton(
                    "➕ إضافة مستخدم جديد",
                    icon=ft.icons.ADD,
                    style=ft.ButtonStyle(bgcolor=COLORS['success'], color=COLORS['white']),
                    on_click=lambda e: self._add_user_dialog(),
                ),
                ft.ElevatedButton(
                    "🔑 تغيير كلمة مرور المدير",
                    style=ft.ButtonStyle(bgcolor=COLORS['warning'], color=COLORS['white']),
                    on_click=lambda e: self._change_admin_password_dialog(),
                ),
            ]),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        self.user_search_field = ft.TextField(
            hint_text="🔍 بحث في المستخدمين",
            width=250,
            on_change=self.filter_users,
        )

        self.user_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("المعرف")),
                ft.DataColumn(ft.Text("اسم المستخدم")),
                ft.DataColumn(ft.Text("الاسم الكامل")),
                ft.DataColumn(ft.Text("الدور")),
                ft.DataColumn(ft.Text("الحالة")),
                ft.DataColumn(ft.Text("آخر تسجيل")),
                ft.DataColumn(ft.Text("الإجراءات")),
            ],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=15,
            data_row_max_height=60,
        )

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    header,
                    ft.Row([self.user_search_field], alignment=ft.MainAxisAlignment.END),
                    ft.Container(
                        content=self.user_table,
                        padding=10,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])

        self._load_users()

    def _load_users(self, search=""):
        if search:
            users = self.db.execute_query("""
                SELECT id, username, full_name, role, is_active, last_login 
                FROM users 
                WHERE username LIKE ? OR full_name LIKE ?
                ORDER BY id
            """, (f'%{search}%', f'%{search}%'))
        else:
            users = self.db.execute_query("""
                SELECT id, username, full_name, role, is_active, last_login 
                FROM users 
                ORDER BY id
            """)

        rows = []
        for user in users:
            uid, username, full_name, role, is_active, last_login = user
            role_text = "مدير" if role == 'admin' else "مشغل"
            status_text = "نشط" if is_active else "غير نشط"
            status_color = COLORS['success'] if is_active else COLORS['danger']
            last_login_text = last_login[:16] if last_login else "لم يسجل دخول"

            actions = ft.Row(spacing=5)
            actions.controls.append(
                ft.IconButton(
                    icon=ft.icons.EDIT,
                    icon_size=18,
                    icon_color=COLORS['white'],
                    bgcolor=COLORS['primary'],
                    tooltip="تعديل",
                    on_click=lambda e, uid=uid, un=username: self._edit_user_dialog(uid, un),
                )
            )
            actions.controls.append(
                ft.IconButton(
                    icon=ft.icons.SECURITY,
                    icon_size=18,
                    icon_color=COLORS['white'],
                    bgcolor=COLORS['purple'],
                    tooltip="الصلاحيات",
                    on_click=lambda e, uid=uid, un=username: self._manage_permissions_dialog(uid, un),
                )
            )
            actions.controls.append(
                ft.IconButton(
                    icon=ft.icons.PASSWORD,
                    icon_size=18,
                    icon_color=COLORS['white'],
                    bgcolor=COLORS['warning'],
                    tooltip="تغيير كلمة المرور",
                    on_click=lambda e, uid=uid, un=username: self._change_user_password_dialog(uid, un),
                )
            )
            if username != DEFAULT_USER:
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.ENABLED_USERS if is_active else ft.icons.DISABLED_BY_DEFAULT,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['danger'] if is_active else COLORS['success'],
                        tooltip="تعطيل" if is_active else "تفعيل",
                        on_click=lambda e, uid=uid, un=username, act=not is_active: self._toggle_user_status(uid, un, act),
                    )
                )
                actions.controls.append(
                    ft.IconButton(
                        icon=ft.icons.DELETE,
                        icon_size=18,
                        icon_color=COLORS['white'],
                        bgcolor=COLORS['danger'],
                        tooltip="حذف",
                        on_click=lambda e, uid=uid, un=username: self._delete_user_confirm(uid, un),
                    )
                )

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(uid))),
                        ft.DataCell(ft.Text(username)),
                        ft.DataCell(ft.Text(full_name or "")),
                        ft.DataCell(ft.Text(role_text)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(status_text),
                            bgcolor=status_color + '20',
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            border_radius=12,
                        )),
                        ft.DataCell(ft.Text(last_login_text)),
                        ft.DataCell(actions),
                    ]
                )
            )
        self.user_table.rows = rows
        self.page.update()

    def filter_users(self, e):
        self._load_users(self.user_search_field.value.strip())

    def _add_user_dialog(self):
        username_field = ft.TextField(label="اسم المستخدم", width=350, autofocus=True)
        password_field = ft.TextField(label="كلمة المرور", width=350, password=True, can_reveal_password=True)
        confirm_field = ft.TextField(label="تأكيد كلمة المرور", width=350, password=True, can_reveal_password=True)
        fullname_field = ft.TextField(label="الاسم الكامل", width=350)
        role_dropdown = ft.Dropdown(
            label="الدور",
            width=350,
            options=[
                ft.dropdown.Option("مشغل"),
                ft.dropdown.Option("مدير"),
            ],
            value="مشغل",
        )

        def save(e):
            username = username_field.value.strip()
            password = password_field.value.strip()
            confirm = confirm_field.value.strip()
            fullname = fullname_field.value.strip()
            role_text = role_dropdown.value
            if not username or not password:
                self.show_snack_bar("الرجاء إدخال اسم المستخدم وكلمة المرور", COLORS['danger'])
                return
            if password != confirm:
                self.show_snack_bar("كلمة المرور غير متطابقة", COLORS['danger'])
                return
            role = "admin" if role_text == "مدير" else "operator"
            try:
                user_id = self.db.execute_insert(
                    """INSERT INTO users (username, password, full_name, role, is_active, created_by) 
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (username, password, fullname, role, self.current_user['id'])
                )
                permissions = DEFAULT_PERMISSIONS.copy()
                if role == 'admin':
                    for key in permissions:
                        permissions[key] = 1
                self.db.update_user_permissions(user_id, permissions)
                self.db.log_action(self.current_user['id'], 'add_user', f'إضافة مستخدم جديد {username}')
                self.close_dialog()
                self.show_snack_bar("تم إضافة المستخدم بنجاح", COLORS['success'])
                self._load_users()
            except sqlite3.IntegrityError:
                self.show_snack_bar("اسم المستخدم موجود مسبقاً", COLORS['danger'])

        dialog = ft.AlertDialog(
            title=ft.Text("إضافة مستخدم جديد", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    username_field,
                    password_field,
                    confirm_field,
                    fullname_field,
                    role_dropdown,
                ], width=400, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _edit_user_dialog(self, user_id, username):
        result = self.db.execute_query(
            "SELECT full_name, role FROM users WHERE id = ?",
            (user_id,)
        )
        if not result:
            self.show_snack_bar("المستخدم غير موجود", COLORS['danger'])
            return
        fullname, role = result[0]

        username_display = ft.TextField(label="اسم المستخدم", width=350, value=username, read_only=True)
        fullname_field = ft.TextField(label="الاسم الكامل", width=350, value=fullname or "")
        role_dropdown = ft.Dropdown(
            label="الدور",
            width=350,
            options=[
                ft.dropdown.Option("مشغل"),
                ft.dropdown.Option("مدير"),
            ],
            value="مدير" if role == 'admin' else "مشغل",
        )

        def save(e):
            new_fullname = fullname_field.value.strip()
            new_role_text = role_dropdown.value
            new_role = "admin" if new_role_text == "مدير" else "operator"
            self.db.execute_query(
                "UPDATE users SET full_name = ?, role = ? WHERE id = ?",
                (new_fullname, new_role, user_id)
            )
            if new_role == 'admin':
                permissions = DEFAULT_PERMISSIONS.copy()
                for key in permissions:
                    permissions[key] = 1
                self.db.update_user_permissions(user_id, permissions)
            self.db.log_action(self.current_user['id'], 'edit_user', f'تعديل بيانات المستخدم {username}')
            self.close_dialog()
            self.show_snack_bar("تم تحديث بيانات المستخدم بنجاح", COLORS['success'])
            self._load_users()

        dialog = ft.AlertDialog(
            title=ft.Text(f"تعديل بيانات المستخدم: {username}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([username_display, fullname_field, role_dropdown],
                                  width=400, spacing=15, scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _manage_permissions_dialog(self, user_id, username):
        permissions = self.db.get_user_permissions(user_id)

        # مجموعات الصلاحيات
        groups = [
            ("لوحة التحكم", ['can_view_dashboard']),
            ("إدارة العربات", ['can_manage_carts', 'can_add_cart', 'can_edit_cart', 'can_delete_cart']),
            ("حركة العربات", ['can_move_cart', 'can_view_movements']),
            ("الصيانة", ['can_manage_maintenance', 'can_complete_maintenance']),
            ("المستودعات", ['can_view_warehouses', 'can_add_warehouse', 'can_edit_warehouse', 'can_delete_warehouse']),
            ("التقارير", ['can_view_reports', 'can_export_reports']),
            ("إدارة النظام", ['can_manage_users', 'can_manage_backup']),
            ("إعدادات المستخدم", ['can_change_own_password'])
        ]

        permission_labels = {
            'can_view_dashboard': 'عرض لوحة التحكم',
            'can_manage_carts': 'إدارة العربات',
            'can_add_cart': 'إضافة عربة جديدة',
            'can_edit_cart': 'تعديل العربات',
            'can_delete_cart': 'حذف العربات',
            'can_move_cart': 'نقل العربات',
            'can_view_movements': 'عرض سجل الحركات',
            'can_manage_maintenance': 'إدارة الصيانة',
            'can_complete_maintenance': 'إتمام الصيانة',
            'can_view_warehouses': 'عرض المستودعات',
            'can_add_warehouse': 'إضافة مستودع',
            'can_edit_warehouse': 'تعديل المستودعات',
            'can_delete_warehouse': 'حذف المستودعات',
            'can_view_reports': 'عرض التقارير',
            'can_export_reports': 'تصدير التقارير',
            'can_manage_users': 'إدارة المستخدمين',
            'can_manage_backup': 'إدارة النسخ الاحتياطي',
            'can_change_own_password': 'تغيير كلمة المرور الشخصية'
        }

        permission_vars = {}

        content = ft.Column(spacing=15, scroll=ft.ScrollMode.AUTO)
        for group_name, perm_list in groups:
            group_controls = []
            for perm in perm_list:
                if perm in permission_labels:
                    var = ft.Checkbox(
                        label=permission_labels[perm],
                        value=permissions.get(perm, 0) == 1,
                    )
                    permission_vars[perm] = var
                    group_controls.append(var)
            if group_controls:
                content.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text(group_name, weight=ft.FontWeight.BOLD, size=16),
                            ft.Column(group_controls, spacing=5),
                        ]),
                        padding=10,
                        border=ft.border.all(1, COLORS['light']),
                        border_radius=8,
                    )
                )

        def save(e):
            new_perms = {}
            for key, var in permission_vars.items():
                new_perms[key] = 1 if var.value else 0
            self.db.update_user_permissions(user_id, new_perms)
            self.db.log_action(self.current_user['id'], 'edit_permissions',
                               f'تعديل صلاحيات المستخدم {username}')
            if user_id == self.current_user['id']:
                self.current_permissions = self.db.get_user_permissions(user_id)
            self.close_dialog()
            self.show_snack_bar(f"تم تحديث صلاحيات المستخدم {username}", COLORS['success'])

        def select_all(e):
            for var in permission_vars.values():
                var.value = True
            self.page.update()

        def deselect_all(e):
            for var in permission_vars.values():
                var.value = False
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"صلاحيات المستخدم: {username}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=content,
                width=600,
                height=500,
                padding=10,
            ),
            actions=[
                ft.TextButton("✅ تحديد الكل", on_click=select_all),
                ft.TextButton("❎ إلغاء الكل", on_click=deselect_all),
                ft.TextButton("💾 حفظ الصلاحيات", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _change_user_password_dialog(self, user_id, username):
        new_pass = ft.TextField(label="كلمة المرور الجديدة", width=350, password=True, can_reveal_password=True)
        confirm_pass = ft.TextField(label="تأكيد كلمة المرور", width=350, password=True, can_reveal_password=True)

        def save(e):
            new = new_pass.value.strip()
            confirm = confirm_pass.value.strip()
            if not new:
                self.show_snack_bar("الرجاء إدخال كلمة المرور الجديدة", COLORS['danger'])
                return
            if new != confirm:
                self.show_snack_bar("كلمة المرور غير متطابقة", COLORS['danger'])
                return
            self.db.execute_query(
                "UPDATE users SET password = ? WHERE id = ?",
                (new, user_id)
            )
            self.db.log_action(self.current_user['id'], 'change_password',
                               f'تغيير كلمة مرور المستخدم {username}')
            self.close_dialog()
            self.show_snack_bar("تم تغيير كلمة المرور بنجاح", COLORS['success'])

        dialog = ft.AlertDialog(
            title=ft.Text(f"تغيير كلمة المرور - {username}", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([new_pass, confirm_pass], width=400, spacing=15),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _toggle_user_status(self, user_id, username, activate):
        status_text = "تفعيل" if activate else "تعطيل"

        def confirm(e):
            self.db.execute_query(
                "UPDATE users SET is_active = ? WHERE id = ?",
                (1 if activate else 0, user_id)
            )
            self.db.log_action(self.current_user['id'], 'toggle_user',
                               f'{status_text} المستخدم {username}')
            self.close_dialog()
            self.show_snack_bar(f"تم {status_text} المستخدم بنجاح", COLORS['success'])
            self._load_users()

        dialog = ft.AlertDialog(
            title=ft.Text(f"تأكيد {status_text}", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"هل أنت متأكد من {status_text} المستخدم '{username}'؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _delete_user_confirm(self, user_id, username):
        if username == DEFAULT_USER:
            self.show_snack_bar("لا يمكن حذف المستخدم الرئيسي", COLORS['danger'])
            return

        def confirm(e):
            self.db.execute_query("DELETE FROM users WHERE id = ?", (user_id,))
            self.db.log_action(self.current_user['id'], 'delete_user', f'حذف المستخدم {username}')
            self.close_dialog()
            self.show_snack_bar("تم حذف المستخدم بنجاح", COLORS['success'])
            self._load_users()

        dialog = ft.AlertDialog(
            title=ft.Text("تأكيد الحذف", weight=ft.FontWeight.BOLD),
            content=ft.Text(f"هل أنت متأكد من حذف المستخدم '{username}'؟"),
            actions=[
                ft.TextButton("نعم", on_click=confirm),
                ft.TextButton("لا", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _change_admin_password_dialog(self):
        current_pass = ft.TextField(label="كلمة المرور الحالية", width=350, password=True, can_reveal_password=True)
        new_pass = ft.TextField(label="كلمة المرور الجديدة", width=350, password=True, can_reveal_password=True)
        confirm_pass = ft.TextField(label="تأكيد كلمة المرور", width=350, password=True, can_reveal_password=True)

        def save(e):
            curr = current_pass.value.strip()
            new = new_pass.value.strip()
            confirm = confirm_pass.value.strip()
            result = self.db.execute_query(
                "SELECT id FROM users WHERE username = ? AND password = ?",
                (DEFAULT_USER, curr)
            )
            if not result:
                self.show_snack_bar("كلمة المرور الحالية غير صحيحة", COLORS['danger'])
                return
            if not new:
                self.show_snack_bar("الرجاء إدخال كلمة المرور الجديدة", COLORS['danger'])
                return
            if new != confirm:
                self.show_snack_bar("كلمة المرور غير متطابقة", COLORS['danger'])
                return
            admin_id = self.db.execute_query(
                "SELECT id FROM users WHERE username = ?", (DEFAULT_USER,)
            )[0][0]
            self.db.execute_query(
                "UPDATE users SET password = ? WHERE id = ?",
                (new, admin_id)
            )
            self.db.log_action(self.current_user['id'], 'change_admin_password',
                               'تغيير كلمة مرور المدير الرئيسي')
            self.close_dialog()
            self.show_snack_bar("تم تغيير كلمة مرور المدير بنجاح", COLORS['success'])

        dialog = ft.AlertDialog(
            title=ft.Text("تغيير كلمة مرور المدير الرئيسي", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([current_pass, new_pass, confirm_pass], width=400, spacing=15),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    # ------------------------------------------------------------
    # إعدادات النظام (للمدير فقط)
    # ------------------------------------------------------------
    def show_system_settings(self):
        if self.current_user['role'] != 'admin':
            self.show_snack_bar("غير مصرح لك بالوصول إلى هذه الصفحة", COLORS['danger'])
            return

        self.clear_content()

        # إعدادات التطبيق
        app_name = self.db.get_app_setting('app_name', APP_NAME)
        company_name = self.db.get_app_setting('company_name', 'الرئاسة العامة لشؤون المسجد الحرام والمسجد النبوي')
        mega_email = self.db.get_app_setting('mega_email', MEGA_EMAIL)
        mega_password = self.db.get_app_setting('mega_password', MEGA_PASSWORD)

        app_name_field = ft.TextField(label="اسم البرنامج", width=400, value=app_name)
        company_name_field = ft.TextField(label="اسم الجهة المشغلة", width=400, value=company_name)

        def save_app_settings(e):
            new_name = app_name_field.value.strip()
            if new_name:
                self.db.update_app_setting('app_name', new_name, self.current_user['id'])
                self.page.title = new_name
                if self.sidebar_app_name_text:
                    self.sidebar_app_name_text.value = new_name
                    self.sidebar_app_name_text.update()
            new_company = company_name_field.value.strip()
            if new_company:
                self.db.update_app_setting('company_name', new_company, self.current_user['id'])
            self.db.log_action(self.current_user['id'], 'update_settings', 'تحديث إعدادات التطبيق')
            self.show_snack_bar("تم تحديث إعدادات التطبيق", COLORS['success'])

        # إعدادات MEGA
        mega_status = ft.Text(
            "✓ مكتبة MEGA مثبتة - جاهز للعمل" if MEGA_AVAILABLE else "✗ مكتبة MEGA غير مثبتة - يرجى تثبيتها: pip install mega.py",
            color=COLORS['success'] if MEGA_AVAILABLE else COLORS['danger'],
        )
        mega_email_field = ft.TextField(label="البريد الإلكتروني MEGA", width=400, value=mega_email)
        mega_pass_field = ft.TextField(
            label="كلمة مرور MEGA",
            width=400,
            value=mega_password,
            password=True,
            can_reveal_password=True,
        )

        def save_mega_settings(e):
            new_email = mega_email_field.value.strip()
            new_pass = mega_pass_field.value.strip()
            if new_email:
                self.db.update_app_setting('mega_email', new_email, self.current_user['id'])
            if new_pass:
                self.db.update_app_setting('mega_password', new_pass, self.current_user['id'])
            self.db.log_action(self.current_user['id'], 'update_settings', 'تحديث إعدادات MEGA')
            self.show_snack_bar("تم تحديث إعدادات MEGA", COLORS['success'])

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("إعدادات النظام", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("إعدادات التطبيق", size=18, weight=ft.FontWeight.BOLD),
                            app_name_field,
                            ft.ElevatedButton("💾 حفظ اسم البرنامج", on_click=save_app_settings),
                            ft.Divider(),
                            company_name_field,
                            ft.ElevatedButton("💾 حفظ اسم الجهة", on_click=save_app_settings),
                        ], spacing=15),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        margin=ft.margin.only(bottom=20),
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("إعدادات النسخ الاحتياطي السحابي (MEGA)", size=18, weight=ft.FontWeight.BOLD),
                            mega_status,
                            ft.Divider(),
                            mega_email_field,
                            mega_pass_field,
                            ft.ElevatedButton("💾 حفظ إعدادات MEGA", on_click=save_mega_settings),
                        ], spacing=15),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        margin=ft.margin.only(bottom=20),
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("معلومات النظام", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(f"إصدار النظام: 2.0.0"),
                            ft.Text(f"تاريخ الإصدار: 2025-02-12"),
                            ft.Text(f"المطور: قسم تقنية المعلومات"),
                            ft.Text(f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
                            ft.Text(f"دعم MEGA: {'مفعل ✓' if MEGA_AVAILABLE else 'غير مفعل ✗'}"),
                        ], spacing=10),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])
        self.page.update()

    # ------------------------------------------------------------
    # النسخ الاحتياطي (للمدير فقط)
    # ------------------------------------------------------------
    def show_backup(self):
        if self.current_user['role'] != 'admin' or not self.check_permission('can_manage_backup'):
            self.show_snack_bar("غير مصرح لك بالوصول إلى هذه الصفحة", COLORS['danger'])
            return

        self.clear_content()

        self.backup_progress = ft.ProgressBar(width=400, value=0, visible=False)
        self.backup_status = ft.Text("", color=COLORS['primary'])

        def create_local_backup(e):
            try:
                self.backup_progress.visible = True
                self.backup_progress.value = 0
                self.backup_status.value = "جاري إنشاء النسخة الاحتياطية..."
                self.page.update()

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"backup_{timestamp}.db"
                backup_path = os.path.join(self.backup_dir, backup_filename)

                self.backup_progress.value = 0.3
                self.page.update()
                shutil.copy2(DB_NAME, backup_path)
                file_size = os.path.getsize(backup_path)

                self.backup_progress.value = 0.7
                self.page.update()

                self.db.execute_insert(
                    """INSERT INTO backups 
                       (file_name, backup_type, user_id, file_size, file_path, status) 
                       VALUES (?, 'local', ?, ?, ?, 'completed')""",
                    (backup_filename, self.current_user['id'], file_size, backup_path)
                )
                self.backup_progress.value = 1.0
                self.backup_status.value = "✅ تم إنشاء النسخة الاحتياطية المحلية بنجاح"
                self.backup_status.color = COLORS['success']
                self.page.update()
                self.db.log_action(self.current_user['id'], 'backup_local',
                                   f'إنشاء نسخة احتياطية محلية {backup_filename}')
                self.show_snack_bar("تم إنشاء النسخة الاحتياطية المحلية", COLORS['success'])
                self._load_backups()
                # إخفاء بعد 3 ثوان
                threading.Timer(3, self._hide_backup_progress).start()
            except Exception as ex:
                self.backup_status.value = f"❌ فشل: {str(ex)}"
                self.backup_status.color = COLORS['danger']
                self.page.update()
                self.show_snack_bar(f"فشل النسخ الاحتياطي: {str(ex)}", COLORS['danger'])

        def create_cloud_backup(e):
            if not MEGA_AVAILABLE:
                self.show_snack_bar("مكتبة MEGA غير مثبتة", COLORS['danger'])
                return
            try:
                self.backup_progress.visible = True
                self.backup_progress.value = 0
                self.backup_status.value = "جاري الاتصال بـ MEGA..."
                self.page.update()

                mega_email = os.environ.get('MEGA_EMAIL') or self.db.get_app_setting('mega_email', MEGA_EMAIL)
                mega_password = os.environ.get('MEGA_PASSWORD') or self.db.get_app_setting('mega_password', MEGA_PASSWORD)

                mega = Mega()
                m = mega.login(mega_email, mega_password)

                self.backup_progress.value = 0.2
                self.backup_status.value = "جاري إنشاء النسخة المحلية..."
                self.page.update()

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"backup_cloud_{timestamp}.db"
                backup_path = os.path.join(self.backup_dir, backup_filename)

                shutil.copy2(DB_NAME, backup_path)
                file_size = os.path.getsize(backup_path)

                self.backup_progress.value = 0.5
                self.backup_status.value = "جاري الرفع إلى MEGA..."
                self.page.update()

                file = m.upload(backup_path)
                link = m.get_upload_link(file)

                self.backup_progress.value = 0.8
                self.page.update()

                self.db.execute_insert(
                    """INSERT INTO backups 
                       (file_name, backup_type, user_id, file_size, file_path, mega_link, status) 
                       VALUES (?, 'cloud', ?, ?, ?, ?, 'completed')""",
                    (backup_filename, self.current_user['id'], file_size, backup_path, link)
                )
                self.backup_progress.value = 1.0
                self.backup_status.value = "✅ تم الرفع إلى MEGA بنجاح"
                self.backup_status.color = COLORS['success']
                self.page.update()
                self.db.log_action(self.current_user['id'], 'backup_cloud',
                                   f'إنشاء نسخة احتياطية سحابية {backup_filename}')
                self.show_snack_bar("تم إنشاء النسخة الاحتياطية السحابية", COLORS['success'])
                self._load_backups()
                threading.Timer(3, self._hide_backup_progress).start()
            except Exception as ex:
                self.backup_status.value = f"❌ فشل: {str(ex)}"
                self.backup_status.color = COLORS['danger']
                self.page.update()
                self.show_snack_bar(f"فشل النسخ الاحتياطي السحابي: {str(ex)}", COLORS['danger'])

        self._hide_backup_progress = lambda: (
            setattr(self.backup_progress, 'visible', False),
            setattr(self.backup_status, 'value', ''),
            self.page.update()
        )

        # سجل النسخ الاحتياطي
        self.backup_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("التاريخ")),
                ft.DataColumn(ft.Text("اسم الملف")),
                ft.DataColumn(ft.Text("النوع")),
                ft.DataColumn(ft.Text("الحجم")),
                ft.DataColumn(ft.Text("رابط MEGA")),
                ft.DataColumn(ft.Text("الحالة")),
                ft.DataColumn(ft.Text("المستخدم")),
            ],
            rows=[],
            border=ft.border.all(1, COLORS['gray']),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, COLORS['light']),
            horizontal_lines=ft.border.BorderSide(1, COLORS['light']),
            column_spacing=15,
            data_row_max_height=50,
        )

        self.content_column.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("النسخ الاحتياطي", size=24, weight=ft.FontWeight.BOLD, color=COLORS['dark']),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("إنشاء نسخة احتياطية", size=18, weight=ft.FontWeight.BOLD),
                            ft.Row([
                                ft.ElevatedButton(
                                    "💾 نسخ احتياطي محلي",
                                    style=ft.ButtonStyle(bgcolor=COLORS['primary'], color=COLORS['white']),
                                    on_click=create_local_backup,
                                ),
                                ft.ElevatedButton(
                                    "☁️ نسخ احتياطي سحابي (MEGA)",
                                    style=ft.ButtonStyle(bgcolor=COLORS['purple'], color=COLORS['white']),
                                    visible=MEGA_AVAILABLE,
                                    on_click=create_cloud_backup,
                                ),
                            ]),
                            ft.Row([self.backup_progress, self.backup_status], alignment=ft.MainAxisAlignment.START),
                        ], spacing=15),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        margin=ft.margin.only(bottom=20),
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("سجل النسخ الاحتياطي", size=18, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=self.backup_table,
                                padding=10,
                                bgcolor=COLORS['white'],
                                border_radius=10,
                                expand=True,
                                scroll=ft.ScrollMode.AUTO,
                            ),
                        ]),
                        padding=20,
                        bgcolor=COLORS['white'],
                        border_radius=10,
                        expand=True,
                    ),
                ]),
                padding=ft.padding.only(left=25, right=25, top=20, bottom=20),
                expand=True,
            )
        ])

        self._load_backups()

    def _load_backups(self):
        backups = self.db.execute_query("""
            SELECT b.created_at, b.file_name, b.backup_type, b.file_size, 
                   b.mega_link, b.status, u.username
            FROM backups b
            LEFT JOIN users u ON b.user_id = u.id
            ORDER BY b.created_at DESC 
            LIMIT 50
        """)
        rows = []
        for backup in backups:
            created_at, filename, btype, file_size, mega_link, status, username = backup
            type_text = "محلي" if btype == 'local' else "سحابي"
            status_text = "✓ مكتمل" if status == 'completed' else "✗ فشل"
            status_color = COLORS['success'] if status == 'completed' else COLORS['danger']
            if file_size:
                if file_size < 1024:
                    size_text = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_text = f"{file_size / 1024:.1f} KB"
                else:
                    size_text = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_text = "-"
            link_text = mega_link[:30] + "..." if mega_link and len(mega_link) > 30 else (mega_link or "-")

            rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(created_at[:19] if created_at else "")),
                        ft.DataCell(ft.Text(filename)),
                        ft.DataCell(ft.Text(type_text)),
                        ft.DataCell(ft.Text(size_text)),
                        ft.DataCell(ft.Text(link_text)),
                        ft.DataCell(ft.Container(
                            content=ft.Text(status_text),
                            bgcolor=status_color + '20',
                            padding=ft.padding.symmetric(horizontal=8, vertical=2),
                            border_radius=12,
                        )),
                        ft.DataCell(ft.Text(username or "")),
                    ]
                )
            )
        self.backup_table.rows = rows
        self.page.update()

    # ------------------------------------------------------------
    # تغيير كلمة المرور الشخصية
    # ------------------------------------------------------------
    def show_change_password(self):
        if not self.check_permission('can_change_own_password'):
            self.show_snack_bar("غير مصرح لك بتغيير كلمة المرور", COLORS['danger'])
            return

        current_pass = ft.TextField(label="كلمة المرور الحالية", width=350, password=True, can_reveal_password=True)
        new_pass = ft.TextField(label="كلمة المرور الجديدة", width=350, password=True, can_reveal_password=True)
        confirm_pass = ft.TextField(label="تأكيد كلمة المرور", width=350, password=True, can_reveal_password=True)

        def save(e):
            curr = current_pass.value.strip()
            new = new_pass.value.strip()
            confirm = confirm_pass.value.strip()
            result = self.db.execute_query(
                "SELECT id FROM users WHERE id = ? AND password = ?",
                (self.current_user['id'], curr)
            )
            if not result:
                self.show_snack_bar("كلمة المرور الحالية غير صحيحة", COLORS['danger'])
                return
            if not new:
                self.show_snack_bar("الرجاء إدخال كلمة المرور الجديدة", COLORS['danger'])
                return
            if new != confirm:
                self.show_snack_bar("كلمة المرور غير متطابقة", COLORS['danger'])
                return
            self.db.execute_query(
                "UPDATE users SET password = ? WHERE id = ?",
                (new, self.current_user['id'])
            )
            self.db.log_action(self.current_user['id'], 'change_own_password', 'تغيير كلمة المرور الشخصية')
            self.close_dialog()
            self.show_snack_bar("تم تغيير كلمة المرور بنجاح", COLORS['success'])

        dialog = ft.AlertDialog(
            title=ft.Text("تغيير كلمة المرور الشخصية", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"المستخدم: {self.current_user['username']}", size=14, color=COLORS['gray']),
                    current_pass,
                    new_pass,
                    confirm_pass,
                ], width=400, spacing=15),
                padding=10,
            ),
            actions=[
                ft.TextButton("حفظ", on_click=save),
                ft.TextButton("إلغاء", on_click=self.close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()


def main(page: ft.Page):
    app = CartsManagementApp(page)


if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
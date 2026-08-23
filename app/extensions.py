from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
login_manager = LoginManager()
migrate = Migrate()
correo = Mail()

import os

from flask import Flask, render_template
from flask_security import Security, SQLAlchemyUserDatastore

from application.database import db
from application.models import Role, User
from application.permissions import init_principal

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SECURITY_PASSWORD_SALT"] = os.environ.get(
        "SECURITY_PASSWORD_SALT", "dev-salt-change-me"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
        BASE_DIR, "instance", "placement.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Flask-Security-Too behaviour
    app.config["SECURITY_REGISTERABLE"] = False  # we roll our own register routes per-role
    app.config["SECURITY_SEND_REGISTER_EMAIL"] = False
    app.config["SECURITY_TRACKABLE"] = False
    # JSON-only API for now (no server-rendered login form yet) — CSRF is
    # revisited once Flask-WTF forms are wired to real templates in later
    # milestones.
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECURITY_CSRF_PROTECT_MECHANISMS"] = []

    db.init_app(app)

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    app.security = Security(app, user_datastore)
    app.user_datastore = user_datastore

    init_principal(app)

    from application.auth_routes import auth_bp
    from application.protected_routes import protected_bp
    from application.admin_routes import register_admin_resources

    app.register_blueprint(auth_bp)
    app.register_blueprint(protected_bp)
    register_admin_resources(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
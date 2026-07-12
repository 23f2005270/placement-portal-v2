import os

from celery.signals import worker_process_init
from flask import Flask, render_template, send_from_directory
from flask_security import Security, SQLAlchemyUserDatastore

from application.database import db
from application.models import Role, User
from application.permissions import init_principal
from application.celery_app import celery as celery_app
from flask_cache import cache

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
    cache.init_app(app)

    user_datastore = SQLAlchemyUserDatastore(db, User, Role)
    app.security = Security(app, user_datastore)
    app.user_datastore = user_datastore

    init_principal(app)

    # Bind Flask application-context awareness onto the shared Celery
    # instance, so every task runs inside `with app.app_context()` and
    # can use `db`/models normally without each task re-deriving it.
    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    app.celery = celery_app

    from application.auth_routes import auth_bp
    from application.protected_routes import protected_bp
    from application.admin_routes import register_admin_resources
    from application.company_routes import register_company_resources
    from application.student_routes import register_student_resources, student_files_bp
    from application.task_routes import task_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(protected_bp)
    app.register_blueprint(student_files_bp)
    app.register_blueprint(task_bp)
    register_admin_resources(app)
    register_company_resources(app)
    register_student_resources(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/sw.js")
    def service_worker():
        # Served at the root path (not /static/sw.js) so the browser
        # grants it scope '/' by default, letting it control the whole
        # app instead of just the /static/ subtree.
        response = send_from_directory(app.static_folder, "sw.js")
        response.headers["Content-Type"] = "application/javascript"
        return response

    with app.app_context():
        db.create_all()

    return app


app = create_app()
# Module-level name so `celery -A app.celery worker` resolves correctly
# (Celery's -A flag imports module `app`, then looks up attribute `celery`).
celery = celery_app


@worker_process_init.connect
def _reinit_db_engine_in_worker_child(**kwargs):
    """
    Celery's default 'prefork' pool forks worker child processes, and
    those children inherit the parent's already-open SQLite connection.
    SQLite connections aren't safe to share across forked processes —
    reusing the inherited one causes hard-to-diagnose corruption
    (surfaces as things like a bare MemoryError). Disposing the engine
    here forces each child to open its own fresh connection on first use.
    """
    with app.app_context():
        db.engine.dispose()


if __name__ == "__main__":
    app.run(debug=True)
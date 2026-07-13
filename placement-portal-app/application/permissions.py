"""
Flask-Principal wiring. Defines one Permission per role and loads the
current user's RoleNeeds into the Identity on every request.
"""
from flask_principal import Permission, Principal, RoleNeed, UserNeed, identity_loaded

principal = Principal()

admin_permission = Permission(RoleNeed("admin"))
company_permission = Permission(RoleNeed("company"))
student_permission = Permission(RoleNeed("student"))


def init_principal(app):
    principal.init_app(app)

    @identity_loaded.connect_via(app)
    def on_identity_loaded(sender, identity):
        from flask_security import current_user

        identity.user = current_user

        if hasattr(current_user, "id") and current_user.is_authenticated:
            identity.provides.add(UserNeed(current_user.id))

            for role in current_user.roles:
                identity.provides.add(RoleNeed(role.name))


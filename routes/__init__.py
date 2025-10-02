def register_routes(app):
    from . import auth, visitantes, dashboard, ia, eventos, webhooks
    auth.register(app)
    visitantes.register(app)
    dashboard.register(app)
    ia.register(app)
    eventos.register(app)
    webhooks.register(app)


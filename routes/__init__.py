import logging

def register_routes(app):
    from . import auth, visitantes, dashboard, ia, eventos, webhooks, estatisticas

    logging.info("📌 Registrando rotas...")

    auth.register(app)
    logging.info("✅ Rotas auth registradas.")

    visitantes.register(app)
    logging.info("✅ Rotas visitantes registradas.")

    dashboard.register(app)
    logging.info("✅ Rotas dashboard registradas.")

    ia.register(app)
    logging.info("✅ Rotas ia registradas.")

    eventos.register(app)
    logging.info("✅ Rotas eventos registradas.")

    webhooks.register(app)
    logging.info("✅ Rotas webhooks registradas.")

    estatisticas.register(app)
    logging.info("✅ Rotas estatisticas registradas.")


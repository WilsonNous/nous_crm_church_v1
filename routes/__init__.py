import logging

def register_routes(app):
    from . import auth, visitantes, dashboard, ia, eventos, webhooks, estatisticas, app_monitor, app_monitor_resumo, agendamentos, membros

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

    app_monitor.register(app)
    logging.info("✅ Rotas monitor registradas.")

    app_monitor_resumo.register(app)
    logging.info("✅ Rotas resumo do monitor registradas.")

    agendamentos.register(app)
    logging.info("✅ Rotas agendamentos registradas.")

    membros.register(app)   # 👈 NOVO
    logging.info("✅ Rotas membros registradas.")





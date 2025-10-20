class Campanha(db.Model):
    __tablename__ = "campanhas"
    id = db.Column(db.Integer, primary_key=True)
    nome_evento = db.Column(db.String(120))
    mensagem = db.Column(db.Text)
    imagem = db.Column(db.String(255))
    criado_por = db.Column(db.String(80))
    data_envio = db.Column(db.DateTime)
    status = db.Column(db.String(30), default="pendente")
    enviados = db.Column(db.Integer, default=0)
    falhas = db.Column(db.Integer, default=0)


class EnvioWhatsApp(db.Model):
    __tablename__ = "envios_whatsapp"
    id = db.Column(db.Integer, primary_key=True)
    visitante_id = db.Column(db.Integer, db.ForeignKey("visitantes.id"))
    campanha_id = db.Column(db.Integer, db.ForeignKey("campanhas.id"))
    status = db.Column(db.String(30))
    data_envio = db.Column(db.DateTime)

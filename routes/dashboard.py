import logging
from flask import jsonify
from database import (
    obter_total_visitantes, obter_total_membros,
    obter_total_discipulados, obter_dados_genero
)

def register(app):
    @app.route('/api/get-dashboard-data', methods=['GET'])
    def get_dashboard_data():
        try:
            logging.info("📊 Iniciando dashboard...")
    
            logging.info("🔹 obtendo total visitantes...")
            total_visitantes = obter_total_visitantes()
    
            logging.info("🔹 obtendo total membros...")
            total_membros, homens_membros, mulheres_membros = obter_total_membros()
    
            logging.info("🔹 obtendo total discipulados...")
            discipulados, homens_discipulado, mulheres_discipulado = obter_total_discipulados()
    
            logging.info("🔹 obtendo dados de gênero...")
            dados_genero = obter_dados_genero()
    
            logging.info("✅ Dashboard carregado com sucesso")
    
            return jsonify({
                "totalVisitantes": total_visitantes,
                "totalMembros": total_membros,
                "totalhomensMembro": homens_membros,
                "totalmulheresMembro": mulheres_membros,
                "discipuladosAtivos": discipulados,
                "totalHomensDiscipulado": homens_discipulado,
                "totalMulheresDiscipulado": mulheres_discipulado,
                "grupos_comunhao": 0,
                **dados_genero
            }), 200
    
        except Exception as e:
            logging.exception(f"❌ Erro no get-dashboard-data: {e}")
            return jsonify({"error": str(e)}), 500

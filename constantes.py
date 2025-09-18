from enum import Enum

# --- Enum para os diferentes estados do visitante ---


class EstadoVisitante(Enum):
    INICIO = "INICIO"
    INTERESSE_DISCIPULADO = "INTERESSE_DISCIPULADO"
    INTERESSE_NOVO_COMEC = "INTERESSE_NOVO_COMEC"
    PEDIDO_ORACAO = "PEDIDO_ORACAO"
    HORARIOS = "HORARIOS"
    LINK_WHATSAPP = "LINK_WHATSAPP"
    OUTRO = "OUTRO"
    FIM = "FIM"


# --- Links ---
link_grupo = "https://chat.whatsapp.com/DSG6r3VScxS30hJAnitTkK"
link_discipulado = "https://forms.gle/qdxNnPyCfKoJeseU8"
link_discipulado_novosComec = "https://forms.gle/Cm7d5F9Zv77fgJKDA"
link_grupo_homens_corajosos = "https://chat.whatsapp.com/H4pFqtsruDr0QJ1NvCMjda"
link_grupo_transformadas = "https://chat.whatsapp.com/LT0pN2SPTqf66yt3AWKIAe"

# --- Mensagens associadas aos estados ---
mensagens = {
    EstadoVisitante.INICIO: """Escolha uma das opções:
1⃣ Sou batizado em águas, e quero me tornar membro.
2⃣ Não sou batizado, e quero me tornar membro.
3⃣ Gostaria de receber orações.
4⃣ Queria saber mais sobre os horários dos cultos.
5⃣ Quero entrar no grupo do WhatsApp da igreja.
6⃣ Outro assunto.""",
    EstadoVisitante.INTERESSE_DISCIPULADO: f"Que ótimo! Como você já foi batizado, você pode participar do nosso "
                                           f"Discipulado de Novos Membros. Aqui está o link para se inscrever: "
                                           f"{link_discipulado}. Estamos muito felizes com seu interesse em se tornar "
                                           f"parte da nossa família espiritual!",
    EstadoVisitante.INTERESSE_NOVO_COMEC: f"Ficamos felizes com o seu interesse! Como você ainda não foi batizado,"
                                          f" recomendamos que participe do nosso Discipulado Novo Começo, "
                                          f"onde você aprenderá mais sobre a fé e os próximos passos. "
                                          f"Aqui está o link para se inscrever: {link_discipulado_novosComec}. "
                                          f"Estamos à disposição para te ajudar nesse caminho!",
    EstadoVisitante.PEDIDO_ORACAO: "Ficamos honrados em receber o seu pedido de oração. "
                                   "Sinta-se à vontade para compartilhar o que está em seu coração. "
                                   "Estamos aqui para orar junto com você e apoiar no que for preciso. 🙏",
    EstadoVisitante.HORARIOS: (
        "*Seguem nossos horários de cultos:*\n"
        "🌿 *Domingo* - Culto da Família - às 19h\n"
        "Uma oportunidade de estar em comunhão com sua família, adorando a Deus e agradecendo por cada bênção. "
        "\"Eu e a minha casa serviremos ao Senhor.\" *(Josué 24:15)*\n"
        "🔥 *Quinta Fé* - Culto dos Milagres - às 20h\n"
        "Um encontro de fé para vivermos o sobrenatural de Deus. "
        "\"Tudo é possível ao que crê.\" *(Marcos 9:23)*\n"
        "🎉 *Sábado* - Culto Alive - às 20h\n"
        "Jovem, venha viver o melhor sábado da sua vida com muita alegria e propósito! "
        "\"Ninguém despreze a tua mocidade, mas sê exemplo dos fiéis.\" *(1 Timóteo 4:12)*\n"
        "🙏 Somos Uma Igreja Família, Vivendo os Propósitos de Deus! "
        "\"Pois onde estiverem dois ou três reunidos em meu nome, ali estou no meio deles.\" *(Mateus 18:20)*\n"
        "Gostaria de mais informações?"
        ),
    EstadoVisitante.LINK_WHATSAPP: f"Aqui está o link para entrar no nosso grupo do WhatsApp: {link_grupo}\n"
                                   "Agradecemos seu contato e esperamos vê-lo em breve!",
    EstadoVisitante.OUTRO: "Entendido! 😉 Fique à vontade para nos contar como podemos te ajudar. "
                           "Estamos aqui para ouvir e apoiar você!",
    EstadoVisitante.FIM: "Muito obrigado pelo seu contato, {visitor_name}! 🙏 "
                         "Se precisar de mais alguma coisa, estaremos sempre aqui para você. "
                         "Que Deus te abençoe e até breve! 👋",
}

# --- Palavras-chave de ministérios ---
palavras_chave_ministerios = {
    "homens": "Paz de Cristo, somos os Homens Corajosos da Mais de Cristo Canasvieiras, "
              "nossa missão é servir a Deus com toda força e coração, nos colocando a frente dos propósitos de Deus, "
              "para sermos, sacerdotes da nossa casa, homens de coragem e temente a Deus.\n"
              "Venha fazer parte deste exército e ficar mais próximo do seu propósito.\n"
              "Segue link do grupo de whatsapp: " + link_grupo_homens_corajosos,
    "mulheres": "Paz de Cristo, somos o Ministério Mulheres Transformadas da Mais de Cristo Canasvieiras. "
                "Nosso objetivo é promover o crescimento espiritual das mulheres, fortalecendo nossa fé e "
                "nos unindo em amor e comunhão. Temos encontros mensais cheios de aprendizado e inspiração.\n"
                "Venha fazer parte deste grupo e viver os propósitos que Deus tem para sua vida.\n"
                "Segue link do grupo de whatsapp: " + link_grupo_transformadas,
    "jovens": "O Ministério Alive é dedicado aos jovens e adolescentes, com cultos vibrantes e cheios de propósito.",
    "criancas": "Venha fazer a diferença na vida das crianças! "
                "Junte-se ao Ministério Kids e ajude a semear amor e fé no coração dos pequenos.",
    "kids": "Venha fazer a diferença na vida das crianças! "
            "Junte-se ao Ministério Kids e ajude a semear amor e fé no coração dos pequenos.",
    "infantil": "Venha fazer a diferença na vida das crianças! "
                "Junte-se ao Ministério Kids e ajude a semear amor e fé no coração dos pequenos.",
    "21 dias": "Olá! Ficamos felizes com seu interesse nos 21 dias de oração. 🙏 "
               "Este evento acontece diariamente, das 23h às 23:30, na igreja, e seguirá até o dia 20 de novembro.\n"
               "Será um tempo especial para buscar paz, inspiração e fortalecer a fé. "
               "Caso precise de mais informações ou queira confirmar presença, estou aqui para ajudar!",
    "pastor": "Nossos pastores atuais são:\n"
              "- *Pr Fábio Ferreira*\n"
              "- *Pra Cláudia Ferreira*\n"
              "Você pode seguir o *_Pr Fábio Ferreira_* no Instagram: _@prfabioferreirasoficial_\n"
              "E a *_Pra Cláudia Ferreira_* no Instagram: _@claudiaferreiras1_",
    "mais amor": "O Ministério Mais Amor é focado em ações sociais, ajudando os necessitados da nossa comunidade.",
    "gc": "*Grupos de Comunhão (GC)* - _Pequenos encontros semanais nos lares para compartilhar histórias,_\n"
          " _oração e comunhão._ \n"
          "Participe e viva momentos de fé e crescimento espiritual!\n"
          "*Inscreva-se aqui:* \n"
          "https://docs.google.com/forms/d/e/1FAIpQLSdj0b3PF-3jwt9Fsw8FvOxv6rSheN7POC1e0bDzub6vEWJm2A/viewform"
}

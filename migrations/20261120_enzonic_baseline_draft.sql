-- Nous CRM Church | reconstrução inicial MySQL 8.4 / Enzonic
-- Executar SOMENTE em instância vazia de homologação.
-- Não recupera dados históricos. Revisar compatibilidade antes de produção.
-- Banco já provisionado pela Enzonic: main. Não executar CREATE DATABASE.
SET NAMES utf8mb4;
CREATE TABLE IF NOT EXISTS visitantes (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 nome VARCHAR(255) NOT NULL, telefone VARCHAR(32) NOT NULL UNIQUE,
 email VARCHAR(255), data_nascimento DATE, cidade VARCHAR(100),
 genero VARCHAR(20), estado_civil VARCHAR(50), igreja_atual VARCHAR(100),
 frequenta_igreja TINYINT(1), indicacao VARCHAR(100), membro VARCHAR(50),
 pedido_oracao TEXT, horario_contato VARCHAR(100),
 origem VARCHAR(64) DEFAULT 'integra+', data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP,
 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_visitantes_cadastro(data_cadastro)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS fases (
 id INT AUTO_INCREMENT PRIMARY KEY, descricao VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS status (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, visitante_id BIGINT NOT NULL,
 fase_id INT, origem VARCHAR(64) DEFAULT 'integra+',
 data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_status_visitante(visitante_id, id),
 CONSTRAINT fk_status_visitante FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE,
 CONSTRAINT fk_status_fase FOREIGN KEY (fase_id) REFERENCES fases(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS interacoes (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, visitante_id BIGINT,
 tipo VARCHAR(50), data_hora DATETIME DEFAULT CURRENT_TIMESTAMP, observacao TEXT,
 FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS conversas (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, visitante_id BIGINT,
 mensagem TEXT NOT NULL, message_sid VARCHAR(255),
 tipo VARCHAR(50), origem VARCHAR(64) DEFAULT 'integra+',
 data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_conversas_visitante_data(visitante_id, created_at),
 INDEX idx_conversas_sid(message_sid),
 FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS estatisticas (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, numero VARCHAR(32) NOT NULL,
 estado_atual VARCHAR(100) NOT NULL, proximo_estado VARCHAR(100) NOT NULL,
 origem VARCHAR(64) DEFAULT 'integra+', data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS usuarios (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(255) NOT NULL,
 email VARCHAR(255) NOT NULL UNIQUE, senha VARCHAR(255) NOT NULL,
 tipo_usuario VARCHAR(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS membros (
 id_membro BIGINT AUTO_INCREMENT PRIMARY KEY,
 nome VARCHAR(255) NOT NULL, telefone VARCHAR(32) UNIQUE, email VARCHAR(255),
 data_nascimento DATE, genero VARCHAR(20), cep VARCHAR(16), bairro VARCHAR(120),
 cidade VARCHAR(120), estado VARCHAR(40), estado_civil VARCHAR(50),
 conjuge_nome VARCHAR(255), possui_filhos VARCHAR(32), filhos_info TEXT,
 novo_comeco VARCHAR(100), novo_comeco_quando VARCHAR(100),
 classe_membros VARCHAR(100), apresentacao_data DATE, consagracao VARCHAR(100),
 status_membro VARCHAR(50) DEFAULT 'ativo', data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS membros_discipulados (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, id_membro BIGINT NOT NULL,
 discipulado VARCHAR(255) NOT NULL, INDEX idx_md_membro(id_membro),
 FOREIGN KEY (id_membro) REFERENCES membros(id_membro) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS membros_ministerios (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, id_membro BIGINT NOT NULL,
 ministerio VARCHAR(255) NOT NULL, INDEX idx_mm_membro(id_membro),
 FOREIGN KEY (id_membro) REFERENCES membros(id_membro) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS eventos (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(255) NOT NULL,
 data DATE, descricao TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS log_mensagens (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, visitante_id BIGINT,
 mensagem TEXT NOT NULL, status VARCHAR(50),
 data_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS eventos_envios (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, visitante_id BIGINT NOT NULL,
 mensagem TEXT, imagem_url TEXT, status VARCHAR(50) DEFAULT 'pendente',
 data_envio DATETIME NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_eventos_envios_status(status),
 FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS fila_envios (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, numero VARCHAR(32) NOT NULL,
 mensagem TEXT NOT NULL, imagem_url TEXT, status VARCHAR(32) DEFAULT 'pendente',
 tentativas INT NOT NULL DEFAULT 0, meta_json JSON NULL,
 criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
 atualizado_em DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_fila_status(status,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS training_pairs (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, question VARCHAR(768) NOT NULL,
 answer TEXT NOT NULL, category VARCHAR(100), fonte VARCHAR(100),
 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_training_question(question(190))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS unknown_questions (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, question TEXT NOT NULL,
 status VARCHAR(32) DEFAULT 'pending',
 created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS spaces (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, nome VARCHAR(255) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS reservas (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, space_id BIGINT NOT NULL,
 nome VARCHAR(255) NOT NULL, telefone VARCHAR(32), finalidade TEXT,
 data DATE NOT NULL, hora_inicio TIME NOT NULL, hora_fim TIME NOT NULL,
 status VARCHAR(32) NOT NULL DEFAULT 'pendente',
 criado_em DATETIME DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_reservas_agenda(space_id,data,status,hora_inicio,hora_fim),
 FOREIGN KEY (space_id) REFERENCES spaces(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO fases(descricao) VALUES
 ('INICIO'),('MENU'),('BATIZADO'),('INTERESSE_DISCIPULADO'),
 ('INTERESSE_NOVO_COMEC'),('PEDIDO_ORACAO'),('OUTRO'),('FIM'),
 ('HORARIOS'),('LINK_WHATSAPP'),('EVENTO_ENVIADO');
-- A migration 20261012_oracao_persistente.sql deve ser aplicada separadamente,
-- após validar as tabelas acima. Nenhum usuário, membro ou espaço é inventado.

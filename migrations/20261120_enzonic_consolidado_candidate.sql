-- NOUS CRM Church / Enzonic MySQL 8.4
-- Consolidacao estrutural para banco NOVO main. Dados antigos NAO incluidos.
-- AINDA NAO HOMOLOGADO EM MYSQL REAL. Execute apenas apos validacao final.
-- NAO executa CREATE DATABASE, DROP, TRUNCATE, nem cria usuarios.
-- Automacoes de WhatsApp permanecem desativadas por padrao.

-- Nous CRM Church | reconstrução inicial MySQL 8.4 / Enzonic
-- Consolidacao em auditoria; nao executar em producao sem validacao.
-- Corrigidos campos confirmados em fila_envios e eventos_envios.
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
 evento_nome VARCHAR(255), mensagem TEXT, imagem_url TEXT, origem VARCHAR(64), status VARCHAR(50) DEFAULT 'pendente',
 data_envio DATETIME NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_eventos_envios_status(status),
 FOREIGN KEY (visitante_id) REFERENCES visitantes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS fila_envios (
 id BIGINT AUTO_INCREMENT PRIMARY KEY, numero VARCHAR(32) NOT NULL,
 mensagem TEXT NOT NULL, imagem_url TEXT, status VARCHAR(32) DEFAULT 'pendente',
 tentativas INT NOT NULL DEFAULT 0, meta_json JSON NULL,
 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 scheduled_for DATETIME NULL, status_code INT NULL, last_error VARCHAR(500) NULL,
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

-- Tabelas IA e configuracao de automacoes
-- Complemento de auditoria do CRM (2026-11-20)
-- Campos confirmados em routes/ia.py e servicos/planejador_boas_vindas.py
CREATE TABLE IF NOT EXISTS knowledge_base (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 question VARCHAR(768) NOT NULL,
 answer TEXT NOT NULL,
 category VARCHAR(100) NULL,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_knowledge_question (question(190))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS crm_automation_settings (
 automation_key VARCHAR(80) PRIMARY KEY,
 enabled TINYINT(1) NOT NULL DEFAULT 0,
 last_run DATETIME NULL,
 last_result VARCHAR(255) NULL,
 updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO crm_automation_settings(automation_key,enabled) VALUES ('boas_vindas',0);

-- Fluxo de oracao
-- Aplicar manualmente no MySQL antes de habilitar o fluxo.
CREATE TABLE IF NOT EXISTS integra_pedidos_oracao (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 telefone VARCHAR(32) NOT NULL,
 origem VARCHAR(64) NOT NULL DEFAULT 'integra+',
 nome VARCHAR(160) NOT NULL,
 sid_origem VARCHAR(160) NULL,
 situacao_atendimento ENUM('PENDENTE','CONCLUIDO') NOT NULL DEFAULT 'PENDENTE',
 motivo TEXT NULL,
 estado ENUM('AGUARDANDO_MOTIVO','PRONTO','ENCAMINHADO','ENVIO_INCERTO') NOT NULL DEFAULT 'AGUARDANDO_MOTIVO',
 prazo_utc DATETIME NOT NULL,
 criado_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 encaminhado_utc DATETIME NULL,
 UNIQUE KEY uq_oracao_sid (origem, sid_origem),
 INDEX idx_prazo (estado, prazo_utc),
 INDEX idx_telefone (telefone, origem, estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS integra_oracao_entregas (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 pedido_id BIGINT NOT NULL,
 destinatario VARCHAR(32) NOT NULL,
 estado ENUM('PENDENTE','EM_ENVIO','CONFIRMADO','INCERTO') NOT NULL DEFAULT 'PENDENTE',
 atualizado_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_pedido_destinatario (pedido_id,destinatario),
 FOREIGN KEY (pedido_id) REFERENCES integra_pedidos_oracao(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
-- Campo pastoral separado do estado de diálogo; não substituir o status atual.
CREATE TABLE IF NOT EXISTS integra_interesses (
 telefone VARCHAR(32) NOT NULL,
 origem VARCHAR(64) NOT NULL,
 ultimo_interesse VARCHAR(64) NOT NULL,
 atualizado_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 PRIMARY KEY(telefone, origem)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Complementos tardios: entrega independente, sem reenviar o pedido original.
CREATE TABLE IF NOT EXISTS integra_oracao_complementos (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 pedido_id BIGINT NOT NULL,
 sid_origem VARCHAR(160) NULL,
 texto TEXT NOT NULL,
 criado_utc DATETIME NOT NULL,
 UNIQUE KEY uq_complemento_sid (pedido_id, sid_origem),
 FOREIGN KEY (pedido_id) REFERENCES integra_pedidos_oracao(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS integra_oracao_complemento_entregas (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 complemento_id BIGINT NOT NULL,
 destinatario VARCHAR(32) NOT NULL,
 estado ENUM('PENDENTE','EM_ENVIO','CONFIRMADO','INCERTO') NOT NULL DEFAULT 'PENDENTE',
 UNIQUE KEY uq_complemento_destinatario (complemento_id,destinatario),
 FOREIGN KEY (complemento_id) REFERENCES integra_oracao_complementos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Diagnostico final (execute como consulta separada se o editor nao suportar multiplas instrucoes)
SELECT COUNT(*) AS total_tabelas FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE';
SELECT automation_key,enabled FROM crm_automation_settings;

-- Aplicar manualmente no MySQL antes de habilitar o fluxo.
CREATE TABLE IF NOT EXISTS integra_pedidos_oracao (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 telefone VARCHAR(32) NOT NULL,
 origem VARCHAR(64) NOT NULL DEFAULT 'integra+',
 nome VARCHAR(160) NOT NULL,
 motivo TEXT NULL,
 estado ENUM('AGUARDANDO_MOTIVO','PRONTO','ENCAMINHADO','ENVIO_INCERTO') NOT NULL DEFAULT 'AGUARDANDO_MOTIVO',
 prazo_utc DATETIME NOT NULL,
 criado_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 encaminhado_utc DATETIME NULL,
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

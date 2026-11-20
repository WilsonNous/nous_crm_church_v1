-- Complemento de auditoria do CRM (2026-11-20)
-- NÃO EXECUTAR ISOLADAMENTE: depende da baseline revisada.
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

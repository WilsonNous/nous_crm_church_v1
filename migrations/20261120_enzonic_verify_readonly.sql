-- Execute in Enzonic SQL Editor, database main. READ ONLY.
SELECT DATABASE() AS database_name, VERSION() AS mysql_version;
SELECT COUNT(*) AS tables_found FROM information_schema.tables WHERE table_schema=DATABASE() AND table_type='BASE TABLE';
SELECT t.table_name, COUNT(c.column_name) AS columns_found
FROM information_schema.tables t
LEFT JOIN information_schema.columns c ON c.table_schema=t.table_schema AND c.table_name=t.table_name
WHERE t.table_schema=DATABASE() AND t.table_type='BASE TABLE'
GROUP BY t.table_name ORDER BY t.table_name;
SELECT k.table_name,k.column_name,k.referenced_table_name,k.referenced_column_name
FROM information_schema.key_column_usage k
WHERE k.table_schema=DATABASE() AND k.referenced_table_name IS NOT NULL
ORDER BY k.table_name,k.column_name;
SELECT automation_key,enabled FROM crm_automation_settings;
SELECT COUNT(*) AS spaces_count FROM spaces;
-- Verify high-risk columns (zero rows = no missing columns).
SELECT required.table_name, required.column_name
FROM (
 SELECT 'fila_envios' AS table_name,'scheduled_for' AS column_name UNION ALL
 SELECT 'fila_envios','status_code' UNION ALL SELECT 'fila_envios','last_error' UNION ALL
 SELECT 'fila_envios','created_at' UNION ALL SELECT 'fila_envios','meta_json' UNION ALL
 SELECT 'eventos_envios','evento_nome' UNION ALL SELECT 'eventos_envios','origem' UNION ALL
 SELECT 'conversas','created_at' UNION ALL SELECT 'visitantes','data_cadastro' UNION ALL
 SELECT 'reservas','hora_inicio' UNION ALL SELECT 'reservas','hora_fim' UNION ALL
 SELECT 'knowledge_base','question' UNION ALL SELECT 'knowledge_base','answer'
) required
LEFT JOIN information_schema.columns actual
ON actual.table_schema=DATABASE() AND actual.table_name=required.table_name AND actual.column_name=required.column_name
WHERE actual.column_name IS NULL;

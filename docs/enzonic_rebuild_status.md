# Reconstrução Enzonic — rascunho, NÃO aplicar em produção

Branch: `rebuild/enzonic-mysql-20261120`
Banco destino: `main` na instância `nouscrmchurch`.

## Situação
- O banco Enzonic foi confirmado vazio via information_schema.
- Foi preparado um esquema **inicial**, não uma reconstrução homologada.
- O script `database_setup.py` antigo não cobre módulos atuais e tem FK de `status` antes de `fases`.
- `database.py` usa `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DB`, `MYSQL_USER`, `MYSQL_PASSWORD`; TLS obrigatório ainda exige ajuste e teste.
- A migration existente `20261012_oracao_persistente.sql` deve ser aplicada depois da baseline.
- **Não executar ainda**: falta revisão integral das consultas, colunas e contratos da aplicação, testes em MySQL 8.4 e verificação de privilégios.
- **Não habilitar fila de WhatsApp**: histórico de consentimento e registros de conversa não foram recuperados.
- Nenhum dado histórico da HostGator foi recuperado.
- Nenhuma credencial deve ser commitada. Rotacionar senha compartilhada na conversa.

## Pendências antes de execução
1. Auditar todas as referências SQL (inclusive `fila_envios`, `eventos_envios`, `training_pairs`, `unknown_questions`, `reservas`).
2. Comparar colunas, tipos e índices contra cada query.
3. Validar seed de espaços e autenticação sem criar contas ou senhas padrão.
4. Implementar TLS com verificação de certificado e testar cold start da Enzonic.
5. Executar DDL em banco de homologação vazio e rodar testes de integração.
6. Só então planejar cutover do Render com rollback e backup externo.

## Validação somente leitura
```sql
SELECT TABLE_NAME FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
```

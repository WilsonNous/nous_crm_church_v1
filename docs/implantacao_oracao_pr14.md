# Implantação controlada — fluxo de oração

## Antes do deploy

1. Fazer backup do MySQL e aplicar `migrations/20261012_oracao_persistente.sql` no banco correto. Confirmar as cinco tabelas e as chaves únicas.
2. Executar `python -m unittest discover -s tests -p 'test_prayer_*.py' -v` em ambiente isolado. Os testes não enviam WhatsApp.
3. Configurar um **Render Cron Job separado**, com as mesmas variáveis de ambiente de banco e Z-API do serviço web, comando `python -m servicos.oracao_persistente` e cron `* * * * *` (cada minuto). Validar previamente a disponibilidade e custo desse recurso no plano contratado.
4. Implantar o serviço web somente depois de confirmar a migração e o cron configurado. Evitar duas instâncias do cron com a mesma responsabilidade.

## Critérios operacionais

- Seleção 3 registra pedido com prazo de 15 minutos; resposta antecipada torna o pedido PRONTO.
- Ao vencer o prazo, o worker prepara duas entregas, uma por intercessor.
- Uma entrega INCERTO ou EM_ENVIO não pode ser reenviada automaticamente: revisar manualmente evidências na Z-API antes de qualquer ação.
- CONCLUIDO exige confirmação das entregas registradas. A confirmação de API não comprova leitura pelo destinatário.
- Complemento tardio deve usar prefixo `complemento:` ou `motivo:` e SID único do webhook.
- Testar manualmente o cenário de webhook duplicado e concorrência em homologação com banco isolado antes de habilitar envios reais.

## Plano de retorno

- Se ocorrer falha, desabilitar o cron e reverter o deploy web; preservar as tabelas e entregas para auditoria.
- Não apagar pedidos ou reprocessar EM_ENVIO/INCERTO automaticamente.
- Evitar colocar conteúdo sensível de oração em logs de aplicação.

**Importante:** o workflow GitHub valida sintaxe e lógica isolada, não substitui testes integrados com MySQL real de homologação, nem confirma que o Render Cron está ativo.

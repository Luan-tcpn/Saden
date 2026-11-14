# Release 2 — próximas ações

**Data:** 2026-11-14

## Prioridade 1 — operação real

1. **Deploy em ambiente autorizado.** Não existe ambiente público configurado
   aqui. Falta: host, domínio, `JWT_SECRET` de produção, volume persistente e
   `SADEN_ADMIN_EMAILS`. Ver `DEPLOYMENT_STATUS.md`.
2. **Ligar o CI em runner remoto.** O workflow existe e os comandos foram
   rodados localmente; falta a primeira execução no GitHub Actions.
3. **Monitorar a primeira semana.** Acompanhar `/api/health/worker` e
   `worker_runs` para ver taxa de sucesso real com a fonte.

## Prioridade 2 — dívida conhecida

4. **`rain_above` legado**: decidir arquivamento explícito na UI (hoje aparece
   na lista e não é avaliado).
5. **Feriados de mercado**: só modelar se aparecerem falsos "atrasado".
6. **Fuso na exibição**: o worker agenda em `America/Sao_Paulo`; a interface usa
   o fuso do navegador. Aceitável, mas pode confundir — considerar padronizar.

## Prioridade 3 — produto (guiado por uso)

Ver `docs/product/USAGE_DRIVEN_ROADMAP.md`. Nada novo antes de sinal de uso.

## Bloqueios

| item | bloqueio |
|---|---|
| deploy público | ausência de infraestrutura autorizada |
| e-mail/push | ausência de SMTP/serviço; fora de escopo |
| série física regional | CEPEA/CONAB sem API pública |

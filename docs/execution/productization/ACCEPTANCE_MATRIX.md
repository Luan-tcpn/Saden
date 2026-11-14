# Productização — matriz de aceitação

**Data:** 2026-11-14

| # | critério | estado | evidência |
|---|---|---|---|
| 1 | branch própria criada | **aceito** | `product/price-alerts-mvp` a partir de `3f7ad33` |
| 2 | V1.1 preservada | **aceito** | `main`/`v1-final` inalterados; sem merge |
| 3 | aplicação existente funcionando | **aceito** | 85 testes verdes; suíte da V1.1 intacta |
| 4 | funcionalidade principal implementada | **aceito** | alertas de preço por série |
| 5 | backend integrado | **aceito** | `alertEngine` no fluxo real de atualização de preço |
| 6 | frontend integrado | **aceito** | seção Alertas da própria navegação |
| 7 | persistência funcionando | **aceito** | tabelas migradas; eventos gravados |
| 8 | autenticação respeitada | **aceito** | todas as rotas com `requireAuth` |
| 9 | isolamento entre usuários | **testado** | alerta e eventos de terceiros: 404 / 0 linhas |
| 10 | fonte real consultada | **validado** | algodão R$ 4,45/lp em 2026-11-13 (Yahoo+PTAX) |
| 11 | atualização e limitações comunicadas | **aceito** | painel da série + guia + relatório §8 |
| 12 | eventos persistidos | **aceito** | `alert_events` com preço, data e leitura |
| 13 | idempotência comprovada | **testado** | mesmo par (alerta, observação) ⇒ 1 evento |
| 14 | responsividade validada | **testado** | 320/390/414/768/1024 px sem overflow |
| 15 | testes aprovados | **aceito** | 21 unit + 4 integração novos + 65 herdados = 90 |
| 16 | documentação completa | **aceito** | decisão, relatório, guia, 5 checkpointos |
| 17 | regressões corrigidas | **aceito** | delete global de eventos removido; overflow corrigido |
| 18 | bundle validado | **aceito** | ver `BUNDLE_INFO.txt` |
| 19 | branch publicada | **aceito** | `origin/product/price-alerts-mvp` |

## Não aceito / bloqueado

| # | item | estado | motivo |
|---|---|---|---|
| 20 | monitoramento com app fechado | **bloqueado** | exige agendador persistente; não existe no ambiente |
| 21 | notificação por e-mail | **bloqueado** | sem SMTP configurado; outbox é de desenvolvimento |
| 22 | série de preço físico regional | **bloqueado** | CEPEA/CONAB sem API pública (verificado) |
| 23 | push notification | **não implementado** | fora do escopo declarado |
| 24 | E2E no CI | **não implementado** | validação foi manual e documentada |
| 25 | rate limit em `/alerts/evaluate` | **pendente** | herdado só no login |

## Veredito

O critério "não considere concluído um recurso apenas visual" está atendido: o
evento nasce de uma observação real persistida, é gravado uma única vez, é
consultável e pode ser marcado como lido. O que **não** está entregue é a
promessa implícita de vigilância contínua — e ela é explicitamente negada na
interface, no guia e neste documento.

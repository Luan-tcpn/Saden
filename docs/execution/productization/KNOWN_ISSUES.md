# Productização — problemas conhecidos

**Data:** 2026-11-14

## Funcionais

| # | problema | impacto | estado |
|---|---|---|---|
| K1 | **Sem avaliação em segundo plano**: só avalia quando o preço é atualizado por consulta ou em "Verificar agora" | alto — é a limitação central do recurso | declarado na UI e no relatório |
| K2 | Sem notificação por e-mail/push | médio | fora de escopo (sem infraestrutura) |
| K3 | Série é referência internacional convertida, não preço local | alto para decisão comercial | declarado em toda a UI |
| K4 | Não há série física regional (CEPEA/CONAB sem API) | alto | fontes marcadas como `blocked` |
| K5 | Frescor fixo de 7 dias para todas as séries | baixo (todas são diárias hoje) | mapeado em NEXT_ACTIONS 2.2 |
| K6 | `rain_above` legado não é criável nem avaliado | baixo | registros antigos seguem visíveis |
| K7 | Alerta disparado não "rearma" sozinho | por desenho | documentado no guia |

## Técnicos

| # | problema | impacto | estado |
|---|---|---|---|
| K8 | Node do PATH (26) é incompatível com o `better-sqlite3` instalado (Node 22) | médio — ambiente | contornado com Node 22 em `tmp/`; documentado |
| K9 | `POST /api/alerts/evaluate` sem rate limit | baixo | NEXT_ACTIONS 3.2 |
| K10 | Sem lock para múltiplas instâncias no gancho de avaliação | baixo (instância única) | relevante só se escalar |
| K11 | E2E não está no CI | médio | NEXT_ACTIONS 3.3 |
| K12 | Tabela de alertas rola internamente em telas < 560 px | baixo (por desenho) | aceito |

## Riscos que valem atenção

**K1 é o risco que importa.** Um usuário pode criar o alerta, fechar o app e
esperar ser avisado — e não ser, porque nada roda. A interface diz isso na seção
de eventos, mas a expectativa de "alerta" é forte. Se este release for
apresentado a usuários reais, o texto deve ser explícito **antes** da criação,
não apenas na lista de eventos. Registrado como ação prioritária 1.1.

**K3 é o risco de interpretação.** R$ 154,88/sc de soja em Chicago convertido
por PTAX não é o preço da saca na fazenda. A UI mostra a limitação no painel da
série e no guia; qualquer evolução deve manter esse aviso.

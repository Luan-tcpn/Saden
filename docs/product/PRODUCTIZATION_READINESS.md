# SADEN — Prontidão para integração ao produto

**Data:** 2026-11-14 · Escopo: **avaliação apenas**. Nada foi implementado.
Frontend, backend, banco e arquitetura da aplicação **não foram alterados**.

---

## 1. Situação de partida

A V1.1 é a referência de estabilidade do produto (`v1-final`, `3f7ad33`). Ela
projeta preço a partir de séries internacionais e câmbio. A pesquisa
agroclimática (V2.6–V3.5) nunca foi integrada.

Uma versão só supera a V1.1 se houver ganho **concreto e mensurável**. Um
relatório científico, por si só, **não é** uma versão superior da aplicação.

## 2. Critérios de avaliação

Para cada candidato: ganho validado? validação temporal? generalização? fonte
real? série atualizada? usável pelo usuário? limitação comunicável? risco de
interpretação errada?

| candidato | ganho validado | valid. temporal | generalização | fonte real | atualiza | usável | limitação comunicável | risco | veredito |
|---|---|---|---|---|---|---|---|---|---|
| **Contexto agroclimático descritivo** (percentil do déficit na janela) | parcial (associação) | não | 7 UFs | sim (NASA POWER + PAM) | sim, anual | sim | **sim** | baixo | **candidato nº 1** |
| **Indicador de oferta** (produção esperada) | **não** | não | não | sim | sim | sim | difícil | **alto** | não fazer |
| **Alerta de safra** | **não** | não | não | sim | sim | sim | muito difícil | **muito alto** | **não fazer** |
| **Informação territorial** (mapa, MRS, CAD) | descritivo | n/a | Brasil (IBGE) | sim | anual | sim | sim | baixo | candidato nº 2 |
| **Proveniência nas previsões de preço** | **sim** (é o que a V1.1 já faz) | n/a | n/a | sim | sim | sim | sim | baixo | **já existe** |
| **Explicação de previsões** | parcial | não | n/a | sim | sim | sim | sim | médio | candidato nº 3 |
| **Relatórios exportáveis** | baixo | n/a | n/a | sim | n/a | sim | sim | baixo | candidato nº 4 |

## 3. Detalhe dos candidatos viáveis

### 3.1. Contexto agroclimático descritivo — prioridade 1

Mostrar, para o município/região selecionado, o déficit hídrico da janela
agrícola da safra corrente e sua posição na série (percentil). Exemplo:
"déficit de 152 mm na janela da soja — percentil 78 da série 2017–2025".

- **Base científica:** o déficit é a variável com associação mais robusta
  (−2,27 kg/ha/mm na soja, MDE 1,14).
- **Por que é defensável:** é descritivo. Não afirma efeito, não prevê safra.
- **O que ainda falta:** definir a redação exata que impeça leitura causal;
  decidir o que fazer nos 52% do território sem cobertura.
- **Risco residual:** usuário inferir "vai quebrar safra". Mitigável com texto
  explícito e ausência de semáforo/alerta.

### 3.2. Informação territorial — prioridade 2

MRS, CAD observada, área municipal, centróide. Dados oficiais, sem inferência.

### 3.3. Explicação de previsões — prioridade 3

A V1.1 é um modelo Ridge: já é possível expor contribuições por variável sem
novo resultado científico. Independente da linha B.

### 3.4. Relatórios — prioridade 4

Exportar o que já existe. Sem ganho científico novo.

## 4. O que explicitamente **não** deve ser feito

- **Qualquer previsão de produtividade** exibida como expectativa de safra.
- **Semáforo de risco climático** baseado em limiar escolhido depois de olhar os
  dados.
- **Agregação nacional** — a cobertura é 48,3% do território indicado.
- **Mistura com preço** do tipo "déficit alto ⇒ preço alto": não há nenhuma
  estimativa que ligue as duas linhas.

## 5. Portão de autorização

A consolidação termina aqui. A próxima etapa de produto deve ser **separada**,
com escopo definido e autorização própria. Recomendação objetiva:

1. Escrever a **redação** do contexto agroclimático (uma página) e submetê-la a
   revisão crítica antes de qualquer código.
2. Verificar que a série 2025 está completa para os municípios exibidos.
3. Só então implementar, em branch própria, sem tocar em `main`.

Não há merge em `main` nesta etapa.

## 6. Comparação com a V1.1

| dimensão | V1.1 | V3.5 (pesquisa) |
|---|---|---|
| utilidade ao usuário final | alta (preço) | nula (não é interface) |
| funcionamento | estável, congelado | pipeline reprodutível |
| confiabilidade dos dados | séries internacionais | PAM auditada, clima não validado contra estação |
| experiência | existente | inexistente |
| manutenção | baixa dívida | pipeline canônico criado agora |
| capacidade de uso | sim | não |

**Conclusão:** a linha B **não supera** a V1.1 como aplicação. Ela é insumo
potencial para uma **V2.0** que ainda não existe e não foi autorizada.

# SADEN V2.8 — Próximas ações

> A V2.8 está encerrada. P0–P3 concluídos; P4 é a pauta da V2.9.

## P0 — Decomposição e reprodução (concluída)

- [x] Auditar e reproduzir P1/P3/P5 (`SE = P3`, `TE = P5` exatos).
- [x] Medir a estrutura das divisões (tamanhos, anos, blocos, UFs).
- [x] Fatorial espaço × tempo com controle de tamanho (D87).
- [x] Refutar a hipótese de tamanho amostral (≤ 1 kg/ha de diferença).

## P1 — Linha de base (concluída)

- [x] Auditar a linha de base (média nacional do treino).
- [x] Acrescentar média por UF e média UF×ano, com quedas explícitas.
- [x] Acrescentar `climate_plus_state` para igualar informação.
- [x] Comparar com IC por bootstrap de bloco.
- [x] Documentar que a média UF×ano não é referência operacional.

## P2 — CAD e ciclo (concluídas com escopo limitado)

- [x] Validar a unidade `mm/cm` numericamente (D88).
- [x] Medir o efeito da CAD no balanço hídrico (9 municípios).
- [x] Diagnosticar a cobertura de CAD no painel (5/1.296 municípios).
- [x] Estratificar a associação por classe de ciclo do ZARC (D89).
- [x] Medir a duração da janela ZARC por classe.
- [ ] Rotular as classes de ciclo — **bloqueado**: dicionário de dados do ZARC
  (PDF) não está nos artefatos adquiridos.

## P3 — Síntese, testes e publicação (concluída)

- [x] Relatório `docs/V2_8_GENERALIZATION_REPORT.md` (20 seções).
- [x] Decisões D87–D89 em `docs/DECISIONS.md`.
- [x] Suíte **338/338** offline.
- [x] Bundle e publicação da branch.

## P4 — V2.9 (recomendações)

1. **Adotar `climate_plus_state`** como modelo de referência dos protocolos
   territoriais, reportando sempre média nacional **e** média da UF.
2. **Completar a CAD** para os 1.296 municípios do painel, preservando a
   heterogeneidade (razão 1,9 entre mínimo e máximo), e reestimar os
   coeficientes de déficit. Exige decisão de escopo e extração WCS massiva.
3. **Obter o dicionário de dados do ZARC** para rotular as classes de ciclo e
   reconstruir janelas por classe em vez de uma janela modal única.
4. **Investigar o efeito do bloco no milho** — é o fator dominante dessa
   cultura e não é explicado por UF nem por ano.
5. **Profundidade radicular por cultura** com fonte agronômica verificável,
   para substituir o perfil 0–100 cm por uma CAD efetiva.
6. Manter a **Ridge** como único modelo de preços; nenhuma variável
   agroclimática entra na previsão de preços sem ganho temporal demonstrado.

## Bloqueios herdados

- ERA5-Land nativo: credencial CDS ausente (D83).
- CHIRPS/ARCO: sem resolução DNS.

# SADEN V2.9 — Próximas ações

> A V2.9 está encerrada. P0–P3 concluídos; P4 é a pauta da V3.0.

## P0 — Auditoria e reprodução (concluída)

- [x] Auditar a equalização da V2.8 (global ≠ por célula) e refazer com
  equalização estrita (D90).
- [x] Modelos aninhados M0 → M1 → M2 com igualdade de informação (D91).
- [x] Escala do bloco em 150/250/400/600 km, sem reotimizar (D92).

## P1 — CAD e ZARC (concluídas com escopo declarado)

- [x] Validar a estratégia de aquisição (scaleFactor=0.2, 60× menor) e corrigir
  a integração por profundidade (D93).
- [x] Amostra estratificada de 120 municípios (20 por UF).
- [x] Balanço hídrico com a CAD do próprio município; heterogeneidade da razão
  quantificada.
- [x] Dicionário oficial do ZARC obtido e registrado (D94).
- [x] Teste formal de interação por grupo de ciclo; correção da leitura da V2.8.
- [ ] Cobertura completa de CAD (1.296 municípios) — **parcial**: plano
  validado, ~5 h de aquisição, retomável.
- [ ] Profundidade radicular por cultura — **bloqueado**: sem fonte
  cultivar-específica.

## P2 — Testes e reprodutibilidade (concluída)

- [x] 26 testes novos (equalização, repetições, ciclo/interação, CAD por
  profundidade).
- [x] Suíte **364/364** offline.

## P3 — Publicação (concluída)

- [x] Relatório `docs/V2_9_REGIONAL_AGROCLIMATIC_REPORT.md`.
- [x] Decisões D90–D94 em `docs/DECISIONS.md`.
- [x] Bundle e publicação da branch.

## P4 — V3.0 (recomendações)

1. **Concluir a CAD** (1.296 municípios) e **reestimar o déficit** por
   município. A heterogeneidade da razão (0,007–0,959; 13,6% de déficit
   eliminado) é o que muda a inferência, não a média.
2. **Adotar M0/M1/M2 como padrão de relato**; "ganho contra a média nacional"
   não descreve valor incremental do clima.
3. **Reduzir a dependência do ano compartilhado**: qualquer alegação de
   generalização deve vir do braço TE, e o braço TE precisa de mais anos ou de
   dados que não sejam reanálise.
4. **Investigar PR/MS no milho**: o efeito do bloco está concentrado ali
   (+421 e +171 kg/ha). Testar se um termo espacial suave (latitude/longitude)
   ou um baseline de vizinhos históricos reduz o efeito.
5. **Ampliar UFs** apenas com diagnóstico de representatividade por bioma e
   sistema produtivo — hoje são 5–6 de 27.
6. **Profundidade radicular** com fonte agronômica verificável, para substituir
   o perfil 0–100 cm por uma CAD efetiva por cultura.
7. Manter a **Ridge** como único modelo de preços.

## Bloqueios herdados

- ERA5-Land nativo: credencial CDS ausente (D83).
- CHIRPS/ARCO: sem resolução DNS.
- Rótulo precoce/médio/tardio: **não existe** no dicionário oficial; não
  atribuir.

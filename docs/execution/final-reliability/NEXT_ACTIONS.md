# Fechamento — próximas ações

**Data:** 2026-11-14

## Prioridade 1 — fecha lacunas metodológicas abertas

### 1.1. Migrar os 6 manifestos restantes para `write_manifest`
`pam_quality_audit`, `climate_source_adjudication`, `independent_replication`,
`bootstrap_calibration`, `applied_inference`, `full_build_validation`.
Mecânico; a infraestrutura existe e está testada.

### 1.2. `null_imposed` na biblioteca (D129)
Corrigir `robust.wild_cluster_bootstrap_fast` para impor H0 quando o desenho tem
uma única coluna, ou marcar a função como deprecada e apontar para
`fast_bootstrap`. Hoje o nome promete o que não faz.

### 1.3. Wild bootstrap no relatório padrão
Todo resultado novo reporta WCR + CR1 e conclui apenas quando concordarem.

## Prioridade 2 — validação de fonte

### 2.1. Validar a agregação de janela contra INMET
O diário já foi comparado (627.381 pares). O que falta é comparar **a variável
que entra no modelo**: precipitação acumulada da janela, graus-dia da janela,
déficit da janela. Exige reconstruir a janela com INMET para os 215 municípios e
medir o desvio da exposição — não do clima diário.

### 2.2. Investigar o vento
r = 0,409 é o pior caso e não foi explicado. Suspeita: hora da observação vs
média diária. Afeta ET0 e, portanto, o déficit.

### 2.3. `Conley HAC` como sensibilidade
Não implementado. A exposição varia em UF×ano, mas correlação espacial residual
entre municípios vizinhos não foi testada.

## Prioridade 3 — consistência do build

### 3.1. Build completo com física histórica
Para provar equivalência bit a bit em 30.207 linhas (hoje provada em 14).
Custo ~11 min, nenhum risco.

### 3.2. Medir a magnitude do D124 no painel completo
Rodar o balanço de referência em 30.207 janelas e somar a diferença de excedente.
Só tem valor documental, já que nada publicado usa excedente.

## Prioridade 4 — expansão (só depois)

### 4.1. MG, conforme D119 e D126
Acrescenta **clusters** UF × ano, a única dimensão que compra precisão.
Não acrescentar municípios nas 7 UFs atuais: reduz o EP em < 1%.

## Bloqueios

| item | bloqueio |
|---|---|
| revisão acadêmica | exige autorização expressa; `SADEN-TCC` permanece congelada |
| validação contra ET0 de estação | INMET não publica ET0 |

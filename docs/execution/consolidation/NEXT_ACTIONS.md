# Consolidação técnica — próximas ações

**Data:** 2026-11-14

Ordenadas por relação risco/custo. Nenhuma delas é expansão científica.

---

## Prioridade 1 — curto prazo

### 1.1. Wild cluster bootstrap no fluxo oficial
**Por quê:** erro tipo I observado de 6%–10% onde se declara 5% (D125).
**O que:** incorporar `tools/calibrate_wild_bootstrap.py` ao relatório padrão de
inferência; reportar os dois p-valores; concluir só quando concordarem.
**Custo:** baixo. É o maior ganho metodológico por hora gasta.

### 1.2. Manifestos determinísticos
**Por quê:** o hash do manifesto muda entre execuções por causa de
`generated_at`, então o hash não serve como verificação de integridade.
**O que:** separar `content_hash` (sem campos voláteis) de `generated_at`.
**Custo:** baixo.

### 1.3. Build completo do pipeline canônico
**Por quê:** a equivalência foi provada em 14 de 2.425 municípios.
**O que:** rodar `--stage all` completo (~2 h) e comparar as 30.207 linhas.
**Custo:** tempo de máquina, nenhum risco.

## Prioridade 2 — médio prazo

### 2.1. Validar o clima contra estação
**Por quê:** os 627.381 registros INMET nunca foram usados. É a única forma
gratuita de testar a reaálise.
**O que:** para municípios com estação, comparar precipitação e temperatura
NASA POWER × INMET na janela agrícola.
**Custo:** médio. Muda o status do clima de "validado com ressalva" para
validado ou não.

### 2.2. Corrigir a ET0 em uma versão identificada
**Por quê:** `es(Tmean)` e o fator 0,4 no vento desviam da FAO-56.
**O que:** nova versão científica (V3.6 ou V4.0) que reconstrua ET0 e reexecute
as estimativas; comparar o que muda.
**Custo:** alto. **Não fazer sem autorização**, porque altera resultados.

### 2.3. Resolver ou aceitar o excedente (D124)
**Por quê:** a formulação de referência superestima excedente.
**O que:** ou corrigir em versão nova, ou remover `excess_*` do painel por não
ser usado.
**Custo:** baixo, se for remoção.

## Prioridade 3 — quando houver decisão de produto

### 3.1. Redação do contexto agroclimático
Escrever uma página com o texto exato antes de qualquer código de produto, e
submetê-la a revisão crítica. Ver `docs/product/PRODUCTIZATION_READINESS.md`.

## Prioridade 4 — expansão (só depois do acima)

### 4.1. MG, conforme D119
**Justificativa revisada:** acrescenta **clusters** UF × ano, a única dimensão
que ainda compra precisão (D126). Não por volume de municípios.

### 4.2. Não fazer
- mais municípios dentro das 7 UFs atuais (reduz EP em < 1%);
- novas hipóteses de temperatura com o desenho atual (MDE proibitivo);
- novo contraste regional sem variação dentro da unidade (não identificado).

## Bloqueios

| item | bloqueio |
|---|---|
| bundle completo com dados | derivados somam 6,3 GB e têm licença de terceiros |
| build completo | tempo de máquina (~2 h), não é bloqueio técnico |
| revisão acadêmica | depende de autorização expressa do usuário |

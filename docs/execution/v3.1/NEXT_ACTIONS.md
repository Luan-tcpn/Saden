# V3.1 — NEXT ACTIONS (recomendações para V3.2)

## Prioridade 1 — inclinação climática heterogênea (não testada na V3.1)

A V3.1 mostra que o valor climático do milho está **concentrado em PR**
(−607,4 kg/ha contra a média da UF), é moderado em BA/GO e **negativo** em
MS/MT/RS. A V3.1 testou apenas modelos com inclinação **comum** (com ou sem
tendência espacial); a heterogeneidade de inclinação não foi estimada.

Hipótese a pré-registrar: um modelo hierárquico (intercepto e inclinação por UF,
com encolhimento parcial) generaliza melhor que a inclinação comum no TE.

Cuidados obrigatórios:
* seleção de hiperparâmetros somente no treino;
* comparar com M1 e M2 nas mesmas linhas (pareado, bootstrap de bloco);
* não apresentar UF com n pequeno como região validada (BA tem 106 linhas);
* não transformar ganho preditivo em causalidade.

## Prioridade 2 — vizinhos históricos: reduzir a arbitrariedade da vizinhança

A grade de M1c foi fixada e reportada, mas a escolha ideal de raio/decaimento
ficou aberta. Próximo passo correto: escolher a configuração por validação
**interna dentro do treino** (nunca por TE) e reportar a curva de cobertura ×
erro. Também vale contrastar M1c com M2 num desenho pareado, o que a V3.1 não
fez (conjuntos de linhas diferentes).

## Prioridade 3 — janela fenológica separada da janela ZARC

A V3.1 manteve a janela ZARC de semeadura para **todas** as variáveis, inclusive
graus-dia. Isso é documentado, mas é uma aproximação: graus-dia até maturação
não é a mesma coisa que graus-dia na janela de semeadura. Se houver fonte com
datas de plantio/colheita observadas (PAM não traz), testar uma janela
fenológica específica como cenário — sem substituir a atual.

## Prioridade 4 — expansão de cobertura

O painel cobre 5–6 UFs de 27. Qualquer expansão exige diagnóstico prévio de
PAM, geometria, clima, solo, ZARC e comparabilidade temporal. Não expandir por
conveniência.

## Bloqueios que permanecem

* ERA5-Land: sem credencial CDS. CHIRPS/ARCO: DNS. Não há caminho técnico novo;
  não repetir tentativas.
* CAD: licença CC BY-NC 3.0 BR — não versionar rasters nem redistribuir.

## Não reabrir

* NDVI como preditor (sem hipótese nova).
* Inversão de temperatura da soja por classe de ciclo (retratada na V2.9).
* CAD bruta como preditora (D98).
* Tendência espacial global (D102) como modelo principal.

# V3.4 — NEXT ACTIONS

## Concluído

* Classificação regional em fonte oficial, congela antes de qualquer estimativa
  (D112).
* Mapeamento municipal parseado (4.286 pares; hash registrado).
* Diagnóstico de identificação medido antes dos resultados: região aninhada em UF
  (Cramér's V = 1,000).
* Pré-registro com precedência explícita de E sobre B.
* Contraste preditivo e associativo calculados, com IC duplo e 6 figuras.
* Estabilidade: LOO-UF, LOO-ano, dentro de estado.
* Sensibilidades: 5 classificações, 3 ponderações, 10 decis de déficit.
* Diagnóstico de cobertura territorial com denominador oficial.

## Rejeitado

* **Modelo regional do bloco hídrico** — não identificável (D113) e a fronteira
  não organiza o fenômeno (D114).
* **Replicação na soja** — instável por ano e por suporte.
* **Replicação na milho 2ª** — sinal inverte no leave-one-UF-out.
* **"SUL = PR + RS, Cerrado = resto"** como afirmação científica — é um contraste
  entre grupos de estados, não um efeito regional.
* **Novas variáveis, limiares ou interações regionais** — a especificação não é o
  gargalo (D108 + D114).

## Inconclusivo

* O achado **descritivo** é robusto (5 classificações, 3 ponderações, 9/10 decis,
  LOO estável no milho), mas permanece **sem identificação** e **sem validação
  independente**. Fica registrado como descrição, não como explicação.
* O teste dentro do estado mais informativo (MS, MRS 2 × 3) aponta na mesma
  direção (+222 kg/ha/100 mm) mas não é significativo (p = 0,110) com 166
  observações em um dos braços.

## O que faria a hipótese avançar (e quanto custa)

**Uma UF com municípios em MRS 1 e MRS 3/4.** Só **SP** satisfaz (645 municípios
indicados: RE 103 é MRS 1, oeste paulista é MRS 3). Sem isso, o contraste
permanece um contraste entre estados.

Custo: baixar PAM de SP, clima diário NASA POWER na janela ZARC corrigida, CAD de
SP (ou cenário declarado), e **reestimar os baselines** — porque M0/M1 mudam de
composição e os resultados da V3.0–V3.4 deixam de ser diretamente comparáveis.

## Prioridades para V3.5

1. **SP**, pelos critérios de aceitação do diagnóstico §7. É a única aquisição que
   ataca a identificação.
2. **MG** (852 municípios, MRS 2 e 3), em segundo lugar: separa transição de
   Cerrado dentro de UF.
3. **SC** (295, MRS 1): aprofunda o grupo Sul, hoje sustentado por RS + PR parcial.
4. Reestimar M0/M1/M2 no painel ampliado e **reclassificar** as conclusões
   anteriores como "não comparáveis sem reestimação".

## Não reabrir

* Forma funcional do bloco hídrico (D108) e duração × intensidade (D109).
* Heterogeneidade de inclinações por UF como modelo operacional (D105/D114).
* Tendência espacial global (D102); CAD bruta como preditora (D98).
* Associações meteorológicas brutas da V2.7 (D110).

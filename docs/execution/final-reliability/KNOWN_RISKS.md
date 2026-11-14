# Fechamento — riscos conhecidos

**Data:** 2026-11-14

## Riscos científicos

| # | risco | gravidade | estado |
|---|---|---|---|
| R1 | p-valores CR1 anti-conservadores | **alta** | **mitigado**: WCR calibrado e aplicado; 0 resultados inverteram |
| R2 | ET0 fora da convenção FAO-56 | baixa | **resolvido**: net +0,54%; corrigido no pipeline |
| R3 | excedente superestimado (D124) | baixa | **resolvido** no módulo corrigido; nada publicado depende |
| R4 | clima não validado na agregação de janela | **alta** | **não mitigado** — diário comparado, janela não |
| R5 | milho 2ª usa rendimento anual | média | limitação da fonte, não resolvível |
| R6 | poder insuficiente para temperatura | média | declarado; MDE 203–433 kg/ha/°C |
| R7 | cobertura de 48,3% do território indicado | média | declarado |
| R8 | vento INMET com r = 0,409 sem explicação | média | aberto |

## Riscos de dados

| # | risco | gravidade | estado |
|---|---|---|---|
| R9 | revisões da PAM não auditáveis | média | sem vintage; requer 2ª extração no tempo |
| R10 | 2.020 linhas INMET no painel base | baixa | **rastreadas**; contrato impede reuso acidental |
| R11 | latitude exportada só para SP | baixa | contornado pelo centróide |
| R12 | 545 municípios do cadastro sem linha analítica | média | **medido e explicado** (77,5%) |

## Riscos de engenharia

| # | risco | gravidade | estado |
|---|---|---|---|
| R13 | `null_imposed` ignorado com k=1 | **alta** (silencioso) | **documentado** (D129); caminho correto existe |
| R14 | `null_policy="auto"` escolhe p pelo resultado | **alta** | **documentado**; proibido em análise nova |
| R15 | 6 manifestos ainda com timestamp no conteúdo | baixa | migração pendente |
| R16 | build completo só em blocos | baixa | merge validado; determinístico |
| R17 | escrita em segundo plano instável no launcher | baixa | contornado com execução em primeiro plano |

## O risco que mais preocupa

**R4 — a agregação não foi validada.** A comparação NASA × INMET foi feita no
diário. O modelo usa **acumulados de janela** de 2 a 9 meses. Erro diário de
3,1 mm tem parte cancelada ao acumular, mas ninguém mediu quanto. Enquanto isso
não for feito, a afirmação honesta é "a exposição é consistente com a reanálise",
não "a exposição é consistente com o clima observado".

**R13/R14 são o segundo.** Uma função que promete impor a hipótese nula e não
impõe, e uma política que escolhe o p-valor depois de ver o resultado, são
exatamente o tipo de defeito que produz inferência confiante e errada. Ambos
estão documentados e fora do caminho canônico, mas continuam no repositório.

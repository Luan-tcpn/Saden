# V3.3 — NEXT ACTIONS

## Concluído

* Auditoria de integridade (V1.1, `main`, V3.0–V3.2, bundles) antes de alterar.
* Pré-registro com H3 declarada não testável **antes** dos resultados.
* Descritores de estresse (duração, sequência, armazenamento mínimo, ETR/ETP) na
  biblioteca, não em script.
* Auditoria de dependência que eliminou variáveis redundantes antes do desenho.
* 7 modelos × 3 culturas em TE, com comparação pareada e IC duplo.
* Auditoria de 45 hipóteses históricas com reprodução exata dos coeficientes.
* 17 testes novos; 427/427 na suíte.

## Rejeitado

* **Bloco hídrico como melhoria preditiva** — ΔMAE +1,33 no milho; nenhuma
  variante melhora (D108).
* **Forma quadrática** — piora +51 no milho e +195 no milho 2ª.
* **Graus-dia como bloco adicional** — não acrescenta (p = 0,961).
* **Interação água × calor** — +6,15 (IC exclui zero, pior) e colinearidade 0,84.
* **Associações meteorológicas brutas da V2.7** — 0 de 4 sobrevivem a Holm.
* **Interação por grupo de ciclo da V2.9** — 0 de 1 sobrevive.

## Inconclusivo

* **Associação do bloco hídrico**: p = 0,038 bruto, Holm 0,076. Não é evidência
  confirmatória, mas também não é nulo. Precisa de família pré-registrada maior
  ou de mais dados para resolver.
* **Não linearidade no milho**: sobrevive ao Holm (0,041) como associação e
  **piora** a previsão. Associação real, utilidade preditiva nula.
* **Milho 2ª safra**: nenhuma das cinco definições de déficit tem associação
  detectável (p duplo 0,47–0,86). Com 31 clusters UF×ano, é poder limitado, não
  ausência demonstrada.
* **Calor extremo no milho**: p duplo 0,017, mas não sobrevive ao Holm de 21 e
  não foi pré-registrado como hipótese própria.

## Hipótese que resta (a única)

**Gradiente regional do bloco hídrico**: ajuda em PR e RS, atrapalha no Cerrado,
nas duas culturas de verão (milho: −33,8 / −53,1 contra +4,1 a +173,5; soja repete
o sinal em escala menor). Não foi pré-registrado; é exploratório.

Teste adequado na V3.4:
1. partição **a priori** Sul vs Cerrado, definida por critério agronômico
   publicado (não pelos dados);
2. contraste pareado dentro de cada partição, IC por UF×ano;
3. pré-registro com família declarada;
4. se não sobreviver, encerrar o assunto.

## Limitações que dependem de novos dados

* **Balanço diário** seria necessário para testar duração × intensidade (D109).
  Não implementar sem evidência de que importaria.
* **Mais UFs** é o único caminho para as perguntas de generalização. Exige
  diagnóstico de PAM, geometria, clima, solo e ZARC (V3.1 §15) — não é um passo
  automático.
* ERA5-Land / CHIRPS seguem bloqueados.

## Prioridades para V3.4

1. **Teste regional do bloco hídrico** (descrito acima). É a única hipótese que a
   V3.3 deixou viva.
2. **Ampliar cobertura territorial** — depois de (1), porque é o gargalo real:
   toda conclusão do projeto está limitada a 5–6 UFs.
3. **Não** adicionar variáveis climáticas, limiares ou formas funcionais. A V3.3
   mostrou que a especificação não é o gargalo.

## Não reabrir

* NDVI como preditor (sem hipótese nova).
* Inversão de temperatura da soja por classe de ciclo (retratada na V2.9 e agora
  sem nem p significativo).
* CAD bruta como preditora (D98).
* Tendência espacial global (D102).
* Inclinações heterogêneas por UF como modelo operacional (D105/D107).

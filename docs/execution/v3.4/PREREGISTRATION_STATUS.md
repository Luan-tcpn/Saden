# V3.4 — STATUS DO PRÉ-REGISTRO

Documento de controle: confronta o que foi congelado com o que foi executado.

**Pré-registro:** `docs/V3_4_REGIONAL_WATER_PREREGISTRATION.md` (congelado 2026-11-14, antes das estimativas).
**Classificação:** `docs/V3_4_REGIONAL_CLASSIFICATION_PROTOCOL.md` (congelada antes do pré-registro).

## 1. Desvios do pré-registro

| # | item | previsto | executado | classificação |
|---|---|---|---|---|
| 1 | análise por decis de déficit | prevista como teste de suporte (§7.4) | executada, mas **a primeira implementação tinha bug de chave** (município só, não município-ano) | **erro corrigido**, não desvio de desenho |
| 2 | análise dentro de estado | prevista (§7.3) | executada; a primeira versão usou 3 dobras espaciais em vez de 5 | **inconsistência de protocolo corrigida** |
| 3 | família confirmatória | 2 testes, milho, Holm | executado exatamente | sem desvio |
| 4 | IC do contraste | UF×ano (primário) + bloco (sensibilidade) | executado exatamente | sem desvio |
| 5 | precedência de E sobre B | fixada antes | aplicada | sem desvio |

**Nenhum desvio de desenho.** Os dois itens acima foram erros de implementação,
detectados por revisão e corrigidos antes de entrar em qualquer relatório final;
os números reportados são os da versão corrigida.

## 2. Regra de decisão aplicada

O pré-registro fixou, em §6:

> "1. **E tem precedência sobre B**: se não houver nenhuma UF com municípios nos
> dois grupos, a alegação de 'efeito regional independente de estado' é não
> identificável, mesmo que D seja grande."

Resultado medido: **Cramér's V = 1,000** nas três culturas, **nenhuma** UF nos
dois grupos → **Nível E**.

O D do milho é grande e estável (sobrevive a LOO-UF e LOO-ano), o que sob a regra
2 seria Nível B. A precedência de E foi aplicada como escrito. **Sem essa regra
estar pré-registrada, o resultado teria sido classificado como B** — e essa é
exatamente a razão de tê-la fixado antes.

## 3. Status de independência (declarado antes dos resultados)

| item | estado |
|---|---|
| amostra não examinada usada na descoberta | **não existe** |
| confirmação independente alegada | **não** |
| rótulo usado | "reanálise protocolada de achado exploratório" |
| p-valores interpretados como confirmação definitiva | **não** |

## 4. Família confirmatória executada

| teste | p bruto | Holm | decisão |
|---|---:|---:|---|
| preditivo D (milho) | 0,0010 | 0,0010 | rejeita H0 |
| associativo interação (milho) | 1,8×10⁻⁶ | 3,6×10⁻⁶ | rejeita H0 |

Os dois rejeitam. **Isso não eleva a classificação para A ou B**: a hipótese nula
testada é "não há diferença entre os grupos", e não "a região é o mecanismo". A
diferença existe e é grande; o que não é identificável é a atribuição à região
(§2). A distinção está explícita no relatório principal §11.

## 5. O que o pré-registro impediu

1. Escolher a fronteira depois de ver o resultado (congelada antes).
2. Incluir MRS 2 no grupo conveniente (excluída por regra, não por resultado).
3. Promover o achado a confirmação independente (declarado impossível antes).
4. Chamar B de A usando o D grande (precedência de E fixada antes).
5. Escolher a ponderação que favorece (três reportadas).
6. Testar classificações até uma dar significância (cinco pré-listadas; todas
   reportadas, todas com o mesmo sinal).

## 6. Itens não executados e por quê

| item | motivo |
|---|---|
| validação em amostra independente | inexistente nos dados; declarado |
| participação nacional na produção | PAM do repositório cobre 6 UFs |
| modelo regional regularizado | sem identificação, não faria sentido estimar |
| classificação oficial de milho equivalente | não existe nas fontes consultadas |

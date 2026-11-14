# Como usar os alertas de preço

Guia rápido do recurso de **monitoramento de preço** do SADEN.

---

## 1. O que o recurso faz

Você escolhe **uma série de preço**, define **uma condição** e o SADEN registra
um evento quando o preço observado satisfizer essa condição.

O alerta serve para você **não precisar abrir o app para conferir o preço**: ele
é avaliado quando o SADEN atualiza os preços e quando você clica em
**Verificar agora**.

## 2. Antes de começar: o que é cada série

Cada série tem um identificador fixo, por exemplo `yahoo:ZS=F:brl:sc60`:

| parte | significado |
|---|---|
| `yahoo` | fonte da cotação (Yahoo Finance) |
| `ZS=F` | contrato futuro (aqui, soja em Chicago) |
| `brl` | moeda do valor (real) |
| `sc60` | unidade (saca de 60 kg; `lp` = libra-peso) |

**Importante:** é uma **referência internacional convertida pelo dólar PTAX**.
Não é o preço que você recebe na sua região — frete, base local, prêmio
portuário e custo de exportação não estão incluídos.

## 3. Criar um alerta

1. Abra o SADEN e clique em **Alertas** no menu.
2. Em **Série de preço**, escolha a commodity/mercado.
   - O painel abaixo mostra: mercado, instrumento, fonte, unidade, última
     observação e se o dado está **atualizada** ou **desatualizada**.
3. Em **Condição**, escolha:
   - **Preço maior ou igual a** — avisa quando o preço subir até o limite;
   - **Preço menor ou igual a** — avisa quando o preço cair até o limite.
4. Digite o **limite** na unidade mostrada ao lado do campo.
5. (Opcional) Dê um **rótulo** — ex.: "vender soja".
6. Clique em **Criar alerta**.

### Se o preço já estiver além do limite

O SADEN avisa **antes** de criar:

> A última observação já satisfaz a condição: Soja: R$ 154,88 R$/sc 60kg em
> 2026-11-13. Se criar agora, o alerta dispara na primeira verificação e ficará
> como "disparado" até você reativar. Criar mesmo assim?

Escolha conscientemente: isso evita a surpresa de um alerta que "dispara
sozinho" logo depois de criado.

## 4. Acompanhar

Em **Meus alertas** você vê, por linha:

- **Rótulo**, **Série**, **Condição** e **Limite**;
- **Último preço** e a data da observação;
- **Estado**: `ativo`, `pausado` ou `disparado`;
- Ações: **Pausar/Reativar** e **Excluir**.

Em **Eventos disparados** aparecem apenas os disparos reais, com data do evento,
preço observado, data da observação e se você já leu.

O contador ao lado de "Meus alertas" mostra quantos eventos novos existem.

## 5. Como o alerta dispara

- Dispara **uma vez** e passa para o estado **disparado**.
- Depois disso ele **não** volta a disparar até você clicar em **Reativar**.
- Se você reativar, ele pode disparar de novo — mas **uma vez por observação**:
  a mesma cotação nunca gera dois eventos.
- Uma observação com **mais de 7 dias** é considerada desatualizada e **não
  dispara**, mesmo que satisfaça a condição.

## 6. Quando a avaliação acontece

| situação | avalia? |
|---|---|
| você abre o painel / consulta preços (cache expirado) | **sim** |
| você clica em **Verificar agora** | **sim** |
| você deixa o app aberto e o preço não atualiza | não |
| servidor desligado | **não** |

O SADEN **não** promete monitoramento em tempo real nem funcionamento com o
servidor desligado. A avaliação depende de os preços serem efetivamente
atualizados.

## 7. Perguntas frequentes

**Meu alerta não disparou. Por quê?**
Verifique: (a) o estado é `ativo`? (b) a série está "atualizada"? (c) o preço
realmente cruzou o limite? Se o dado estiver desatualizado, o alerta espera uma
observação nova.

**Posso receber por e-mail?**
Não nesta versão. A notificação é interna.

**O preço mostrado é o que eu recebo?**
Não. É referência internacional convertida por PTAX. Para preço físico da sua
região, o SADEN declara explicitamente que não há fonte automatizada (CEPEA e
CONAB não têm API pública).

**Por que não existe alerta de chuva?**
A versão anterior tinha um esboço. Ele dependia de previsão de 7 dias (não de
observação) e não é um alerta de preço. Nesta release, alertas são apenas de
preço.

**Posso ter várias condições na mesma série?**
Sim: crie um alerta para cada condição (ex.: um `≥` para venda e um `≤` para
compra).

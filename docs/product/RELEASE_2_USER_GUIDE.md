# Alertas de preço — monitoramento automático

Guia do usuário (Release 2).

---

## 1. O que mudou

Antes, o SADEN só conferia seus alertas quando você abria a página ou clicava em
"Verificar agora". Agora existe um **monitoramento automático**: um processo do
SADEN verifica os preços por conta própria, todos os dias úteis, no fim da tarde.

O que continua valendo:

- o alerta dispara **uma vez**;
- depois fica **disparado** até você reativar;
- a mesma cotação **nunca** gera dois avisos;
- dado com mais de 4 dias não dispara.

## 2. O que o monitoramento faz (e não faz)

**Faz:** consulta as séries que têm alertas ativos, uma vez por dia útil, e
avalia as suas condições.

**Não faz:**

- não funciona com o servidor desligado;
- não é tempo real — a cotação é de **fechamento diário**;
- não avisa por e-mail nem por celular (o aviso é dentro do SADEN);
- não acompanha fins de semana e feriados: o mercado está fechado, e isso não é
  atraso.

## 3. O aviso no topo da tela

Na página **Alertas** há uma faixa que mostra o estado real:

| faixa | significado |
|---|---|
| verde — "Monitoramento automático ativo" | está funcionando; mostra a última verificação e a próxima |
| amarela — "ativo com falhas recentes" | está rodando, mas a última verificação falhou |
| vermelha — "temporariamente indisponível" | o monitoramento parou; o SADEN avisa em vez de fingir que está tudo bem |

Se a faixa estiver vermelha, seus alertas continuam salvos — eles serão avaliados
quando o monitoramento voltar.

## 4. Como criar (igual, mas com mais informação)

1. **Alertas** → escolha a **série de preço**.
2. O painel mostra mercado, fonte, unidade, última cotação e se o dado está
   **atualizado**, **atrasado**, **aguardando** ou com **erro na fonte**.
3. Escolha a condição (≥ ou ≤) e digite o limite na unidade mostrada.
4. Crie. Se o preço atual já estiver além do limite, o SADEN explica antes.

## 5. Quando serei avisado

- A verificação automática acontece **ao fim da tarde, em dias úteis**.
- Se a cotação do dia satisfizer sua condição, o evento aparece em **Eventos
  disparados** na próxima vez que você abrir o SADEN.
- Você também pode forçar uma verificação com **Verificar agora** (máximo de 20
  por 10 minutos, por conta).

## 6. O que NÃO é preço da sua região

As séries são **referências internacionais** (futuros em Chicago/Nova York)
convertidas pelo dólar PTAX. **Não são o preço que você recebe na fazenda** — não
incluem frete, base local, prêmio portuário nem custo de exportação.

## 7. Enviar retorno

No fim da página **Alertas** há um campo para relatar problema, sugestão,
dificuldade ou utilidade. É opcional e não pede dado pessoal além da sua conta.
É por ali que o SADEN decide o que melhorar.

## 8. Perguntas frequentes

**Por que meu alerta não disparou?**
Confira, nesta ordem: a faixa de monitoramento está verde? a série está
"atualizada"? o preço realmente cruzou o limite? o alerta está **ativo**?

**Preciso deixar a página aberta?**
Não. O monitoramento roda no servidor. Mas o servidor precisa estar ligado.

**Recebo aviso com o SADEN fechado?**
Não por e-mail nem celular. O evento fica registrado e você o vê ao voltar.

**Existe monitoramento à noite ou de hora em hora?**
Não. A fonte publica fechamento diário; verificar mais vezes não traria dado novo.

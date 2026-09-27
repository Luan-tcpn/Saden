# SADEN G6 — Investigação de fonte regional real (2026-09-27)

> Verificação atualizada pós-D26 (2026-09-15). Métodos: páginas oficiais
> acessadas em 2026-09-27, termos de contratação CEPEA, metodologia IMEA,
> documentação B3. Nenhum CAPTCHA/WAF contornado; nenhum scraping executado.
> Sem schema, sem código, sem dados artificiais.

## Matriz final

| Fonte | Commodities (5 do SADEN) | Região | Tipo de preço | Unidade | Frequência | Histórico | API/download | Autenticação | Licença | Automação legítima | Cobertura | Compat. SADEN | Limitações | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CONAB precosiagroweb | todas (112+ produtos, filtrável) | UF × nível de comercialização | preço médio semanal/mensal físico | varia por produto | semanal/mensal | desde 2014 | XLS/HTML/PDF manual | CAPTCHA por consulta (confirmado ao vivo) | reprodução com citação; comercialização proibida | NÃO (exige CAPTCHA) | nacional por UF | alta (se acessível) | gate CAPTCHA; granularidade UF, não município | NÃO AUTOMATIZÁVEL |
| CEPEA indicadores | soja/milho/café (módulo Grãos) + demais módulos | praças/indicadores CEPEA | indicador físico regional | R$/sc etc. | diária (fechamento após 19h) | sim (série do indicador) | REST JSON `api.cepea.org.br`, 50 req/min | contrato + chave | contrato FEALQ; site CC BY-NC 4.0 | SIM, mediante contratação | por módulo | alta | R$ 11.000 (Grãos) / R$ 22.300 (Completo); sem credencial acadêmica conhecida | VIÁVEL COM CONTRATAÇÃO |
| IMEA | soja, milho, algodão (3/5; sem café/trigo) | MT (20 municípios p/ milho; macrorregiões) | preço ao produtor físico (compra, sem tributos) | R$/sc 60kg | diária | série histórica existe (endpoint não documentado) | site público + API de frontend não documentada | portal com login; API sem docs oficiais | restritiva (redistribuição exige autorização escrita — a confirmar em contato direto) | NÃO (sem autorização) | só MT | média (MT-only; sem café/trigo) | 1 estado; licença; sem docs | PARCIAL |
| B3 | milho (CCM), café (ICF/CNL), soja (SJC/SOY) | — (bolsa) | futuro (liquidação financeira; CCM referencia índice Campinas) | R$/sc, US$/sc | pregão | sim | market data pago (vendors) | contrato/vendor | paga | n/a | nacional (bolsa) | nenhuma (futuro ≠ físico) | semântica errada para regional | INCOMPATÍVEL |
| ANTT/CKAN | — | — | — | — | — | — | só multas (D26, sem mudança apurada) | — | — | — | — | nenhuma | sem fonte de frete estruturada | INCOMPATÍVEL |
| Pacotes scrapers (ex.: agrobr) | — | — | — | — | — | — | scraping não autorizado | — | zona cinzenta | NÃO (sem autorização clara) | — | nenhuma | não é fonte; é contorno | INCOMPATÍVEL |

## Portas futuras concretas (não ações)

1. CEPEA: verificar convênio/acesso acadêmico ESALQ (preço atual incompatível com TCC sem financiamento).
2. IMEA: contato formal solicitando autorização escrita p/ redistribuição (cobre 3/5 commodities em MT).
3. CONAB: reavaliar somente se o precosiagroweb ganhar acesso sem CAPTCHA ou download em massa documentado.

## Conclusão

**NENHUMA FONTE REGIONAL REAL ADEQUADA ENCONTRADA PARA INTEGRAÇÃO NESTE MOMENTO.**
G6 confirma D26 no resultado, com evidências novas e mais precisas (termos e
valores CEPEA; IMEA como candidato parcial inédito; CAPTCHA CONAB reconfirmado
ao vivo; nuance B3/Campinas). Nenhum schema criado; Price Reference Engine
inalterado; proxy Yahoo×IBGE segue proibido. Sem D39 (nada a decidir).

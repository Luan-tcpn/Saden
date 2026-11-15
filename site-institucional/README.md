# SADEN — site institucional

Página estática de apresentação do SADEN v1.2.3. **Não** é a aplicação: não tem
backend, banco, login, API ou qualquer dependência do servidor do SADEN.

## Estrutura

```text
site-institucional/
├── public/                     ← única pasta publicada
│   ├── index.html              página única, 8 seções
│   ├── assets/
│   │   ├── css/site.css        identidade herdada do produto
│   │   ├── js/site.js          menu móvel + revelação (sem dependências)
│   │   ├── img/                logo, 3 fotos do produto, captura real da tela
│   │   └── icons/favicon.svg
│   ├── robots.txt
│   ├── sitemap.xml
│   ├── _headers                CSP, HSTS, cache imutável de /assets
│   └── _redirects
├── README.md
└── DEPLOY.md
```

## Conteúdo e precisão

Todo o texto foi escrito a partir do código e da documentação da v1.2.3.
Afirmações deliberadamente **ausentes** porque não são verdadeiras:

- CEPEA/CONAB como fontes ativas (não há API validada);
- preço físico brasileiro (as séries são referência internacional convertida);
- notificação por e-mail/WhatsApp/SMS (alertas vivem no painel);
- garantia de previsão, acurácia universal ou eliminação de risco;
- clientes, parceiros ou usuários inexistentes;
- formulário de contato (não existe backend para tratá-lo).

A única captura de tela é real, feita do sistema em execução (`tela-entrada.png`).
Não há dados de usuário visíveis.

## Identidade visual

Paleta e tipografia herdadas de `frontend/css/styles.css`:
`#1a3a24` (verde profundo), `#2c5f3a`, `#f4f6f1` (fundo), `#22301f` (tinta),
`#9a6b1e` (âmbar). Sem gradientes, sem bibliotecas de UI, sem fontes externas —
o site é HTML + CSS + 60 linhas de JS.

## Verificação executada

| item | resultado |
|---|---|
| overflow horizontal em 320/360/390/414/768/1024/1366/1920 px | **0 ofensores** |
| dependência de backend | nenhuma |
| requisições externas (fontes, CDNs, analytics) | nenhuma |
| peso total de `public/` | ~1,1 MB (dominado pelas imagens) |
| acessibilidade | skip link, hierarquia h1→h3, foco visível, alt, `aria-*` no menu, contraste AA |
| SEO | title, description, canonical, OG/Twitter, sitemap, robots |

## Pré-visualização local

```powershell
start "C:\caminho\Saden_AgroClima\site-institucional\public\index.html"
```

Funciona por `file://` porque não há rotas nem fetch.

## Publicação

Ver `DEPLOY.md`.

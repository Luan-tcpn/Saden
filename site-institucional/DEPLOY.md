# Deploy — Cloudflare Pages (plano Free)

**Estado: preparado, não publicado.** Não há conta Cloudflare autenticada neste
ambiente, e publicar exigiria autorização sobre a conta e sobre o repositório.
Os passos abaixo são os que faltam.

---

## 1. O que já está pronto

| item | valor |
|---|---|
| Diretório de publicação | `site-institucional/public` |
| Build command | nenhum (sitio estático) — use `exit 0` |
| Output directory | `public` |
| Root directory | `site-institucional` |
| Framework preset | None |
| Node | não é necessário |
| Funções/Workers | não usados |
| Plano | Free |

O plano Free do Cloudflare Pages cobre sites estáticos com builds e requisições
dentro dos limites publicados em
<https://developers.cloudflare.com/pages/platform/limits/>. Este site não usa
Functions, nem KV, nem D1 — portanto não consome nenhum limite além de banda e
número de builds.

## 2. Publicar com Git integration (recomendado)

1. Cloudflare Dashboard → **Workers & Pages** → **Create** → **Pages** →
   **Connect to Git**.
2. Autorizar o GitHub e escolher o repositório `Luan-tcpn/Saden`.
   > A integração funciona com repositório **privado**; não torne o repositório
   > público para publicar.
3. Configuração do projeto:
   - **Project name:** `saden-institucional` → URL `saden-institucional.pages.dev`
   - **Production branch:** `main`
   - **Root directory (advanced):** `site-institucional`
   - **Build command:** `exit 0`
   - **Build output directory:** `public`
4. **Save and Deploy**.

A partir daí, cada push em `main` republica; cada outro branch gera um preview
com URL própria. Preview não substitui produção.

> Atenção: um projeto criado por Git integration **não** pode ser convertido
> depois para Direct Upload. Escolha o modo de forma deliberada.

## 3. Publicar por Direct Upload (alternativa sem Git)

```bash
npx wrangler pages deploy site-institucional/public --project-name saden-institucional
```

Requer `wrangler` autenticado (`npx wrangler login`). Sem upload contínuo: cada
atualização é um novo upload manual.

## 4. Depois do primeiro deploy

1. Abrir `https://saden-institucional.pages.dev/` e conferir visual e console.
2. **Atualizar as URLs absolutas** — elas hoje apontam para o subdomínio previsto:
   - `index.html`: `canonical`, `og:url`, `og:image`
   - `public/robots.txt` (linha `Sitemap:`)
   - `public/sitemap.xml` (`<loc>`)
   Se o projeto for criado com outro nome, a URL muda e esses campos precisam
   acompanhar.
3. Verificar os headers: `curl -I https://saden-institucional.pages.dev/` deve
   mostrar `content-security-policy`, `strict-transport-security` e
   `x-content-type-options`.
4. Conferir que `/assets/...` responde com `cache-control: public, max-age=31536000, immutable`.
5. Rodar um teste de responsividade no navegador (DevTools) em 390 e 1440 px.

## 5. Atualizar o site

Com Git integration: `git push` em `main`. O build leva poucos segundos porque
não há compilação.

Se o conteúdo mudar de forma relevante, atualize também `sitemap.xml` (a data de
`lastmod` é opcional) e a versão citada na ficha do projeto.

## 6. Custo

Zero. Nenhum recurso pago é usado: sem domínio próprio, sem Functions, sem
analytics, sem formulário, sem banco.

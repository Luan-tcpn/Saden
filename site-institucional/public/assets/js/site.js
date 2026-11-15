// Menu móvel, revelação discreta e ano do rodapé. Sem dependências.
(() => {
  const botao = document.querySelector('.menu-btn');
  const menu = document.querySelector('#menu');

  if (botao && menu) {
    botao.addEventListener('click', () => {
      const aberto = botao.getAttribute('aria-expanded') === 'true';
      botao.setAttribute('aria-expanded', String(!aberto));
      botao.setAttribute('aria-label', aberto ? 'Abrir menu' : 'Fechar menu');
      menu.dataset.aberto = String(!aberto);
    });

    // Fecha ao navegar (âncora) e ao apertar Escape.
    menu.addEventListener('click', (evento) => {
      if (evento.target.closest('a')) {
        botao.setAttribute('aria-expanded', 'false');
        menu.dataset.aberto = 'false';
      }
    });
    document.addEventListener('keydown', (evento) => {
      if (evento.key === 'Escape') {
        botao.setAttribute('aria-expanded', 'false');
        menu.dataset.aberto = 'false';
        botao.focus();
      }
    });
  }

  // Revelação progressiva: só ativa se o navegador suportar e o usuário aceitar movimento.
  const semMovimento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const alvos = [...document.querySelectorAll('.bloco, .item, .cartao, .mini')];
  if (!semMovimento && 'IntersectionObserver' in window && alvos.length) {
    alvos.forEach((el) => el.classList.add('reveal'));
    const observador = new IntersectionObserver((entradas) => {
      for (const entrada of entradas) {
        if (entrada.isIntersecting) {
          entrada.target.classList.add('visivel');
          observador.unobserve(entrada.target);
        }
      }
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.15 });
    alvos.forEach((el) => observador.observe(el));
  }
})();

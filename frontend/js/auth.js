'use strict';
// Sessão + roteador público: / (landing), /login, /register, /reset, /dashboard.
// Usuário autenticado em rota pública é levado ao app; sem token, /dashboard volta à landing.
(function () {
  const Api = () => window.SadenApi;

  function views() {
    return {
      landing: document.getElementById('view-landing'),
      auth: document.getElementById('view-auth'),
      app: document.getElementById('view-app'),
    };
  }

  function showOnly(name) {
    const v = views();
    v.landing.classList.toggle('hidden', name !== 'landing');
    v.auth.classList.toggle('hidden', name !== 'auth');
    v.app.classList.toggle('hidden', name !== 'app');
  }

  function setError(id, msg) {
    const el = document.getElementById(id);
    el.textContent = msg || '';
    el.classList.toggle('hidden', !msg);
  }

  function setOk(id, msg) {
    const el = document.getElementById(id);
    el.textContent = msg || '';
    el.classList.toggle('hidden', !msg);
  }

  function authTab(which) {
    const login = which !== 'register';
    document.getElementById('tab-login').classList.toggle('active', login);
    document.getElementById('tab-register').classList.toggle('active', !login);
    document.getElementById('form-login').classList.toggle('hidden', !login);
    document.getElementById('form-register').classList.toggle('hidden', login);
    document.getElementById('form-forgot').classList.add('hidden');
    document.getElementById('form-reset').classList.add('hidden');
  }

  function go(path) {
    if (location.pathname !== path) history.pushState({}, '', path);
    route();
  }

  async function route() {
    const path = location.pathname;
    const token = Api().getToken();
    if (token) {
      try {
        const { user } = await Api().me();
        document.getElementById('user-label').textContent = `${user.name} (${user.email})`;
        showOnly('app');
        if (path !== '/dashboard') history.replaceState({}, '', '/dashboard');
        await window.SadenApp.init();
        return;
      } catch {
        Api().setToken(null);
      }
    }
    if (path === '/login' || path === '/register') {
      showOnly('auth');
      authTab(path === '/register' ? 'register' : 'login');
    } else if (path === '/reset') {
      showOnly('auth');
      authTab('login');
      document.getElementById('form-login').classList.add('hidden');
      document.getElementById('form-reset').classList.remove('hidden');
    } else {
      if (path !== '/') history.replaceState({}, '', '/');
      showOnly('landing');
    }
  }

  async function afterAuth(payload) {
    Api().setToken(payload.token);
    document.getElementById('user-label').textContent = `${payload.user.name} (${payload.user.email})`;
    history.pushState({}, '', '/dashboard');
    showOnly('app');
    await window.SadenApp.init();
  }

  function bind() {
    document.querySelectorAll('[data-go]').forEach((b) => {
      b.addEventListener('click', () => go(b.getAttribute('data-go')));
    });
    window.addEventListener('popstate', route);

    const menuBtn = document.getElementById('btn-landing-menu');
    const landingNav = document.getElementById('landing-nav');
    if (menuBtn && landingNav) {
      menuBtn.addEventListener('click', () => {
        const open = landingNav.classList.toggle('open');
        menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      landingNav.querySelectorAll('a').forEach((a) => {
        a.addEventListener('click', () => {
          landingNav.classList.remove('open');
          menuBtn.setAttribute('aria-expanded', 'false');
        });
      });
    }

    // Header integrado: transparente no topo, superfície sutil após rolar.
    const landingTop = document.querySelector('.landing-top');
    if (landingTop) {
      const onScroll = () => {
        landingTop.classList.toggle('scrolled', window.scrollY > 24);
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }

    document.getElementById('tab-login').addEventListener('click', () => authTab('login'));
    document.getElementById('tab-register').addEventListener('click', () => authTab('register'));

    document.getElementById('form-login').addEventListener('submit', async (e) => {
      e.preventDefault();
      setError('login-error', '');
      try {
        const payload = await Api().login(
          document.getElementById('login-email').value,
          document.getElementById('login-password').value
        );
        await afterAuth(payload);
      } catch (err) {
        setError('login-error', err.message);
      }
    });

    document.getElementById('form-register').addEventListener('submit', async (e) => {
      e.preventDefault();
      setError('register-error', '');
      try {
        const payload = await Api().register(
          document.getElementById('reg-name').value,
          document.getElementById('reg-email').value,
          document.getElementById('reg-password').value
        );
        await afterAuth(payload);
      } catch (err) {
        setError('register-error', err.message);
      }
    });

    document.getElementById('link-forgot').addEventListener('click', () => {
      authTab('login');
      document.getElementById('form-login').classList.add('hidden');
      document.getElementById('form-forgot').classList.remove('hidden');
      setError('forgot-error', '');
      setOk('forgot-ok', '');
    });
    document.getElementById('link-back-login').addEventListener('click', () => authTab('login'));

    document.getElementById('form-forgot').addEventListener('submit', async (e) => {
      e.preventDefault();
      setError('forgot-error', '');
      setOk('forgot-ok', '');
      try {
        const res = await Api().forgot(document.getElementById('forgot-email').value);
        setOk('forgot-ok', res.message);
      } catch (err) {
        setError('forgot-error', err.message);
      }
    });

    document.getElementById('form-reset').addEventListener('submit', async (e) => {
      e.preventDefault();
      setError('reset-error', '');
      setOk('reset-ok', '');
      const token = new URLSearchParams(location.search).get('token') || '';
      try {
        if (!token) throw new Error('Link de recuperação inválido. Solicite um novo link.');
        const res = await Api().reset(token, document.getElementById('reset-password').value);
        setOk('reset-ok', `${res.message} Volte ao login.`);
      } catch (err) {
        setError('reset-error', err.message);
      }
    });

    document.getElementById('btn-logout').addEventListener('click', () => {
      Api().setToken(null);
      go('/');
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    bind();
    route();
    // Entrada suave única das seções da landing (sem animação contínua).
    try {
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (!reduce && 'IntersectionObserver' in window) {
        const seq = document.querySelectorAll('#view-landing .hero-text, #view-landing .hero-photo, #view-landing .landing-section, #view-landing .landing-cta');
        seq.forEach((el) => el.classList.add('reveal'));
        const io = new IntersectionObserver(
          (entries) => {
            entries.forEach((en) => {
              if (en.isIntersecting) {
                en.target.classList.add('in');
                io.unobserve(en.target);
              }
            });
          },
          { threshold: 0.05, rootMargin: '0px 0px 120px 0px' }
        );
        seq.forEach((el) => io.observe(el));
      }
    } catch {
      /* efeito progressivo: nunca bloqueia conteúdo */
    }
  });
  window.SadenAuth = { route, go };
})();

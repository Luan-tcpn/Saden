'use strict';
// Aplica o tema antes da primeira pintura (evita flash). Sem dependências,
// sem frameworks — chamado por um script inline mínimo no <head>.
function SadenThemeInit() {
  try {
    var t = localStorage.getItem('saden_theme') || 'system';
    var dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  } catch (e) {
    document.documentElement.dataset.theme = 'light';
  }
}

// Auto-aplicação ao carregar (o <head> inclui este arquivo antes do CSS/first paint).
if (typeof document !== 'undefined') SadenThemeInit();

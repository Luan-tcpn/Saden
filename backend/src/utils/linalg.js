'use strict';

// Álgebra linear mínima compartilhada (sem dependências):
// eliminação de Gauss com pivoteamento parcial + OLS via equações normais.
// Movido verbatim de forecastService.js (E3) para evitar duplicação;
// comportamento numérico idêntico, coberto pela suíte existente.
function solve(A, b) {
  const n = A.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col++) {
    let piv = col;
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(M[r][col]) > Math.abs(M[piv][col])) piv = r;
    }
    if (Math.abs(M[piv][col]) < 1e-12) throw new Error('Matriz singular no ajuste ridge');
    [M[col], M[piv]] = [M[piv], M[col]];
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const f = M[r][col] / M[col][col];
      for (let c = col; c <= n; c++) M[r][c] -= f * M[col][c];
    }
  }
  return M.map((row, i) => row[n] / M[i][i]);
}

// OLS: beta para X (n×k, já com coluna de intercepto se desejado) e y.
// Lança Error em matriz singular (chamador decide o fallback honesto).
function olsBeta(X, y) {
  const n = X.length;
  const k = X[0].length;
  const XtX = Array.from({ length: k }, () => new Array(k).fill(0));
  const Xty = new Array(k).fill(0);
  for (let i = 0; i < n; i++) {
    for (let a = 0; a < k; a++) {
      Xty[a] += X[i][a] * y[i];
      for (let b = 0; b < k; b++) XtX[a][b] += X[i][a] * X[i][b];
    }
  }
  return solve(XtX, Xty);
}

module.exports = { solve, olsBeta };

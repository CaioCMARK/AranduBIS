"use strict";

const Modelos = {
  rotulos: { asa: "Asa", placa: "Placa", corpo: "Corpo", trelica: "Treliça", roda: "Roda", massa: "Massa" },

  novo(tipo, nome) {
    switch (tipo) {
      case "asa":
        return { nome, tipo: "asa", perfil: "NACA 4412", n_perfil: 40,
          secoes: [-1, -0.5, 0, 0.5, 1].map(y => ({ y, xle: 0, zle: 0, corda: 0.3 - 0.1 * Math.abs(y), ainc: 0 })) };
      case "placa":
        return { nome, tipo: "placa", espessura: 0.01, y: 0, material: "balsa",
          contorno: [[0, 0], [0.3, 0], [0.3, 0.2], [0, 0.2]] };
      case "corpo":
        return { nome, tipo: "corpo", n_secao: 24, posicao: [0, 0, 0],
          estacoes: [{ x: 0.0, a: 0.03, b: 0.03, expoente: 3 }, { x: 0.15, a: 0.06, b: 0.05, expoente: 4 },
            { x: 0.3, a: 0.03, b: 0.03, expoente: 3 }] };
      case "trelica":
        return { nome, tipo: "trelica", camada: "estrutura",
          tubos: { D4: { de: 0.004, di: 0.003, material: "tubo_carbono" } },
          nos: [[0, 0, 0], [0.3, 0, 0]], barras: [[0, 1, "D4"]] };
      case "roda":
        return { nome, tipo: "roda", diametro: 0.09, largura: 0.008, d_furo: 0.016, d_cubo: 0.028,
          anel: 0.006, n_aros: 6, aro: 0.005, material: "nylon", y: 0, posicao: [0.2, 0, -0.1] };
      case "massa":
        return { nome, tipo: "ponto", massa: 0.1, posicao: [0.2, 0, 0] };
    }
    throw new Error("tipo desconhecido: " + tipo);
  },
};

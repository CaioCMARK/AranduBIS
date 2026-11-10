from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

class ConfiguracaoInvalida(ValueError):
    pass

@dataclass(frozen=True)
class Opcao:
    chave: str
    grupo: str
    rotulo: str
    padrao: object
    ajuda: str
    escolhas: tuple = ()
    minimo: float | None = None
    maximo: float | None = None
    habilita: str = ""

    @property
    def tipo(self) -> str:
        if self.escolhas:
            return "escolha"
        if isinstance(self.padrao, bool):
            return "booleano"
        return "texto" if isinstance(self.padrao, str) else "numero"

OPCOES: tuple[Opcao, ...] = (
    Opcao("aparencia.tema", "Aparência", "Tema da interface", "cinza",
          "auto: segue o claro/escuro do sistema. escuro: preto azulado. cinza: cinza médio, menos contraste e menos cansativo. claro: fundo claro.",
          escolhas=("auto", "escuro", "cinza", "claro")),
    Opcao("polares.fonte", "Polares", "De onde vêm as polares", "banco",
          "banco: usa as polares já calculadas (rápido, funciona sem instalar nada). "
          "xfoil: calcula cada perfil na hora. avl: roda o AVL na aeronave inteira "
          "(mais fiel ao conjunto, exige o AVL instalado).",
          escolhas=("banco", "xfoil", "avl")),
    Opcao("polares.avl_caminho", "Polares", "Caminho do AVL", "",
          "Arquivo avl.exe. O programa não traz o AVL (licença GPL): "
          "baixe-o e aponte aqui.", habilita="polares.fonte=avl"),
    Opcao("polares.xfoil_caminho", "Polares", "Caminho do XFOIL", "",
          "Arquivo xfoil.exe, só se a fonte for xfoil.", habilita="polares.fonte=xfoil"),
    Opcao("polares.ncrit_modo", "Polares", "Ncrit", "auto",
          "auto: o programa escolhe pelo nível de turbulência do túnel ou do ar. "
          "fixo: usa o valor abaixo em todas as polares.",
          escolhas=("auto", "fixo")),
    Opcao("polares.ncrit", "Polares", "Valor fixo de Ncrit", 9.0,
          "Fator de amplificação da transição (e^N). 9 = ar calmo padrão; "
          "valores menores antecipam a transição.", minimo=1.0, maximo=14.0,
          habilita="polares.ncrit_modo=fixo"),
    Opcao("polares.mach_critico_modo", "Polares", "Mach crítico", "auto",
          "auto: calculado do perfil. fixo: usa o valor abaixo.",
          escolhas=("auto", "fixo")),
    Opcao("polares.mach_critico", "Polares", "Valor fixo de Mach crítico", 0.7,
          "Acima disto a correção de compressibilidade deixa de valer.",
          minimo=0.3, maximo=1.0, habilita="polares.mach_critico_modo=fixo"),
    Opcao("polares.reynolds_minimo", "Polares", "Reynolds mínimo da tabela", 40000.0,
          "Abaixo disto o programa extrapola e avisa.", minimo=1e4, maximo=1e6),
    Opcao("polares.ncrit_banco", "Polares", "Ncrit do banco de polares", "4",
          "Qual variante do banco usar: 4 = ar livre turbulento, 7 = ar mais limpo. "
          "Se o perfil só existe numa delas, a outra é usada e a tela avisa.", escolhas=("4", "7")),
    Opcao("analise.velocidade_voo", "Padrões da análise", "Velocidade de decolagem (m/s)", 12.0,
          "Usada no Reynolds de cada faixa e no CL máximo. A aeronave costuma decolar perto de 12 m/s.",
          minimo=3.0, maximo=60.0),
    Opcao("analise.velocidade_cruzeiro", "Padrões da análise", "Velocidade de cruzeiro (m/s)", 15.0,
          "Usada no equilíbrio e na estabilidade.", minimo=3.0, maximo=60.0),
    Opcao("analise.rho", "Padrões da análise", "Densidade do ar (kg/m³)", 1.1,
          "1,225 ao nível do mar; 1,06 a 1330 m de altitude-densidade.", minimo=0.5, maximo=1.4),
    Opcao("analise.CL_alvo", "Padrões da análise", "CL a equilibrar", 0.8,
          "CL em que a aeronave deve voar equilibrada (cruzeiro).", minimo=0.1, maximo=3.0),
    Opcao("analise.margem_estatica_min", "Padrões da análise", "Margem estática mínima (fração da MAC)", 0.05,
          "Piso exigido em todo o envelope de CG. 0,05 = 5% da MAC (hipótese de projeto).", minimo=0.0, maximo=0.5),
    Opcao("estrutura.V_c", "Padrões da estrutura", "Velocidade de cruzeiro Vc do diagrama V-n (m/s)", 13.0,
          "Valor de referência: 13 m/s.", minimo=3.0, maximo=60.0),
    Opcao("estrutura.n_max", "Padrões da estrutura", "Fator de carga máximo de manobra", 1.8,
          "Valor de referência: 1,8 no envelope final (2,5 no preliminar). Ajuste ao seu projeto.", minimo=1.0, maximo=6.0),
    Opcao("estrutura.n_min", "Padrões da estrutura", "Fator de carga mínimo (negativo)", 0.0,
          "0 = sem carga negativa de projeto (referência: 0 no final, -1 no preliminar).", minimo=-3.0, maximo=0.0),
    Opcao("estrutura.V_d", "Padrões da estrutura", "Velocidade de mergulho Vd (m/s)", 15.9,
          "Valor de referência: 15,9 m/s, medida em ensaio de mergulho. Precisa ser maior que a de cruzeiro.", minimo=5.0, maximo=80.0),
    Opcao("estrutura.rajada_Vc", "Padrões da estrutura", "Rajada vertical em Vc (m/s)", 4.0,
          "Valor de referência: 4 m/s (maior observada no local: 2,65 m/s). Pratt-Cooper.", minimo=0.0, maximo=20.0),
    Opcao("estrutura.rajada_Vd", "Padrões da estrutura", "Rajada vertical em Vd (m/s)", 2.0,
          "Metade da rajada em Vc (prática usual).", minimo=0.0, maximo=20.0),
    Opcao("estrutura.fator_seguranca", "Padrões da estrutura", "Fator de segurança", 1.2,
          "Valor usual em aeromodelos de competição: 1,2. Multiplica a carga limite para a carga de ruptura.", minimo=1.0, maximo=3.0),
    Opcao("estrutura.cl_min_rel", "Padrões da estrutura", "CL mínimo / CL máximo (voo invertido)", 0.5,
          "Hipótese: define a parábola de estol negativa do diagrama V-n. Só vale com fator de carga mínimo negativo.", minimo=0.1, maximo=1.0),
    Opcao("estrutura.CL_max", "Padrões da estrutura", "CL máximo da aeronave (0 = calcular)", 0.0,
          "0 usa a teoria de faixas com as polares do banco. Informe o valor de ensaio para substituir.", minimo=0.0, maximo=6.0),
    Opcao("estrutura.qualidade_balsa", "Materiais da estrutura", "Qualidade da balsa (× tensões admissíveis)", 1.0,
          "1 = a de referência (ensaio de tração, 95% de confiança de que 90% superam). Lotes piores: use menos de 1.", minimo=0.3, maximo=1.5),
    Opcao("estrutura.qualidade_carbono", "Materiais da estrutura", "Qualidade do carbono (× tensões admissíveis)", 1.0,
          "1 = a de referência (MatWeb para o tubo). Tubos de procedência incerta: use menos de 1.", minimo=0.3, maximo=1.5),
    Opcao("estrutura.balsa_E", "Materiais da estrutura", "Balsa: módulo E na fibra (GPa)", 2.85,
          "Referência: 3,20 medido, 2,85 calibrado com o ensaio de flexão da asa.", minimo=0.5, maximo=10.0),
    Opcao("estrutura.balsa_X", "Materiais da estrutura", "Balsa: tração admissível (MPa)", 12.39,
          "Ensaio de referência ASTM D3039 (Small Sample).", minimo=1.0, maximo=50.0),
    Opcao("estrutura.balsa_XC", "Materiais da estrutura", "Balsa: compressão admissível (MPa)", 14.0,
          "Valor de referência de ensaio.", minimo=1.0, maximo=50.0),
    Opcao("estrutura.balsa_S", "Materiais da estrutura", "Balsa: cisalhamento admissível (MPa)", 2.1,
          "Valor de referência de ensaio.", minimo=0.2, maximo=10.0),
    Opcao("estrutura.tubo_E", "Materiais da estrutura", "Tubo de carbono: módulo E (GPa)", 112.0,
          "Referência: 126 do fornecedor, 112 calibrado com o ensaio.", minimo=20.0, maximo=300.0),
    Opcao("estrutura.tubo_X", "Materiais da estrutura", "Tubo de carbono: tração admissível (MPa)", 1218.0,
          "Referência: MatWeb.", minimo=100.0, maximo=4000.0),
    Opcao("estrutura.tubo_XC", "Materiais da estrutura", "Tubo de carbono: compressão admissível (MPa)", 1200.0,
          "Referência: MatWeb.", minimo=100.0, maximo=4000.0),
    Opcao("estrutura.margem_aeroelastica", "Torção e aeroelasticidade", "Margem de velocidade (× Vd)", 1.2,
          "Reversão e divergência precisam ficar acima de 1,2 × Vd (FAR 23.629(c)).", minimo=1.0, maximo=2.0),
    Opcao("estrutura.x_ca_c", "Torção e aeroelasticidade", "Centro aerodinâmico (fração da corda)", 0.25,
          "Hipótese: 0,25 (perfil fino). Mede-se no túnel ou se tira do cm das polares.", minimo=0.15, maximo=0.35),
    Opcao("estrutura.cl_alpha_2d", "Torção e aeroelasticidade", "Inclinação cl-α 2D (1/rad)", 6.2832,
          "Teoria de faixas sem efeito 3D: 2π é conservador (a reversão chega mais cedo).", minimo=3.0, maximo=7.0),
    Opcao("estrutura.eficiencia_comando", "Torção e aeroelasticidade", "Eficiência do aileron (viscosa)", 0.85,
          "Multiplica cl-δ e cm-δ de perfil fino. Valores usuais de 0,8 a 0,9.", minimo=0.4, maximo=1.0),
    Opcao("estrutura.calib_GJ", "Torção e aeroelasticidade", "Calibração do GJ (× modelo)", 1.0,
          "1 = modelo de parede fina. Troque pelo fator do ensaio de torção estática (um FEM de referência usou 0,848).", minimo=0.2, maximo=3.0),
    Opcao("estrutura.ea_desloc_c", "Torção e aeroelasticidade", "Deslocamento da linha elástica (fração da corda, + para trás)", 0.0,
          "Correção do GVT: use quando o ensaio de vibração em solo discordar do modelo.", minimo=-0.2, maximo=0.2),
    Opcao("estrutura.x_apoio", "Cauda e treliça", "Apoio da cauda: nós com x até (m)", 0.30,
          "Hipótese: a treliça é engastada na região da fuselagem, onde começa o boom.", minimo=0.0, maximo=1.0),
    Opcao("estrutura.CL_max_h", "Cauda e treliça", "CL máximo da empenagem horizontal (profundor a fundo)", 0.8,
          "Hipótese: empenagem simétrica com profundor deflexionado; vale em Vd.", minimo=0.2, maximo=1.5),
    Opcao("estrutura.K_flambagem", "Cauda e treliça", "Fator K de flambagem das barras", 0.8,
          "Valor do Arandu 0.2.0 para barras com juntas coladas (0,5 engastada, 1,0 articulada).", minimo=0.5, maximo=2.0),
    Opcao("estrutura.tailstrike_peso", "Cauda e treliça", "Tailstrike: reação na ponta do boom (× peso, 0 = não verificar)", 0.0,
          "Sem valor padrão: muitas aeronaves são projetadas para evitar o tailstrike. Informe um valor só para ver quanto o boom aguenta.", minimo=0.0, maximo=10.0),
    Opcao("estrutura.balsa_E_transv", "Flambagem do chapeado", "Balsa: módulo E transversal à fibra (GPa)", 0.12,
          "Estimativa (balsa: de 3 a 5 % do E na fibra); a direção transversal raramente é ensaiada.", minimo=0.02, maximo=1.0),
    Opcao("estrutura.knockdown_pele", "Flambagem do chapeado", "Fator de imperfeição do chapeado (× teoria)", 0.5,
          "Estimativa: a casca real flamba abaixo do valor teórico. Ajuste até reproduzir o autovalor do FEM da sua asa (um caso de referência: 0,92 sem nervura falsa, 1,26 com).", minimo=0.1, maximo=1.0),
    Opcao("estrutura.fator_pouso", "Trem de pouso", "Fator de carga de pouso (× peso)", 5.4,
          "Valor de referência: 5,4 estrutural (ensaio de queda de 13,4 cm, com margem). Reação do solo = fator × peso, sem sustentação residual.", minimo=1.0, maximo=15.0),
    Opcao("estrutura.atrito_pouso", "Trem de pouso", "Atrito de spin-up no pouso (× reação vertical)", 0.3,
          "Estimativa: força para trás nas rodas principais quando elas giram até a velocidade do solo.", minimo=0.0, maximo=1.0),
    Opcao("estrutura.fator_taxi_y", "Trem de pouso", "Taxi: fator lateral (× peso)", 0.5,
          "Valor de referência: 0,5.", minimo=0.0, maximo=2.0),
    Opcao("estrutura.fator_taxi_z", "Trem de pouso", "Taxi: fator vertical (× peso)", 1.0,
          "Valor de referência: 1,0.", minimo=0.5, maximo=3.0),
    Opcao("estrutura.raio_inercia", "Trem de pouso", "Raio de espalhamento da massa (m)", 0.25,
          "Estimativa: a massa da aeronave entra igual em todos os nós da treliça a menos deste raio do CG; define por onde a inércia carrega a estrutura.", minimo=0.05, maximo=1.0),
    Opcao("estrutura.raio_solda", "Trem de pouso", "Zona rígida da solda do eixo (m)", 0.02,
          "Estimativa: a união de fibras enroladas e epóxi que prende o eixo a cada pé da treliça é rígida por este meio-comprimento ao longo do eixo. 0 = junta pontual.", minimo=0.0, maximo=0.1),
    Opcao("analise.efeito_solo", "Padrões da análise", "Efeito solo na corrida", True,
          "Considera o chão (imagem do sistema de vórtices) no CL e no CD da corrida e da subida."),
    Opcao("tracao.potencia_w", "Padrões da tração", "Potência na bateria (W)", 600.0,
          "Limite do regulamento da bateria. Muda de ano para ano.", minimo=50.0, maximo=5000.0),
    Opcao("tracao.V_max", "Padrões da tração", "Tração até a velocidade (m/s)", 18.0,
          "Fim da curva T(V). A aeronave raramente passa de 15 m/s.", minimo=5.0, maximo=60.0),
    Opcao("tracao.v_celula", "Padrões da tração", "Tensão por célula sob carga (V)", 3.6,
          "Hipótese para a tensão do pack (células × este valor). Meça a sua bateria.", minimo=2.8, maximo=4.2),
    Opcao("tracao.celulas", "Padrões da tração", "Células do pack em série", "6",
          "0 = sem limite de tensão. O usual é 6S; o regulamento permite 4 a 6 células.",
          escolhas=("0", "4", "5", "6")),
    Opcao("tracao.capacidade_Ah", "Padrões da tração", "Capacidade do pack (Ah)", 1.5,
          "Mínimo do regulamento: 1500 mAh. Com a taxa C dá a corrente máxima do pack.", minimo=0.1, maximo=30.0),
    Opcao("tracao.taxa_C", "Padrões da tração", "Taxa de descarga do pack (C)", 20.0,
          "Mínimo do regulamento: 20C.", minimo=1.0, maximo=200.0),
    Opcao("tracao.perdas_realistas", "Padrões da tração", "Perdas realistas do motor", True,
          "Enrolamento a 70 °C, perdas em vazio crescendo com a rotação e ESC com curva."),
    Opcao("tracao.motor", "Padrões da tração", "Motor inicial", "Scorpion SII-4035-330",
          "Nome exato do motor do catálogo."),
    Opcao("tracao.helice", "Padrões da tração", "Hélice inicial", "22x10E",
          "Nome exato da hélice APC, ex. 22x10E."),
    Opcao("dinamica.massa_kg", "Padrões da dinâmica de voo", "Massa de voo de referência (kg)", 15.0,
          "Massa usada nos modos de voo. 0 = a soma das massas declaradas no modelo.",
          minimo=0.0, maximo=200.0),
    Opcao("dinamica.modo_inercia", "Padrões da dinâmica de voo", "Origem das inércias", "auto",
          "auto: usa as massas do modelo se ele declara a maior parte da massa, senão estima por raio de giro. "
          "modelo: sempre as massas do modelo. raio: sempre o raio de giro.", escolhas=("auto", "modelo", "raio")),
    Opcao("dinamica.raio_x", "Padrões da dinâmica de voo", "Raio de giro em rolagem (Rx/b)", 0.25,
          "Fração da envergadura. 0,25 é típico de avião leve monomotor (Roskam).", minimo=0.05, maximo=0.6),
    Opcao("dinamica.raio_y", "Padrões da dinâmica de voo", "Raio de giro em arfagem (Ry/L)", 0.38,
          "Fração do comprimento. 0,38 é típico de avião leve monomotor (Roskam).", minimo=0.05, maximo=0.8),
    Opcao("dinamica.raio_z", "Padrões da dinâmica de voo", "Raio de giro em guinada (Rz/média de b e L)", 0.39,
          "Fração da média entre envergadura e comprimento. 0,39 é típico de avião leve monomotor (Roskam).", minimo=0.05, maximo=0.8),
    Opcao("controle.sobe_max", "Padrões dos ailerons", "Deflexão máxima para cima (°)", 30.0,
          "Batente do aileron para cima. Projetos costumam usar 25 a 30°.", minimo=1.0, maximo=45.0),
    Opcao("controle.desce_max", "Padrões dos ailerons", "Deflexão máxima para baixo (°)", 25.0,
          "Batente para baixo, na opção sobe e desce. Na opção só sobe o aileron não desce.", minimo=1.0, maximo=45.0),
    Opcao("controle.pb2V_min", "Padrões dos ailerons", "pb/2V mínimo", 0.05,
          "Taxa de rolagem adimensional exigida. Critério de projeto: use o número do seu requisito.",
          minimo=0.005, maximo=0.5),
    Opcao("controle.t_inclinacao_max", "Padrões dos ailerons", "Tempo máximo para inclinar (s)", 1.5,
          "Tempo para atingir a inclinação abaixo. Critério de projeto, ajuste ao seu requisito.", minimo=0.2, maximo=10.0),
    Opcao("controle.V_servo", "Padrões dos ailerons", "Velocidade para dimensionar o servo (m/s)", 18.0,
          "O momento de charneira cresce com o quadrado da velocidade: use a máxima que o avião pode atingir, com folga.",
          minimo=5.0, maximo=80.0),
    Opcao("controle.inclinacao", "Padrões dos ailerons", "Inclinação do critério (°)", 30.0,
          "Ângulo de rolagem usado no critério de tempo.", minimo=5.0, maximo=90.0),
    Opcao("decolagem.pista_m", "Padrões da decolagem", "Distância até o obstáculo (m)", 55.0,
          "Muda de ano para ano e de regulamento.", minimo=5.0, maximo=500.0),
    Opcao("decolagem.obstaculo_m", "Padrões da decolagem", "Altura do obstáculo (m)", 0.9,
          "Altura que a aeronave precisa ter nessa distância.", minimo=0.0, maximo=10.0),
    Opcao("decolagem.altitude_densidade_m", "Padrões da decolagem", "Altitude-densidade (m)", 1330.0,
          "Define a densidade do ar da decolagem (atmosfera padrão).", minimo=-500.0, maximo=5000.0),
    Opcao("decolagem.mu", "Padrões da decolagem", "Atrito de rolagem μ", 0.062,
          "Depende da pista e das rodas. Meça o da sua.", minimo=0.005, maximo=0.5),
    Opcao("decolagem.d_alpha_rotacao", "Padrões da decolagem", "Giro até sair do solo (°)", 6.0,
          "Quanto a atitude muda da corrida até a saída.", minimo=0.0, maximo=30.0),
    Opcao("decolagem.taxa_rotacao", "Padrões da decolagem", "Taxa de rotação (°/s)", 20.0,
          "Velocidade com que o piloto levanta o nariz.", minimo=1.0, maximo=200.0),
    Opcao("decolagem.margem_rotacao", "Padrões da decolagem", "Início da rotação (× V de estol)", 1.02,
          "Fração da velocidade de estol em que começa a puxar.", minimo=0.5, maximo=2.0),
    Opcao("avl.n_secoes", "Análise", "Painéis em envergadura (AVL)", 20,
          "Mais painéis, mais fiel e mais lento.", minimo=6, maximo=60,
          habilita="polares.fonte=avl"),
    Opcao("otimizacao.mostrar_individuos", "Otimização", "Indivíduos mostrados", "alguns",
          "A otimização é a etapa mais pesada. nenhum: só o resultado final. "
          "alguns: uma amostra por geração (abaixo). todos: cada indivíduo "
          "avaliado (lento e usa muita memória).", escolhas=("nenhum", "alguns", "todos")),
    Opcao("otimizacao.individuos_max", "Otimização", "Quantos por geração", 20,
          "Número de indivíduos mostrados em cada geração (os melhores primeiro).",
          minimo=1, maximo=10000, habilita="otimizacao.mostrar_individuos=alguns"),
    Opcao("otimizacao.a_cada_geracoes", "Otimização", "Mostrar a cada N gerações", 1,
          "1 mostra todas as gerações; 5 mostra uma em cada cinco.",
          minimo=1, maximo=1000),
    Opcao("pastas.base", "Pastas do projeto", "Base de dados", "",
          "Pasta com os dados do projeto (polares, ensaios, tabelas)."),
    Opcao("pastas.relatorios", "Pastas do projeto", "Relatórios", "",
          "Pasta com os relatórios (PDF, texto)."),
    Opcao("pastas.desenhos", "Pastas do projeto", "Desenhos", "",
          "Pasta com os desenhos e as aeronaves (.json, imagens, PDF)."),
    Opcao("vista.malha_ao_abrir", "Interface", "Abrir já em modo malha", False,
          "Mostra a triangulação em vez do sólido ao abrir uma aeronave."),
)

_POR_CHAVE = {o.chave: o for o in OPCOES}

def opcao(chave: str) -> Opcao:
    try:
        return _POR_CHAVE[chave]
    except KeyError:
        raise ConfiguracaoInvalida(f"opção desconhecida: {chave}") from None

def validar(chave: str, valor):
    o = opcao(chave)
    if o.tipo == "escolha":
        if valor not in o.escolhas:
            raise ConfiguracaoInvalida(f"{chave}: use {', '.join(o.escolhas)}")
    elif o.tipo == "booleano":
        if not isinstance(valor, bool):
            raise ConfiguracaoInvalida(f"{chave}: use verdadeiro ou falso")
    elif o.tipo == "texto":
        if not isinstance(valor, str):
            raise ConfiguracaoInvalida(f"{chave}: texto")
    else:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ConfiguracaoInvalida(f"{chave}: número")
        if (o.minimo is not None and valor < o.minimo) or (
                o.maximo is not None and valor > o.maximo):
            raise ConfiguracaoInvalida(
                f"{chave}: entre {o.minimo:g} e {o.maximo:g}")
        valor = type(o.padrao)(valor)
    return valor

class Configuracao:

    def __init__(self, mudancas: dict | None = None):
        self._m: dict = {}
        for k, v in (mudancas or {}).items():
            self.definir(k, v)

    def valor(self, chave: str):
        o = opcao(chave)
        return self._m.get(chave, o.padrao)

    def definir(self, chave: str, valor) -> None:
        v = validar(chave, valor)
        if v == opcao(chave).padrao:
            self._m.pop(chave, None)
        else:
            self._m[chave] = v

    def ativa(self, chave: str) -> bool:
        h = opcao(chave).habilita
        if not h:
            return True
        k, v = h.split("=")
        return self.valor(k) == v

    def mudancas(self) -> dict:
        return dict(self._m)

    def problemas(self) -> list[str]:
        p = []
        fonte = self.valor("polares.fonte")
        for f, chave, nome in (("avl", "polares.avl_caminho", "AVL"),
                               ("xfoil", "polares.xfoil_caminho", "XFOIL")):
            if fonte == f:
                c = self.valor(chave)
                if not c:
                    p.append(f"Fonte {f}: informe o caminho do {nome}.")
                elif not Path(c).is_file():
                    p.append(f"{nome} não encontrado em {c}.")
        return p

    def gravar(self, caminho) -> None:
        Path(caminho).write_text(
            json.dumps({"versao": 1, "mudancas": self._m}, indent=2,
                       ensure_ascii=False), encoding="utf8")

    @classmethod
    def ler(cls, caminho) -> "Configuracao":
        p = Path(caminho)
        if not p.is_file():
            return cls()
        d = json.loads(p.read_text(encoding="utf8"))
        return cls({k: v for k, v in d.get("mudancas", {}).items() if k in _POR_CHAVE})

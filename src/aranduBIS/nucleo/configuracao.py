from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import referencias as R

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
    derivado: bool = False
    fonte: str = ""
    sem_efeito: bool = False
    auto: str = ""

    @property
    def referencia(self) -> bool:
        return self.derivado or bool(self.fonte) or bool(self.auto)

    @property
    def tipo(self) -> str:
        if self.escolhas:
            return "escolha"
        if isinstance(self.padrao, bool):
            return "booleano"
        return "texto" if isinstance(self.padrao, str) else "numero"

OPCOES: tuple[Opcao, ...] = (
    Opcao("aparencia.tema", "Aparência", "Tema da interface", "claro",
          "auto: segue o claro/escuro do sistema. claro: fundo claro (padrão). cinza: cinza médio, menos contraste. escuro: fundo escuro.",
          escolhas=("auto", "escuro", "cinza", "claro")),
    Opcao("polares.fonte", "Polares", "De onde vêm as polares", "banco",
          "banco: usa as polares já calculadas (rápido, funciona sem instalar nada). "
          "xfoil: calcula cada perfil na hora. avl: roda o AVL na aeronave inteira "
          "(mais fiel ao conjunto, exige o AVL instalado).",
          escolhas=("banco", "xfoil", "avl"), sem_efeito=True),
    Opcao("polares.avl_caminho", "Polares", "Caminho do AVL", "",
          "Arquivo avl.exe. O programa não traz o AVL (licença GPL): "
          "baixe-o e aponte aqui.", habilita="polares.fonte=avl", sem_efeito=True),
    Opcao("polares.xfoil_caminho", "Polares", "Caminho do XFOIL", "",
          "Arquivo xfoil.exe, só se a fonte for xfoil.", habilita="polares.fonte=xfoil", sem_efeito=True),
    Opcao("polares.ncrit_modo", "Polares", "Ncrit", "auto",
          "auto: o programa escolhe pelo nível de turbulência do túnel ou do ar. "
          "fixo: usa o valor abaixo em todas as polares.",
          escolhas=("auto", "fixo"), sem_efeito=True),
    Opcao("polares.ncrit", "Polares", "Valor fixo de Ncrit", 9.0,
          "Fator de amplificação da transição (e^N). 9 = ar calmo padrão; "
          "valores menores antecipam a transição.", minimo=1.0, maximo=14.0,
          habilita="polares.ncrit_modo=fixo", sem_efeito=True),
    Opcao("polares.mach_critico_modo", "Polares", "Mach crítico", "auto",
          "auto: calculado do perfil. fixo: usa o valor abaixo.",
          escolhas=("auto", "fixo"), sem_efeito=True),
    Opcao("polares.mach_critico", "Polares", "Valor fixo de Mach crítico", 0.7,
          "Acima disto a correção de compressibilidade deixa de valer.",
          minimo=0.3, maximo=1.0, habilita="polares.mach_critico_modo=fixo", sem_efeito=True),
    Opcao("polares.reynolds_minimo", "Polares", "Reynolds mínimo da tabela", 40000.0,
          "Abaixo disto o programa extrapola e avisa.", minimo=1e4, maximo=1e6, sem_efeito=True),
    Opcao("polares.ncrit_banco", "Polares", "Ncrit do banco de polares", "4",
          "Qual variante do banco usar: 4 = ar livre turbulento, 7 = ar mais limpo. "
          "Se o perfil só existe numa delas, a outra é usada e a tela avisa.", escolhas=("4", "7")),
    Opcao("analise.velocidade_voo", "Padrões da análise", "Velocidade de decolagem (m/s)", 12.0,
          "Entrada do projeto, sem valor universal: use cerca de 1,2 vezes a velocidade de estol da sua aeronave. "
          "Usada no Reynolds de cada faixa e no CL máximo.",
          minimo=3.0, maximo=60.0),
    Opcao("analise.velocidade_cruzeiro", "Padrões da análise", "Velocidade de cruzeiro (m/s)", 15.0,
          "Entrada do projeto, sem valor universal. Usada no equilíbrio e na estabilidade, e dá o Vc do diagrama V-n.",
          minimo=3.0, maximo=60.0),
    Opcao("analise.rho", "Padrões da análise", "Densidade do ar (kg/m³)", 1.225,
          "Automático: atmosfera padrão (ISA) na altitude-densidade da decolagem. Informe um valor para fixá-lo.",
          minimo=0.5, maximo=1.4, derivado=True),
    Opcao("analise.CL_alvo", "Padrões da análise", "CL a equilibrar", 0.8,
          "Entrada do projeto: CL em que a aeronave deve voar equilibrada (cruzeiro).", minimo=0.1, maximo=3.0),
    Opcao("analise.margem_estatica_min", "Padrões da análise", "Margem estática mínima (fração da MAC)", 0.05,
          "Piso exigido em todo o envelope de CG. 0,05 = 5% da MAC (hipótese de projeto).", minimo=0.0, maximo=0.5),
    Opcao("estrutura.V_c", "Padrões da estrutura", "Velocidade de cruzeiro Vc do diagrama V-n (m/s)", 15.0,
          "Automático: a velocidade de cruzeiro da análise. Informe um valor para fixá-lo.", minimo=3.0, maximo=60.0, derivado=True),
    Opcao("estrutura.n_max", "Padrões da estrutura", "Fator de carga máximo de manobra", 3.8,
          "Automático: 14 CFR 23.337(a)(1), n = 2,1 + 24000/(W + 10000) com W em lb e teto de 3,8 (vale 3,8 para qualquer massa até 1868 kg). "
          "Se o regulamento da sua competição fixar outro, informe aqui.", minimo=1.0, maximo=6.0, derivado=True),
    Opcao("estrutura.n_min", "Padrões da estrutura", "Fator de carga mínimo (negativo)", -1.52,
          "Automático: 14 CFR 23.337(b)(1), 0,4 vezes o positivo, negativo. 0 = sem carga negativa de projeto.", minimo=-3.0, maximo=0.0, derivado=True),
    Opcao("estrutura.V_d", "Padrões da estrutura", "Velocidade de mergulho Vd (m/s)", 18.75,
          "Automático: 1,25 Vc, o mínimo de 14 CFR 23.335(b)(1). Precisa ser maior que a de cruzeiro.", minimo=5.0, maximo=80.0, derivado=True),
    Opcao("estrutura.rajada_Vc", "Padrões da estrutura", "Rajada vertical em Vc (m/s)", 15.24,
          "14 CFR 23.333(c)(1): 50 ft/s em Vc (15,24 m/s). Pratt-Cooper. É a rajada de aeronave tripulada: em aeronave pequena e lenta ela é muito severa, então a carga fica limitada pelo estol; reduza se o seu local ou regulamento justificar.", minimo=0.0, maximo=20.0, fonte="14 CFR 23.333(c)(1)"),
    Opcao("estrutura.rajada_Vd", "Padrões da estrutura", "Rajada vertical em Vd (m/s)", 7.62,
          "14 CFR 23.333(c)(1): 25 ft/s em Vd (7,62 m/s), metade da de Vc.", minimo=0.0, maximo=20.0, fonte="14 CFR 23.333(c)(1)"),
    Opcao("estrutura.fator_seguranca", "Padrões da estrutura", "Fator de segurança", 1.5,
          "14 CFR 23.303: 1,5 sobre a carga limite. Multiplica a carga limite para a carga de ruptura.", minimo=1.0, maximo=3.0, fonte="14 CFR 23.303"),
    Opcao("estrutura.cl_min_rel", "Padrões da estrutura", "CL mínimo / CL máximo (voo invertido)", 0.5,
          "Hipótese de modelagem: define a parábola de estol negativa do diagrama V-n. Só vale com fator de carga mínimo negativo.", minimo=0.1, maximo=1.0),
    Opcao("estrutura.CL_max", "Padrões da estrutura", "CL máximo da aeronave (0 = calcular)", 0.0,
          "0 usa a teoria de faixas com as polares do banco. Informe o valor de ensaio para substituir.", minimo=0.0, maximo=6.0),
    Opcao("estrutura.qualidade_balsa", "Materiais da estrutura", "Qualidade da balsa (× tensões admissíveis)", 1.0,
          "1 = os valores médios da literatura (Wood Handbook). A balsa varia de 2 a 3 vezes com a densidade e os lotes ficam abaixo da média: ensaie o seu e use menos de 1.", minimo=0.3, maximo=1.5),
    Opcao("estrutura.qualidade_carbono", "Materiais da estrutura", "Qualidade do carbono (× tensões admissíveis)", 1.0,
          "1 = lâmina unidirecional ideal da literatura (AS4/3501-6). Um tubo real fica abaixo: use os dados do fabricante ou menos de 1.", minimo=0.3, maximo=1.5),
    Opcao("estrutura.balsa_E", "Materiais da estrutura", "Balsa: módulo E na fibra (GPa)", 3.4,
          "Wood Handbook (FPL-GTR-190): 3,4 GPa em flexão, balsa a 12 % de umidade e densidade relativa 0,17.", minimo=0.5, maximo=10.0, fonte="Wood Handbook (FPL-GTR-190), cap. 5"),
    Opcao("estrutura.balsa_X", "Materiais da estrutura", "Balsa: tração admissível (MPa)", 19.3,
          "Valor médio de tração paralela à fibra para balsa de cerca de 160 kg/m³ (Model Aviation). Não é admissível estatístico.", minimo=1.0, maximo=50.0, fonte="Model Aviation, Simple Structural Test Techniques"),
    Opcao("estrutura.balsa_XC", "Materiais da estrutura", "Balsa: compressão admissível (MPa)", 14.9,
          "Wood Handbook: compressão paralela à fibra, 14,9 MPa (2160 psi).", minimo=1.0, maximo=50.0, fonte="Wood Handbook (FPL-GTR-190), cap. 5"),
    Opcao("estrutura.balsa_S", "Materiais da estrutura", "Balsa: cisalhamento admissível (MPa)", 1.9,
          "Cisalhamento paralelo à fibra, balsa de cerca de 150 kg/m³ (Kotlarewski et al., Eur. J. Wood Prod. 2016). Valor médio.", minimo=0.2, maximo=10.0, fonte="Kotlarewski et al., Eur. J. Wood Prod. 2016"),
    Opcao("estrutura.balsa_YC", "Materiais da estrutura", "Balsa: compressão transversal à fibra (MPa)", 1.1,
          "Balsa de densidade média (120 a 180 kg/m³), ASTM D143. Entra no critério de Tsai-Hill do chapeado em casca.", minimo=0.05, maximo=10.0,
          fonte="Kotlarewski et al., Eur. J. Wood Prod. 2016"),
    Opcao("estrutura.balsa_YT", "Materiais da estrutura", "Balsa: tração transversal à fibra (MPa)", 1.1,
          "HIPÓTESE: não há valor publicado acessível para a balsa; usa o mesmo da compressão transversal. É o dado que mais "
          "vale ensaiar (corpo de prova puxado de través). Entra no Tsai-Hill do chapeado.", minimo=0.05, maximo=10.0),
    Opcao("estrutura.tubo_E", "Materiais da estrutura", "Tubo de carbono: módulo E (GPa)", 126.0,
          "Lâmina unidirecional AS4/3501-6 (Soden, Hinton & Kaddour 1998). Um tubo real é menos rígido: use o dado do seu fabricante.", minimo=20.0, maximo=300.0, fonte="AS4/3501-6, Soden et al. 1998"),
    Opcao("estrutura.tubo_X", "Materiais da estrutura", "Tubo de carbono: tração admissível (MPa)", 1950.0,
          "Lâmina unidirecional AS4/3501-6: 1950 MPa. Um tubo real fica abaixo.", minimo=100.0, maximo=4000.0, fonte="AS4/3501-6, Soden et al. 1998"),
    Opcao("estrutura.tubo_XC", "Materiais da estrutura", "Tubo de carbono: compressão admissível (MPa)", 1480.0,
          "Lâmina unidirecional AS4/3501-6: 1480 MPa. Um tubo real fica abaixo.", minimo=100.0, maximo=4000.0, fonte="AS4/3501-6, Soden et al. 1998"),
    Opcao("estrutura.margem_aeroelastica", "Torção e aeroelasticidade", "Margem de velocidade (× Vd)", 1.2,
          "Reversão e divergência precisam ficar acima de 1,2 × Vd (FAR 23.629(c)).", minimo=1.0, maximo=2.0, fonte="14 CFR 23.629"),
    Opcao("estrutura.x_ca_c", "Torção e aeroelasticidade", "Centro aerodinâmico (fração da corda)", 0.25,
          "Hipótese: 0,25 (perfil fino). Mede-se no túnel ou se tira do cm das polares.", minimo=0.15, maximo=0.35, fonte="teoria do perfil fino"),
    Opcao("estrutura.cl_alpha_2d", "Torção e aeroelasticidade", "Inclinação cl-α 2D (1/rad)", 6.2832,
          "Teoria de faixas sem efeito 3D: 2π é conservador (a reversão chega mais cedo).", minimo=3.0, maximo=7.0, fonte="teoria do perfil fino"),
    Opcao("estrutura.eficiencia_comando", "Torção e aeroelasticidade", "Eficiência do aileron (viscosa)", 0.85,
          "Multiplica cl-δ e cm-δ de perfil fino. Valores usuais de 0,8 a 0,9.", minimo=0.4, maximo=1.0),
    Opcao("estrutura.calib_GJ", "Torção e aeroelasticidade", "Calibração do GJ (× modelo)", 1.0,
          "1 = modelo de parede fina (Bredt-Batho). Troque pelo fator obtido num ensaio de torção estática da sua asa.", minimo=0.2, maximo=3.0),
    Opcao("estrutura.ea_desloc_c", "Torção e aeroelasticidade", "Deslocamento da linha elástica (fração da corda, + para trás)", 0.0,
          "Correção do GVT: use quando o ensaio de vibração em solo discordar do modelo.", minimo=-0.2, maximo=0.2),
    Opcao("estrutura.x_apoio", "Cauda e treliça", "Apoio da cauda: nós com x até (m)", 0.30,
          "Hipótese: a treliça é engastada na região da fuselagem, onde começa o boom.", minimo=0.0, maximo=1.0),
    Opcao("estrutura.CL_max_h", "Cauda e treliça", "CL máximo da empenagem horizontal (profundor a fundo)", 0.8,
          "Hipótese: empenagem simétrica com profundor deflexionado; vale em Vd.", minimo=0.2, maximo=1.5),
    Opcao("estrutura.K_flambagem", "Cauda e treliça", "Fator K de flambagem das barras", 1.0,
          "Euler: 1,0 para barra articulada nas duas pontas (conservador); 0,7 engastada-articulada; 0,5 engastada nas duas.", minimo=0.5, maximo=2.0, fonte="Euler, barra articulada"),
    Opcao("estrutura.tailstrike_peso", "Cauda e treliça", "Tailstrike: reação na ponta do boom (× peso, 0 = não verificar)", 0.0,
          "Sem valor padrão: muitas aeronaves são projetadas para evitar o tailstrike. Informe um valor só para ver quanto o boom aguenta.", minimo=0.0, maximo=10.0),
    Opcao("estrutura.balsa_E_transv", "Flambagem do chapeado", "Balsa: módulo E transversal à fibra (GPa)", 0.051,
          "Automático: 1,5 % do E na fibra (balsa tangencial, Wood Handbook tab. 5-1; radial seria 4,6 %). Informe um valor para fixá-lo.", minimo=0.02, maximo=1.0, derivado=True),
    Opcao("estrutura.knockdown_pele", "Flambagem do chapeado", "Fator de imperfeição do chapeado (× teoria)", 0.0,
          "0 = automático: NASA SP-8007, γ = 1 − 0,901 (1 − e^(−φ)) com φ = √(R/t)/16, calculado em cada painel pelo raio e pela espessura do chapeado (painel plano: 1). Informe um valor entre 0,1 e 1 para fixá-lo, por exemplo o que reproduz um modelo de elementos finitos da sua asa.", minimo=0.0, maximo=1.0),
    Opcao("estrutura.fator_pouso", "Trem de pouso", "Fator de carga de pouso (× peso)", 2.67,
          "14 CFR 23.473(g): fator de inércia de pouso nunca menor que 2,67. A reação do solo é fator × peso, sem descontar sustentação. O valor real depende do curso do trem e da velocidade de descida: se o ensaio de queda der mais, use o dele.", minimo=1.0, maximo=15.0, fonte="14 CFR 23.473(g)"),
    Opcao("estrutura.atrito_pouso", "Trem de pouso", "Atrito de spin-up no pouso (× reação vertical)", 0.3,
          "Estimativa: força para trás nas rodas principais quando elas giram até a velocidade do solo.", minimo=0.0, maximo=1.0),
    Opcao("estrutura.fator_taxi_y", "Trem de pouso", "Taxi: fator lateral (× peso)", 0.5,
          "Giro em curva no solo, 14 CFR 25.495: 0,5 lateral no CG.", minimo=0.0, maximo=2.0, fonte="14 CFR 25.495"),
    Opcao("estrutura.fator_taxi_z", "Trem de pouso", "Taxi: fator vertical (× peso)", 1.0,
          "Giro em curva no solo, 14 CFR 25.495: 1,0 vertical no CG.", minimo=0.5, maximo=3.0, fonte="14 CFR 25.495"),
    Opcao("estrutura.raio_inercia", "Trem de pouso", "Raio de espalhamento da massa (m)", 0.25,
          "Estimativa: a massa da aeronave entra igual em todos os nós da treliça a menos deste raio do CG; define por onde a inércia carrega a estrutura.", minimo=0.05, maximo=1.0),
    Opcao("estrutura.raio_solda", "Trem de pouso", "Zona rígida da união do eixo (m)", 0.0,
          "Hipótese de modelagem: meio-comprimento rígido da união que prende o eixo a cada ponto de apoio. 0 = junta pontual.", minimo=0.0, maximo=0.1),
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
    Opcao("dinamica.massa_kg", "Padrões da dinâmica de voo", "Massa de voo de referência (kg)", 0.0,
          "0 = a soma das massas declaradas no modelo. Informe um valor para fixar a massa dos modos de voo.",
          minimo=0.0, maximo=200.0),
    Opcao("dinamica.modo_inercia", "Padrões da dinâmica de voo", "Origem das inércias", "auto",
          "auto: usa as massas do modelo se ele declara a maior parte da massa, senão estima por raio de giro. "
          "modelo: sempre as massas do modelo. raio: sempre o raio de giro.", escolhas=("auto", "modelo", "raio")),
    Opcao("dinamica.raio_x", "Padrões da dinâmica de voo", "Raio de giro em rolagem (Rx/b)", 0.25,
          "Fração da envergadura. 0,25 é típico de avião leve monomotor (Roskam).", minimo=0.05, maximo=0.6, fonte="Roskam, Airplane Design parte V"),
    Opcao("dinamica.raio_y", "Padrões da dinâmica de voo", "Raio de giro em arfagem (Ry/L)", 0.38,
          "Fração do comprimento. 0,38 é típico de avião leve monomotor (Roskam).", minimo=0.05, maximo=0.8, fonte="Roskam, Airplane Design parte V"),
    Opcao("dinamica.raio_z", "Padrões da dinâmica de voo", "Raio de giro em guinada (Rz/média de b e L)", 0.39,
          "Fração da média entre envergadura e comprimento. 0,39 é típico de avião leve monomotor (Roskam).", minimo=0.05, maximo=0.8, fonte="Roskam, Airplane Design parte V"),
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
    Opcao("decolagem.altitude_densidade_m", "Padrões da decolagem", "Altitude-densidade (m)", 0.0,
          "0 = nível do mar na atmosfera padrão (ISA). Define a densidade do ar da decolagem; informe a do seu local.", minimo=-500.0, maximo=5000.0),
    Opcao("decolagem.mu", "Padrões da decolagem", "Atrito de rolagem μ", 0.05,
          "Freio solto: concreto seco 0,02 a 0,05, grama firme 0,05, terra firme 0,04, grama macia 0,07 (USNTPS Flight Test Manual, cap. 9). Meça o da sua pista.", minimo=0.005, maximo=0.5, fonte="USNTPS Flight Test Manual, tab. 9.2"),
    Opcao("decolagem.d_alpha_rotacao", "Padrões da decolagem", "Giro até sair do solo (°)", 6.0,
          "Quanto a atitude muda da corrida até a saída.", minimo=0.0, maximo=30.0),
    Opcao("decolagem.taxa_rotacao", "Padrões da decolagem", "Taxa de rotação (°/s)", 20.0,
          "Velocidade com que o piloto levanta o nariz.", minimo=1.0, maximo=200.0),
    Opcao("decolagem.margem_rotacao", "Padrões da decolagem", "Início da rotação (× V de estol)", 1.02,
          "Fração da velocidade de estol em que começa a puxar.", minimo=0.5, maximo=2.0),
    Opcao("avl.n_secoes", "Análise", "Painéis em envergadura (AVL)", 20,
          "Mais painéis, mais fiel e mais lento.", minimo=6, maximo=60,
          habilita="polares.fonte=avl", sem_efeito=True),
    Opcao("discretizacao.orcamento_s", "Discretização", "Orçamento de tempo por análise (s)", 120.0,
          "Antes de rodar uma análise pesada (UVLM, por exemplo) o programa estima o tempo pela malha. Acima deste "
          "orçamento ele afina menos onde a regra automática permite e, se ainda não couber, pergunta antes de rodar. "
          "Não é limite físico: suba à vontade num computador mais rápido.", minimo=5.0, maximo=36000.0),
    Opcao("discretizacao.vlm.n_span", "Discretização", "VLM: painéis na envergadura (por superfície)", 24,
          "Faixas de vórtice em cada superfície. Poucas faixas superestimam o CLα de asa curta (o vórtice de ponta "
          "domina). Vale para equilíbrio, cargas, aeroelasticidade, decolagem, otimização e UVLM.", minimo=4, maximo=200,
          auto="pelo alongamento de cada superfície: 24 se AR ≥ 4, 48 se AR ≥ 1, 96 se AR ≥ 0,5"),
    Opcao("discretizacao.vlm.n_chord", "Discretização", "VLM: painéis na corda", 4,
          "Perfil simétrico: CLα converge com 4 (regra 1/4-3/4). Perfil arqueado: a linha média entra como geometria e o CL de "
          "arqueamento converge devagar (NACA 4412: −14 % com 4 painéis, −7 % com 8, −3 % com 16).",
          minimo=1, maximo=40, auto="4 em perfil simétrico, 12 em perfil arqueado (o CL de arqueamento converge como 0,55/n)"),
    Opcao("discretizacao.estrutura.n_estacoes", "Discretização", "Estrutura: estações na semi-envergadura", 41,
          "Onde a asa é cortada para calcular seção, cortante, fletor, torção e flutter. Mais estações, mais detalhe "
          "perto de nervuras e do fim do chapeado.", minimo=11, maximo=401,
          auto="41, ou mais para ter ≥ 2 estações por baia de nervura"),
    Opcao("discretizacao.flutter.n_modos", "Discretização", "Flutter: modos de vibração", 8,
          "Modos da viga usados no p-k. Precisa incluir os modos até ~3× a frequência de flutter.", minimo=2, maximo=30,
          auto="8 (3 flexões, 2 torções e o aileron)"),
    Opcao("discretizacao.flutter.n_V", "Discretização", "Flutter: velocidades na varredura", 45,
          "Pontos de 0 a 3 Vd. O cruzamento do amortecimento é interpolado entre dois pontos.", minimo=10, maximo=400,
          auto="45 (ΔV ≈ 0,07 Vd)"),
    Opcao("discretizacao.chapeado.ns_pele", "Discretização", "Chapeado (CalculiX): elementos no contorno", 40,
          "Elementos de casca S8R ao redor da caixa-D. Precisa de ≥ 4 por meia-onda de flambagem.", minimo=8, maximo=400,
          auto="elemento de ~8 mm no contorno (20 a 100)"),
    Opcao("discretizacao.chapeado.ns_alma", "Discretização", "Chapeado (CalculiX): elementos na alma", 4,
          "Elementos na altura da alma da longarina.", minimo=1, maximo=40, auto="4"),
    Opcao("discretizacao.casca.dy_max", "Discretização", "Asa em casca: maior elemento na envergadura (m)", 0.06,
          "Tamanho máximo do elemento ao longo da envergadura no modelo de casca da asa.", minimo=0.005, maximo=0.5,
          auto="0,06 m (≈ 1/4 da corda típica)"),
    Opcao("discretizacao.casca.n_corda", "Discretização", "Asa em casca: elementos na corda da caixa-D", 6,
          "Elementos no contorno da caixa-D do modelo de casca.", minimo=2, maximo=60, auto="6"),
    Opcao("discretizacao.helice.n_est", "Discretização", "Hélice (BEMT): estações na pá", 40,
          "Faixas da pá no BEMT, em cosseno (mais perto da ponta e do cubo).", minimo=8, maximo=400, auto="40"),
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

def _massa(c):
    return c.valor("dinamica.massa_kg") or None

_DERIVADOS = {
    "analise.rho": lambda c: R.densidade_isa(c.valor("decolagem.altitude_densidade_m")),
    "estrutura.V_c": lambda c: c.valor("analise.velocidade_cruzeiro"),
    "estrutura.V_d": lambda c: R.velocidade_mergulho(c.valor("estrutura.V_c")),
    "estrutura.n_max": lambda c: R.fator_manobra_positivo(_massa(c)),
    "estrutura.n_min": lambda c: R.fator_manobra_negativo(c.valor("estrutura.n_max")),
    "estrutura.balsa_E_transv": lambda c: R.BALSA["ET_sobre_EL"] * c.valor("estrutura.balsa_E"),
}

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
        if chave in self._m:
            return self._m[chave]
        if o.derivado:
            return _DERIVADOS[chave](self)
        if o.auto:
            return None
        return o.padrao

    def manual(self, chave: str) -> bool:
        return chave in self._m

    def definir(self, chave: str, valor) -> None:
        self.definir_varias({chave: valor})

    def definir_varias(self, valores: dict) -> None:
        if not isinstance(valores, dict):
            raise ConfiguracaoInvalida("envie um objeto {chave: valor}")
        validos = {k: (None if v is None and opcao(k).referencia else validar(k, v)) for k, v in valores.items()}
        for k, v in validos.items():
            o = opcao(k)
            if v is None or (not o.derivado and not o.auto and v == o.padrao):
                self._m.pop(k, None)
            else:
                self._m[k] = v

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

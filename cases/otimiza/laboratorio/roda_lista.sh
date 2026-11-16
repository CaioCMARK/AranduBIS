#!/bin/sh
# roda so as configuracoes da lista. Uso: [SEGURO=1] sh roda_lista.sh POP GER nome1 nome2 ...
POP=$1; GER=$2; shift 2
for n in "$@"; do python -W ignore otimiza_laboratorio.py $n $POP $GER 1 2 > saida/$n.log 2>&1; done
echo FIM > saida/FIM

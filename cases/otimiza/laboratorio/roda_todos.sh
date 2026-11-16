#!/bin/sh
# roda as 9 configuracoes em sequencia (2 processos cada). Uso: sh roda_todos.sh [pop] [geracoes]
POP=${1:-16}; GER=${2:-24}
for n in monoplano_cauda asa_voadora_pontas asa_voadora_central burgess_dunne bwb bwb_canard asa_em_caixa tandem duto_na_cauda; do
  python -W ignore otimiza_laboratorio.py $n $POP $GER 1 2 > saida/$n.log 2>&1
done
echo FIM > saida/FIM

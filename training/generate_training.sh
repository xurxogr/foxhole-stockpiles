#!/bin/bash

# This code is heavily based on https://github.com/GICodeWarrior/fir/blob/main/trainer/generate_quantities.sh

compute() {
  accuracy=3
  printf %.2f "$((10**${accuracy} * $1))e-${accuracy}"
}

create_image() {
  directory="$1"
  label="$2"

  echo "Processing: ${directory}/${label}"
  mkdir -p "$directory"

  # Hundreds of pt
  font_sizes=$(seq 800 50 2800)

  for font_size in $font_sizes; do
    file="${directory}/${label}${font_size}"
    font_size=$(compute ${font_size}/100)

    convert \
      -background white \
      -fill black \
      pango:'<span font="Renner*" size="'$font_size'pt">'"$label"'</span>' \
      -resize 500% \
      -threshold 66% \
      -trim \
      "${file}.png"
  done
}

generate_quantities() {
  # Normal quantities 0 to 999
  quantities=$(seq 0 999)
  for quantity in $quantities; do
    create_image "quantity_training/${quantity}" "${quantity}"
  done

  # 1k+ to 20k+. I don't expect a bunker to have more than 20k+ of anything
  quantities=$(seq 0 20)
  for quantity in $quantities; do
    create_image "quantity_training/${quantity}k+" "${quantity}k+"
  done
}

generate_stockpile_type() {
  Encampment=("Encampment" "Campement" "Feldlager" "Acampamento" "Лагерь" "营地")
  Keep=("Keep" "Place Forte" "Wehrturm" "Torreão" "Крепость" "要塞")
  Safe_House=("Safe House" "Planque" "Unterschlupf" "Casa Fortificada" "Yбeжищe" "安全屋")
  Relic_Base=("Relic Base" "Base Relique" "Reliktbasis" "Base Relíquia" "Peликтoвая база" "遗迹基地")
  Bunker_Base=("Bunker Base" "Base Bunker" "Bunkerbasis" "Centro do Bunker" "Base de Bunker" "Base de Casamata" "Бункерная база" "Бункерная База" "地堡基地")
  Border_Base=("Border Base" "Base Frontalière" "Grenzbasis" "Base Fronteiriça" "Пограничная База" "边境基地")
  Town_Base=("Town Base" "Quartier Général" "Stadtkernbasis" "Base de Cidade" "Ратуша" "城镇基地")
  BMS_Longhook=("BMS - Longhook")
  Storage_Depot=("Storage Depot" "Dépôt" "Lagerdepot" "Depósito" "Складское Помещение" "仓库")
  Seaport=("Seaport" "Port" "Seehafen" "Porto" "Морской порт" "海港")
  Undefined=("Undefined")

  keys=("Encampment" "Keep" "Safe_House" "Relic_Base" "Bunker_Base" "Border_Base" "Town_Base" "BMS_Longhook" "Storage_Depot" "Seaport" "Undefined")

  for key in "${keys[@]}"; do
      declare -n current_array="$key"  # Referencing the associative array by its name
      current_key="${current_array[0]}" # Referencing the first element of the array to get the key
      for i in "${!current_array[@]}"; do
        create_image "stockpile_type_training/${current_key}" "${current_array[$i]}"
      done
  done
}

generate_stockpile_type
generate_quantities

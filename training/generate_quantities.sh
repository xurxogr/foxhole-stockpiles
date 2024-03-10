#!/bin/bash

compute() {
  accuracy=3
  printf %.2f "$((10**${accuracy} * $1))e-${accuracy}"
}

quantities=("0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "k" "+" "x")

# Hundreds of pt
font_sizes=$(seq 800 25 2800)

for quantity in "${quantities[@]}"; do
  label="${quantity}"
  directory="quantity_training/${label}"

  echo "Processing: ${directory}"
  mkdir -p "$directory"

  for font_size in $font_sizes
  do
    file="${directory}/${font_size}"
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
done

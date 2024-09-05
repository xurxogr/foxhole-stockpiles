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

generate_quantities

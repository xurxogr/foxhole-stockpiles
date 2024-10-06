#!/bin/bash

download_langdata() {
    local langdata_folder=$1
    local langdata_url='https://raw.githubusercontent.com/tesseract-ocr/langdata_lstm/refs/heads/main/'
    local langs=("${@:2}")

    # Create the langdata directory if it doesn't exist
    mkdir -p ${langdata_folder}

    # Download the training_text files for each language if they don't already exist
    for lang in ${langs[@]}; do
        local training_text_file="${langdata_folder}/${lang}.training_text"
        local unicharset_file="${langdata_folder}/${lang}.unicharset"

        if [ ! -f "$training_text_file" ]; then
            echo "Downloading ${lang}.training_text..."
            wget -q "${langdata_url}${lang}/${lang}.training_text" -O "$training_text_file"
        fi

        if [ ! -f "$unicharset_file" ]; then
            echo "Downloading ${lang}.unicharset..."
            wget -q "${langdata_url}${lang}/${lang}.unicharset" -O "$unicharset_file"
        fi
    done
}

download_traineddata() {
    local langdata_folder=$1
    local langdata_url='https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/refs/heads/main/'
    local langs=("${@:2}")

    # Download the training_text files for each language if they don't already exist
    for lang in ${langs[@]}; do
        local dest_file="${langdata_folder}/${lang}.traineddata"
        if [ ! -f "$dest_file" ]; then
            echo "Downloading bestdata ${lang}.traineddata..."
            wget -q "${langdata_url}${lang}.traineddata" -O "$dest_file"
        fi
    done
}

clone_tesseract() {
    local tesseract_folder=$1
    if [ ! -d "$tesseract_folder" ]; then
        echo "Cloning tesseract repository..."
        git clone https://github.com/tesseract-ocr/tesseract.git "$tesseract_folder" > /dev/null 2>&1
    fi
}

clone_tesstrain() {
    local destination_folder=$1
    if [ ! -d "$destination_folder" ]; then
        echo "Cloning tesstrain repository..."
        git clone https://github.com/tesseract-ocr/tesstrain.git "$destination_folder" > /dev/null 2>&1
    fi
}

generate_numberslangdata() {
    local langdata_folder=$1

    local numbers_file="${langdata_folder}/numbers.training_text"

    # Check if the file already exists
    if [ -f "$numbers_file" ]; then
        return
    fi

    > "$numbers_file"  # Create or clear the file

    # Add numbers from 1 to 999
    for i in $(seq 0 999); do
        echo "$i" >> "$numbers_file"
    done

    # Add numbers from 1 to 50 followed by k+
    for i in $(seq 1 50); do
        echo "${i}k+" >> "$numbers_file"
    done
}

# Function to create training images from the training text
create_training_images() {
    local training_text_file=$1
    local output_directory=$2
    local font=$3
    local lang=$4
    local unicharset_file=$5
    local count=$6
    local char_spacing=$7

    # Create the output directory if it doesn't exist
    mkdir -p "$output_directory"

    # Read the training text file into an array of lines
    mapfile -t lines < "$training_text_file"

    # If a count is specified, limit the number of lines to the count
    if [ "$count" -gt 0 ]; then
        lines=("${lines[@]:0:$count}")
    fi

    line_count=0
    # Loop through each line in the lines array
    for line in "${lines[@]}"; do
        # Create a ground truth text file for each line
        line_training_text="$output_directory/${lang}_${line_count}.gt.txt"
        echo "$line" > "$line_training_text"

        file_base_name="${lang}_${line_count}"

        # Generate an image from the text using text2image
        text2image \
            --font="$font" \
            --fonts_dir=/usr/local/share/fonts \
            --text="$line_training_text" \
            --outputbase="$output_directory/$file_base_name" \
            --max_pages=1 \
            --strip_unrenderable_words \
            --leading=32 \
            --xsize=3600 \
            --ysize=480 \
            --char_spacing="$char_spacing" \
            --exposure=0 \
            --unicharset_file="$unicharset_file"

        ((line_count++))  # Increment the line count
    done

    # Remove empty .box files along with .tif and .gt.txt files
    for file in "$output_directory"/*.box; do
        if [ ! -s "$file" ]; then
            rm -f "$file" "${file%.box}.tif" "${file%.box}.gt.txt"
        fi
    done
}

# Main function to orchestrate the training image creation process
main() {
    local font=''                              # Default font to use
    local count=0                              # Default number of lines to process

    # Parse command line arguments
    while getopts "f:c:" opt; do
        case $opt in
            f) font="$OPTARG" ;;
            c) count="$OPTARG" ;;
            *) echo "Usage: $0 -f font -c count" >&2; exit 1 ;;
        esac
    done

    # Check if mandatory arguments are set
    if [ -z "$font" ] || [ "$count" -eq 0 ]; then
        echo "Usage: $0 -f font -c count" >&2
        exit 1
    fi

    local langdata_folder='langdata'           # Specify the langdata folder
    # Remove special characters from the font name to create a safe directory name
    local safe_font_name=$(echo "$font" | tr -cd '[:alnum:]' | tr '[:upper:]' '[:lower:]')
    local output_base_directory="tesstrain/data/${safe_font_name}"  # Specify the base output directory
    local languages=("eng" "numbers")

    # Download training text files for each language
    download_langdata "$langdata_folder" "${languages[@]}"

    # Clone the tesseract repository
    clone_tesseract "tesseract"
    clone_tesstrain "tesstrain"
    download_traineddata "tesseract/tessdata" "${languages[@]}"

    if [[ ! " ${languages[@]} " =~ " numbers " ]]; then
        # Copying english to "numbers"
        # Generate a numbers training text file
        generate_numberslangdata "$langdata_folder"

        cp tesseract/tessdata/eng.traineddata tesseract/tessdata/numbers.traineddata
        cp "$langdata_folder/eng.unicharset" "$langdata_folder/numbers.unicharset"
    fi

    # Loop through each language
    for lang in "${languages[@]}"; do
        echo "Creating training images for ${lang}..."
        local training_text_file="${langdata_folder}/${lang}.training_text"  # Specify the training text file
        local unicharset_file="${langdata_folder}/${lang}.unicharset"  # Specify the unicharset file

        # Use the English unicharset file for numbers
        if [ "$lang" == "numbers" ]; then
            char_spacing=0.1  # Set char_spacing to 0.1 for numbers
            lang_count=0  # Use all lines for numbers
        else
            char_spacing=1.0  # Set char_spacing to 1 for other languages
            lang_count=$count  # Use the specified count for other languages
        fi

        local output_directory="${output_base_directory}${lang}-ground-truth"  # Specify the output directory
        # Create training images for the current language
        create_training_images "$training_text_file" "$output_directory" "$font" "$lang" "$unicharset_file" "$lang_count" "$char_spacing"
    done
}

# Call the main function with all script arguments
#main "$@"
# This needs Renner font to be installed in the system
main -f 'Renner*' -c 1000

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os
from docling.document_converter import DocumentConverter
from flasgger import Swagger
import re
import json

app = Flask(__name__)
swagger = Swagger(app)

# Configurações
UPLOAD_FOLDER = './uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16 MB

def markdown_to_json(markdown_text):
    # Split the text into lines and remove empty lines
    lines = [line.strip() for line in markdown_text.split('\n') if line.strip()]
    
    # Remove the separator line (contains only |, -, and spaces)
    lines = [line for line in lines if not all(c in '|- ' for c in line)]
    
    # Get headers from the first line
    headers = [header.strip().lower().replace(' ', '_') for header in lines[0].split('|')[1:-1]]
    
    # Process data rows
    result = []
    for line in lines[1:]:
        # Split the line by | and remove empty strings
        values = [val.strip() for val in line.split('|')[1:-1]]
        
        # Create a dictionary for each row
        row_dict = {}
        for header, value in zip(headers, values):
            # Convert empty strings to None
            if value == '':
                value = None
            # Handle currency values with R$ prefix
            elif 'R$' in value:
                try:
                    # Remove R$ and any whitespace, replace comma with dot
                    cleaned_value = value.replace('R$', '').strip().replace(',', '.')
                    value = float(cleaned_value)
                except ValueError:
                    pass
            # Handle regular numeric values
            elif re.match(r'^[\d,]+\.?\d*$', value.replace(',', '.')):
                try:
                    value = float(value.replace(',', '.'))
                except ValueError:
                    pass
            row_dict[header] = value
        result.append(row_dict)
    
    return result


def parse_and_filter_data(doc_info):
    # Convert markdown to initial JSON structure
    data = markdown_to_json(doc_info)
    
    # Create a list to store filtered data
    filtered_data = []
    
    # Loop through each item and extract only needed fields
    for item in data:
        filtered_item = {
            'code': item.get('', '') or item.get('cód', '') or '' ,  # If key doesn't exist or is None, use empty string
            'reference': item.get('disponibilidade', '') or (str(item.get('esférico', '')) + ' ' + str(item.get('cilindrico', ''))) or '',  # If key doesn't exist or is None, use empty string
            'product': item.get('produto', '') or '',  # If key doesn't exist or is None, use empty string
            'price': item.get('valor', '') or ''  # If key doesn't exist or is None, use empty string
        }
        # Only include items that have a code (not empty)
        if filtered_item['code']:
            filtered_data.append(filtered_item)
    
    return json.dumps(filtered_data, indent=2, ensure_ascii=False)



@app.route('/process-file', methods=['POST'])
def process_file():
    """
    Processa um arquivo e retorna informações extraídas
    ---
    tags:
      - Arquivo
    consumes:
      - multipart/form-data
    parameters:
      - name: file
        in: formData
        type: file
        required: true
        description: O arquivo a ser processado
      - name: name
        in: formData
        type: string
        required: false
        description: Nome opcional para validação
    responses:
      200:
        description: Informações extraídas do arquivo
        schema:
          type: object
          properties:
            name:
              type: string
              description: Nome fornecido, se disponível
            data:
              type: object
              description: Dados extraídos do arquivo
      400:
        description: Erro de validação
      500:
        description: Erro interno do servidor
    """
    try:
        # Verifica se há um arquivo na requisição
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo encontrado na requisição.'}), 400

        file = request.files['file']

        # Verifica se o arquivo é válido
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400

        # Obtém o parâmetro opcional 'name'
        name = request.form.get('name', None)

        # Valida o parâmetro 'name' se necessário
        if name and not name.isalnum():
            return jsonify({'error': 'O nome fornecido é inválido. Apenas caracteres alfanuméricos são permitidos.'}), 400
     
        # Salva o arquivo enviado
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        converter = DocumentConverter()
        result = converter.convert(filepath)

        # Processa o arquivo com Docling
        doc_info = result.document.export_to_markdown()

        print(doc_info)

        data = markdown_to_json(doc_info)

        parsed_data = parse_and_filter_data(doc_info)


        # Remove o arquivo salvo após o processamento
        os.remove(filepath)

        # Retorna as informações extraídas em JSON
        return parsed_data

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
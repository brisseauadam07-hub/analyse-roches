# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif pour les graphiques
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'ta_cle_secrete'  # Nécessaire pour les messages flash
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['STATIC_FOLDER'] = 'static'
app.config['RESULTS_FOLDER'] = 'results'

# Créer les dossiers nécessaires
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['STATIC_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

def analyze_and_classify_image(image_path, roche_name=""):
    """Analyse et classification de l'image en niveaux de gris."""
    image = Image.open(image_path).convert('L')
    pixel_data = np.array(image)
    pixel_values = np.arange(256)
    pixel_counts = np.bincount(pixel_data.flatten(), minlength=256)
    total_pixels = np.sum(pixel_counts)

    # Générer l'histogramme
    hist_path = os.path.join(app.config['RESULTS_FOLDER'], "histogram.png")
    plt.figure(figsize=(12, 8))
    plt.plot(pixel_values, pixel_counts, color='blue', linewidth=2, zorder=3)
    plt.fill_between(pixel_values, pixel_counts, color='blue', zorder=3)
    plt.xlabel('Échelle de gris')
    plt.ylabel('Nombre de pixels')
    plt.suptitle('Fig. 1: Échelle de gris', fontsize=18, fontweight='bold')
    plt.title('0=Noir, 255=Blanc', fontsize=12)
    plt.xlim(0, 255)
    plt.grid(which='major', color='gray', linestyle='-', linewidth=0.8, zorder=2)
    plt.grid(which='minor', color='lightgray', linestyle=':', linewidth=0.5, zorder=1)
    plt.minorticks_on()
    plt.savefig(hist_path)
    plt.close()

    # 16 niveaux de gris
    levels = np.linspace(0, 255, 16, dtype=int)
    levels_path = os.path.join(app.config['RESULTS_FOLDER'], "levels.png")
    plt.figure(figsize=(12, 8))
    counts = {level: np.sum((pixel_data >= level) & (pixel_data < level + 255 / 16)) for level in levels}
    counts[255] = np.sum(pixel_data == 255)
    percentages = {level: (count / total_pixels) * 100 for level, count in counts.items()}
    plt.bar(percentages.keys(), percentages.values(), width=10, align='center', color='blue', zorder=3)
    plt.xlim(0, 255)
    plt.xlabel('Niveau de gris')
    plt.ylabel('Pourcentage de pixels (%)')
    plt.title('Fig. 2: Distribution des 16 teintes de gris', fontweight='bold', fontsize=18, pad=40)
    plt.grid(which='major', color='gray', linestyle='-', linewidth=0.8, zorder=2)
    plt.grid(which='minor', color='lightgray', linestyle=':', linewidth=0.5, zorder=1)
    plt.minorticks_on()
    plt.savefig(levels_path)
    plt.close()

    # Moyenne pondérée et classification
    weighted_average = np.sum(pixel_values * pixel_counts) / total_pixels
    intervals = {
        "Holomélanocrate": (0, 50),
        "Mélanocrate": (50, 100),
        "Mésocrate": (100, 150),
        "Leucocrate": (150, 200),
        "Hololeucocrate": (200, 255)
    }
    dominant_category = next((cat for cat, (low, high) in intervals.items() if low <= weighted_average < high), None)

    return {
        'total_pixels': total_pixels,
        'weighted_average': weighted_average,
        'dominant_category': dominant_category,
        'hist_path': hist_path.replace('\\', '/'),
        'levels_path': levels_path.replace('\\', '/'),
        'roche_name': roche_name
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        roche_name = request.form.get('roche_name', '')
        if 'image' not in request.files:
            flash('Aucun fichier sélectionné')
            return redirect(request.url)
        file = request.files['image']
        if file.filename == '':
            flash('Aucun fichier sélectionné')
            return redirect(request.url)
        if file:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(image_path)
            results = analyze_and_classify_image(image_path, roche_name)
            return render_template('results.html', results=results)
    return render_template('index.html')

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    results = {
        'total_pixels': int(request.form['total_pixels']),
        'weighted_average': float(request.form['weighted_average']),
        'dominant_category': request.form['dominant_category'],
        'hist_path': request.form['hist_path'],
        'levels_path': request.form['levels_path'],
        'roche_name': request.form['roche_name']
    }

    # Créer un PDF en mémoire
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Ajouter les graphiques
    c.drawImage(results['hist_path'], 30, height - 360, width=350, height=250)
    c.drawImage(results['levels_path'], 30, height - 600, width=350, height=250)

    # Ajouter les résultats textuels
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 100, f"Nom de la roche : {results['roche_name']}")
    c.drawString(100, height - 130, f"Nombre total de pixels : {results['total_pixels']}")
    c.drawString(100, height - 160, f"Moyenne pondérée : {results['weighted_average']:.0f}")
    c.drawString(100, height - 190, f"Catégorie : {results['dominant_category']}")

    # Ajouter une légende
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 700, "Plus le pourcentage de minéraux sombres est grand, plus la roche est dite mafique.")

    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="resultats_analyse.pdf",
        mimetype='application/pdf'
    )

from flask import send_file

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.config['STATIC_FOLDER'], filename)

@app.route('/results/<path:filename>')
def result_files(filename):
    return send_from_directory(app.config['RESULTS_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

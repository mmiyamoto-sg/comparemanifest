from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_session import Session
from compare_manifest import (
    extract_three_digit_number,
    normalize_section_name,
    apply_rules,
    load_csv,
    compare_manifests
)
import csv
import os
import pandas as pd
from io import StringIO

app = Flask(__name__)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = os.urandom(24)  # This is for session encryption
Session(app)

@app.route("/", methods=["GET", "POST"])
def index():

    differences = []

    if "rules" not in session:
        session["rules"] = ""
    
    if request.method == "POST":
        """csv_contents1 = csv_contents2 = ''
        if 'sgmanifest' in request.files:
            csv_file1 = request.files['sgmanifest']

            if csv_file1.filename != '':
                csv_contents1 = csv_file1.read().decode('utf-8')
        
        if 'clientmanifest' in request.files:
            csv_file2 = request.files['clientmanifest']

            if csv_file2.filename != '':
                csv_contents2 = csv_file2.read().decode('utf-8')"""
        ##uploaded_files = request.files.getlist('manifests')
        
        # Make sure we have both manifests
        """if len(uploaded_files) == 2:
            for file in uploaded_files:
                if file.filename == 'seatgeek_manifest.csv':
                    session['seatgeek_manifest_text'] = file.read().decode('utf-8')
                elif file.filename == 'client_manifest.csv':
                    session['client_manifest_text'] = file.read().decode('utf-8')"""
        if 'csv1' in request.form and 'csv2' in request.form:
            session['client_manifest_text'] = request.form['csv2']
            session['seatgeek_manifest_text'] = request.form['csv1']

            
            rules_text = request.form['rules']
            session["rules"] = rules_text
            session["differences"] = perform_comparison(session.get
            ('seatgeek_manifest_text', ''), session.get('client_manifest_text', ''), rules_text)

            #print(session['seatgeek_manifest_text'])
            
        # Try if statement where upload is 0. Must store csv from first action in variable or text area to be used over and over again within session because POST can't pre-populate input fields due to security
        


    return render_template("index.html", differences=session.get("differences", []), rules=session["rules"])


@app.route('/download/differences', methods=['GET'])
def download_differences():
    with open("differences.txt", "w") as f:
        for diff in session.get("differences", []):
            f.write(diff + "\n")
    return send_from_directory('.', 'differences.txt', as_attachment=True, download_name='differences.txt')

@app.route('/download/rules')
def download_rules():
    with open("rules.txt", "w") as f:
        f.write(session.get("rules", ""))
    return send_from_directory('.', 'rules.txt', as_attachment=True, download_name='rules.txt')

def perform_comparison(seatgeek_text, client_text, rules_text):
    # Save files temporarily for processing
    with open("temp_seatgeek.csv", "w") as f:
        f.write(seatgeek_text)
    
    with open("temp_client.csv", "w") as f:
        f.write(client_text)
    
    rules = load_rules_from_text(rules_text)

    seatgeek_manifest_sections = set()

    with open('temp_seatgeek.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            section_value = row.get('SECTION', row.get('section', '')).lower()
            seatgeek_manifest_sections.add(section_value)
        
    seatgeek_manifest = load_csv('temp_seatgeek.csv', rules, seatgeek_manifest_sections)
    client_manifest = load_csv('temp_client.csv', rules, seatgeek_manifest_sections)

    return compare_manifests(seatgeek_manifest, client_manifest)

def load_rules_from_text(text):
    # Adapt the load_rules function to work with direct text input
    rules = {}
    lines = text.strip().split("\n")
    for line in lines:
        # Check if the line contains the delimiter before splitting
        if ' > ' in line:
            pattern, replace = line.strip().split(' > ')
            pattern = pattern.replace(" ", "-")
            replace = replace.replace(" ", "-")
            rules[pattern] = replace
    return rules


if __name__ == "__main__":
    app.run(debug=True)

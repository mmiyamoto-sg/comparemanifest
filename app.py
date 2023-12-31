from flask import Flask, render_template, request, session, send_from_directory
from flask_session import Session
from compare_manifest import (
    load_csv,
    compare_manifests
)
import csv
import os
from sys import platform
from enum import Enum

class OS(Enum):
    windows = 1
    darwin =2 

os_name = OS.windows if platform.lower().startswith('win') else OS.darwin


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
        if 'csv1' in request.form and 'csv2' in request.form:
            session['client_manifest_text'] = request.form['csv2']
            session['seatgeek_manifest_text'] = request.form['csv1']

            rules_text = request.form['rules']
            session["rules"] = rules_text
            analyze_seat_level = True if request.form['analysisLevel'] == 'seatLevel' else False
            session['analysisLevel'] = analyze_seat_level
            (diff_1, diff_2, count_1, count_2, diff_csv) = perform_comparison(session.get('seatgeek_manifest_text', ''), 
                                                                                      session.get('client_manifest_text', ''), rules_text, analyze_seat_level)
            session['differences'] = diff_csv
            count_1 = str(count_1)+' Potential Issues'
            count_2 = str(count_2)+' Potential Issues'
        return render_template("index3.html", differences_1=diff_1, differences_2 = diff_2, count_1=count_1, count_2=count_2, rules=session["rules"])
    
    return render_template("index3.html", differences_1='', differences_2 = '', count_1='', count_2='', rules=session["rules"])


@app.route('/download/differences', methods=['GET'])
def download_differences():
    with open("differences.csv", "w") as f:
        differences = session.get("differences", '')
        for diff in differences.split('\n'):
            if not diff or len(diff.strip()) < 2:
                continue
            if os_name == OS.windows:
                f.write(diff)
            else:
                f.write(diff + "\n")
    return send_from_directory('.', 'differences.csv', as_attachment=True, download_name='differences.csv')

@app.route('/download/rules')
def download_rules():
    with open("rules.txt", "w") as f:
        f.write(session.get("rules", ""))
    return send_from_directory('.', 'rules.txt', as_attachment=True, download_name='rules.txt')

def perform_comparison(seatgeek_text, client_text, rules_text, analyze_seat_level):
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
        
    seatgeek_manifest = load_csv('temp_seatgeek.csv', rules, seatgeek_manifest_sections, analyze_seat_level)
    client_manifest = load_csv('temp_client.csv', rules, seatgeek_manifest_sections, analyze_seat_level)

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

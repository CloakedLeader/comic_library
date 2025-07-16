import os

from flask import Flask, render_template_string, send_from_directory

app = Flask(__name__)
FILE_DIRECTORY = "D:\\comic_library\\comic_examples"


@app.route("/")
def index():
    files = os.listdir(FILE_DIRECTORY)
    html = """
        <h1>Available Files</h1>
        <ul>
        {% for file in files %}
            <li><a href="/download/{{ file }}">{{ file }}</a></li>
        {% endfor %}
        </ul>
    """
    return render_template_string(html, files=files)


@app.route("/download/<path:filename>")
def download(filename):
    return send_from_directory(FILE_DIRECTORY, filename, as_attachment=True)

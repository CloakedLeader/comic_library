from flask import Flask, send_from_directory, render_template_string, jsonify
import os

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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0" port=5000)

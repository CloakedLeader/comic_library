from flask import Flask, jsonify, render_template
import os

app = Flask(__name__, static_url_path='/static')

FILE_DIR = 'comic_folder'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/files')
def list_files():
    files = os.listdir(FILE_DIR)
    print("FILES", files)
    return jsonify(files)

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
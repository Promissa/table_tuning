from flask import Flask, request, send_file, render_template, jsonify
import os
import shutil
import sys
from werkzeug.utils import secure_filename
import tempfile, json
from src import html_parsing, html2csv
from io import BytesIO
import zipfile

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(sys.path[0], "data")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/")
def index():
    return render_template(
        "/Users/bytedance/projects/table_tuning/templates/index.html"
    )


@app.route("/process", methods=["POST"])
def process():
    try:
        file = request.files["file"]
        if not file:
            return jsonify(error="No selected file"), 400
        html_content = file.read().decode("utf-8")
        processed_html = html_parsing.parse_html(html_content)
        csv_tables, table_map = html2csv.process(processed_html)
        return jsonify({"csv_tables": csv_tables, "table_map": table_map})
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/upload_csv", methods=["POST"])
def upload_csv():
    if "files" not in request.files:
        return jsonify(error="No file part"), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify(error="No selected file"), 400

    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], "csv_uploads")
    shutil.rmtree(upload_dir)
    os.makedirs(upload_dir)

    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)

    return jsonify(message="CSV files uploaded successfully")


@app.route("/update_csv", methods=["POST"])
def update_csv():
    try:
        data = request.get_json()
        filename = data["filename"]
        content = data["content"]

        upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], "csv_uploads")
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "w") as f:
            f.write(content)

        return jsonify(message="CSV file updated successfully")
    except Exception as e:
        print(f"Error updating CSV file: {e}")  # Add this line
        return jsonify(error=str(e)), 500


@app.route("/download_csv", methods=["GET"])
def download_csv():
    upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], "csv_uploads")
    if not os.path.exists(upload_dir):
        return jsonify(error="No CSV files found"), 404

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(upload_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zf.write(file_path, os.path.basename(file_path))

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="tables.zip",
    )


if __name__ == "__main__":
    app.run(debug=True)

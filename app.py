import os
import json
import re
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
from pypdf import PdfReader
import requests

app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

OLLAMA_MODEL = "llama3.2"


def extract_text(path):
    reader = PdfReader(path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.strip()


def generate_quiz(text, n=5):

    text = text[:8000]

    prompt = f"""
Create exactly {n} multiple choice questions from the study text below.

Return ONLY valid JSON.

Use exactly this format:

[
  {{
    "question": "Question here?",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer": "Correct option exactly"
  }}
]

Do not write explanations.
Do not use markdown.
Do not write ```json.

STUDY TEXT:
{text}
"""

    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=600
    )

    response.raise_for_status()

    raw = response.json().get("response", "").strip()

    # Remove markdown if Ollama returns it
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Find JSON array
    match = re.search(r'\[.*\]', raw, re.DOTALL)

    if not match:
        print("OLLAMA RESPONSE:")
        print(raw)
        raise ValueError("Quiz JSON was not generated correctly.")

    quiz = json.loads(match.group())

    if not isinstance(quiz, list) or len(quiz) == 0:
        raise ValueError("No quiz questions generated.")

    # Validate questions
    valid_quiz = []

    for q in quiz:
        if (
            isinstance(q, dict)
            and "question" in q
            and "options" in q
            and "answer" in q
            and isinstance(q["options"], list)
        ):
            valid_quiz.append(q)

    if not valid_quiz:
        raise ValueError("Generated quiz format is invalid.")

    return valid_quiz


@app.route("/", methods=["GET", "POST"])
def index():

    quiz = None
    error = None

    if request.method == "POST":

        try:

            file = request.files.get("file")

            if not file or file.filename == "":
                raise ValueError("Please choose a PDF file.")

            count = int(request.form.get("count", 5))

            filename = secure_filename(file.filename)

            path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            file.save(path)

            text = extract_text(path)

            if not text:
                raise ValueError(
                    "Could not extract text from this PDF."
                )

            quiz = generate_quiz(text, count)

        except Exception as e:

            print("ERROR:", str(e))

            error = "Quiz could not be generated. Please try again."

    return render_template(
        "index.html",
        quiz=quiz,
        error=error
    )


if __name__ == "__main__":
    app.run(debug=True)
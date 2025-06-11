from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

# PostgreSQL connection settings
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "distributor_db",
    "user": "distri",
    "password": "password"  # Change this!
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Create distributor_info table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS distributor_info (
            id SERIAL PRIMARY KEY,
            distributor_name TEXT,
            contact_person TEXT,
            email TEXT,
            phone TEXT,
            address TEXT
        )
    """)

    # Create distributor_answers table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS distributor_answers (
            id SERIAL PRIMARY KEY,
            distributor_id INTEGER REFERENCES distributor_info(id),
            question_number INTEGER,
            answer TEXT
        )
    """)

    conn.commit()
    conn.close()

# 👇 Call this right after defining the function
init_db()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("form.html", {"request": request})

@app.post("/submit")
def submit_form(
    distributor_name: str = Form(...),
    contact_person: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...)
):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO distributor_info (distributor_name, contact_person, email, phone, address)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    ''', (distributor_name, contact_person, email, phone, address))
    distributor_id = cur.fetchone()['id']
    conn.commit()
    conn.close()
    return RedirectResponse(f"/questions.html?distributor_id={distributor_id}", status_code=303)

@app.get("/questions.html", response_class=HTMLResponse)
def show_questions(request: Request):
    return templates.TemplateResponse("questions.html", {"request": request})

@app.post("/submit-answers")
async def submit_answers(request: Request):
    form = await request.form()
    distributor_id = int(form.get("distributor_id"))
    conn = get_conn()
    cur = conn.cursor()
    for i in range(1, 11):
        answer = form.get(f"q{i}")
        cur.execute(
            "INSERT INTO distributor_answers (distributor_id, question_number, answer) VALUES (%s, %s, %s)",
            (distributor_id, i, answer)
        )
    conn.commit()
    conn.close()
    return HTMLResponse(content="""
  <html>
  <head>
    <style>
      body { font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; text-align: center; }
      .card { background: white; padding: 40px; margin: auto; max-width: 400px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
      .btn {
        background: #007bff;
        color: white;
        border: none;
        padding: 10px 20px;
        font-size: 16px;
        border-radius: 5px;
        text-decoration: none;
      }
      .btn:hover { background: #0056b3; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Thank you!</h2>
      <p>Your submission has been recorded.</p>
      <a class="btn" href="/">Go to Home Page</a>
    </div>
  </body>
  </html>
""", status_code=200)


@app.get("/view-submissions", response_class=HTMLResponse)
def view_submissions():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM distributor_info")
    info_rows = cur.fetchall()
    cur.execute("SELECT * FROM distributor_answers")
    answer_rows = cur.fetchall()
    conn.close()

    html = "<h2>Distributor Info</h2><table border='1'><tr><th>ID</th><th>Name</th><th>Contact</th><th>Email</th><th>Phone</th><th>Address</th></tr>"
    for row in info_rows:
        html += f"<tr>{''.join(f'<td>{cell}</td>' for cell in row.values())}</tr>"
    html += "</table><br><h2>Distributor Answers</h2><table border='1'><tr><th>ID</th><th>Distributor ID</th><th>Q No</th><th>Answer</th></tr>"
    for row in answer_rows:
        html += f"<tr>{''.join(f'<td>{cell}</td>' for cell in row.values())}</tr>"
    html += "</table>"
    return HTMLResponse(content=html)

@app.get("/export-excel")
def export_excel():
    conn = get_conn()

    # Fetch data
    df_info = pd.read_sql_query("SELECT * FROM distributor_info", conn)
    df_answers = pd.read_sql_query("SELECT * FROM distributor_answers", conn)

    # Explicitly rename the columns to avoid header issues
    df_answers.columns = ["id", "distributor_id", "question_number", "answer"]

    # Write to Excel
    output_file = "distributor_data.xlsx"
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df_info.to_excel(writer, sheet_name="Distributor Info", index=False)
        df_answers.to_excel(writer, sheet_name="Answers", index=False)

    conn.close()
    return FileResponse(path=output_file, filename="distributor_data.xlsx")

@app.get("/api/distributor-info")
def get_distributor_info():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM distributor_info", conn)
    conn.close()
    return JSONResponse(content=df.to_dict(orient="records"))

@app.get("/api/distributor-answers")
def get_distributor_answers():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM distributor_answers", conn)
    conn.close()
    return JSONResponse(content=df.to_dict(orient="records"))

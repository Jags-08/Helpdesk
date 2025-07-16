from flask import Flask, render_template, request, redirect, send_file, session, url_for
from werkzeug.utils import secure_filename
from fpdf import FPDF
import os
import uuid
import smtplib
import sqlite3
import csv

app = Flask(__name__)
app.secret_key = "secret-key"

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DATABASE = 'tickets.db'

# EMAIL SETTINGS (Update these with real credentials)
EMAIL_SENDER = 'your-email@gmail.com'
EMAIL_PASSWORD = 'your-app-password'
EMAIL_RECEIVER = 'admin-email@gmail.com'

# ----------------- DATABASE SETUP --------------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT,
        name TEXT,
        role TEXT,
        email TEXT,
        category TEXT,
        title TEXT,
        description TEXT,
        image TEXT,
        status TEXT DEFAULT 'Open'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY,
        password TEXT
    )''')
    # Default admin
    c.execute("INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)", ("admin", "admin123"))
    conn.commit()
    conn.close()

init_db()

# ----------------- EMAIL --------------------
def send_email(subject, body):
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            message = f"Subject: {subject}\n\n{body}"
            smtp.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, message)
    except Exception as e:
        print("Email error:", e)

# ----------------- ROUTES --------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"]
    role = request.form["role"]
    email = request.form["email"]
    category = request.form["category"]
    title = request.form["title"]
    description = request.form["description"]
    image_file = request.files["image"]

    ticket_id = str(uuid.uuid4())[:8]
    filename = ""

    if image_file and image_file.filename != "":
        filename = secure_filename(ticket_id + "_" + image_file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image_file.save(image_path)

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT INTO tickets (ticket_id, name, role, email, category, title, description, image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
              (ticket_id, name, role, email, category, title, description, filename))
    conn.commit()
    conn.close()

    # Email notification
    subject = f"New Ticket Submitted: {ticket_id}"
    body = f"Title: {title}\nName: {name}\nCategory: {category}\nDescription:\n{description}"
    send_email(subject, body)

    return render_template("success.html", ticket_id=ticket_id)

@app.route("/track")
def track():
    return render_template("track.html")

@app.route("/ticket/<ticket_id>")
def ticket_view(ticket_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
    ticket = c.fetchone()
    conn.close()
    if not ticket:
        return "Ticket not found"
    return render_template("ticket_view.html", ticket=ticket)

@app.route("/close/<ticket_id>")
def close_ticket(ticket_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("UPDATE tickets SET status='Closed' WHERE ticket_id=?", (ticket_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or "/admin")

@app.route("/download/<ticket_id>")
def download_pdf(ticket_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
    ticket = c.fetchone()
    conn.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Ticket Report", ln=True, align='C')
    pdf.ln(10)

    labels = ["Ticket ID", "Name", "Role", "Email", "Category", "Title", "Description", "Status"]
    for i, label in enumerate(labels):
        pdf.cell(40, 10, f"{label}:", ln=0)
        pdf.cell(150, 10, str(ticket[i+1]), ln=1)

    pdf_path = f"static/{ticket_id}.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True)

# ----------------- ADMIN LOGIN --------------------

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form["username"]
        pw = request.form["password"]
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM admins WHERE username=? AND password=?", (user, pw))
        admin = c.fetchone()
        conn.close()
        if admin:
            session["admin"] = user
            return redirect("/admin")
        else:
            return "Invalid credentials"
    return render_template("admin_login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/admin_login")

@app.route("/admin", methods=["GET"])
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin_login")

    filter_category = request.args.get("filter", "")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    if filter_category:
        c.execute("SELECT * FROM tickets WHERE category=?", (filter_category,))
    else:
        c.execute("SELECT * FROM tickets")
    tickets = c.fetchall()
    conn.close()
    return render_template("admin_dashboard.html", tickets=tickets)

@app.route("/export_csv", methods=["POST"])
def export_csv():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM tickets")
    tickets = c.fetchall()
    conn.close()

    csv_path = "static/tickets.csv"
    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["ID", "Ticket ID", "Name", "Role", "Email", "Category", "Title", "Description", "Image", "Status"])
        for t in tickets:
            writer.writerow(t)

    return send_file(csv_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)

"""
CampusBoard - College Event Management System (Flask + SQLite)

Setup:
    pip install flask
    python app.py
Open http://127.0.0.1:5000

Organizer login: http://127.0.0.1:5000/admin  (password from ADMIN_PASSWORD env var, default "admin123")
"""
import csv, io, os, re, secrets, sqlite3
from datetime import date, timedelta
from flask import (Flask, Response, flash, g, redirect, render_template_string,
                   request, session, url_for)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.db")
CATEGORIES = ["Technical", "Cultural", "Sports", "Career"]


# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL,
        venue TEXT NOT NULL, category TEXT NOT NULL,
        seats INTEGER NOT NULL, description TEXT);
    CREATE TABLE IF NOT EXISTS registrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket TEXT UNIQUE NOT NULL,
        event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        name TEXT NOT NULL, roll TEXT NOT NULL, email TEXT NOT NULL,
        UNIQUE(event_id, roll));
    """)
    if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
        d = lambda n: (date.today() + timedelta(days=n)).isoformat()
        conn.executemany(
            "INSERT INTO events(title,date,time,venue,category,seats,description) VALUES(?,?,?,?,?,?,?)",
            [("Hackathon 24: Build for Campus", d(6), "09:00", "Innovation Lab", "Technical", 120,
              "24 hours, teams of 3-4. Solve a real problem from campus life."),
             ("Spring Fest Open Mic", d(9), "17:30", "Amphitheatre", "Cultural", 200,
              "Music, poetry and stand-up. Sign up to perform or just watch."),
             ("Inter-Department Cricket Cup", d(12), "08:00", "Main Ground", "Sports", 80,
              "Knockout format. Each department fields one team of 11."),
             ("Placement Prep: Resume Clinic", d(15), "14:00", "Seminar Hall B", "Career", 60,
              "Bring your resume. Alumni give one-to-one feedback."),
             ("Intro to Machine Learning Workshop", d(19), "10:30", "Computer Centre 2", "Technical", 40,
              "Hands-on session with Python. Bring a laptop.")])
    conn.commit()
    conn.close()


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper


# ---------- templates ----------
BASE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CampusBoard</title>
<style>
:root{--bg:#f5f7fb;--card:#fff;--ink:#16203a;--muted:#5d6985;--line:#dde3ee;--accent:#2547f5;--hi:#ffd84d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,sans-serif;line-height:1.5}
.wrap{max-width:860px;margin:0 auto;padding:0 18px}
header{border-bottom:1px solid var(--line)}header .wrap{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;flex-wrap:wrap;gap:8px}
.logo{font-weight:800;font-size:1.25rem;color:var(--ink);text-decoration:none}.logo span{background:var(--hi);padding:0 6px;border-radius:4px}
nav a{color:var(--muted);font-weight:600;text-decoration:none;margin-left:14px}nav a:hover{color:var(--accent)}
h1{font-size:2.2rem;letter-spacing:-.03em;margin:28px 0 6px}.sub{color:var(--muted);margin:0 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:12px}
.card h3{margin:0 0 4px}.meta{color:var(--muted);font-size:.92rem;margin:0 0 8px}
.tag{background:var(--hi);padding:1px 8px;border-radius:4px;font-size:.8rem;font-weight:600;margin-right:6px}
input,select,textarea{font:inherit;width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:#fff}
label{display:block;font-weight:600;font-size:.9rem;margin:12px 0 4px}
.btn{font:inherit;font-weight:600;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 16px;cursor:pointer;text-decoration:none;display:inline-block}
.btn.ghost{background:none;color:var(--ink);border:1px solid var(--line)}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.row>*{flex:1 1 160px}.row .btn{flex:0 0 auto}
.flash{padding:10px 14px;border-radius:8px;margin:14px 0;background:#e6f4ec;color:#16794c;font-weight:600}
.flash.error{background:#fdeae6;color:#b3361f}
.meter{height:6px;background:var(--line);border-radius:9px;overflow:hidden}.meter i{display:block;height:100%;background:var(--accent)}
.empty{padding:30px;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:12px}
table{width:100%;border-collapse:collapse;font-size:.92rem}td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
</style></head><body>
<header><div class="wrap"><a class="logo" href="{{ url_for('home') }}"><span>Campus</span>Board</a>
<nav><a href="{{ url_for('home') }}">Events</a><a href="{{ url_for('tickets') }}">My tickets</a>
{% if session.admin %}<a href="{{ url_for('admin') }}">Organizer</a><a href="{{ url_for('logout') }}">Logout</a>
{% else %}<a href="{{ url_for('login') }}">Organizer</a>{% endif %}</nav></div></header>
<main class="wrap">
{% for cat, msg in get_flashed_messages(with_categories=true) %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}
{% block body %}{% endblock %}</main></body></html>
"""

HOME = """{% extends base %}{% block body %}
<h1>What's happening on campus</h1>
<p class="sub">Find fests, workshops and talks. Register in under a minute.</p>
<form class="row" method="get" style="margin-bottom:18px">
  <input name="q" value="{{ q }}" placeholder="Search events or venues">
  <select name="cat"><option value="">All categories</option>
    {% for c in cats %}<option {{ 'selected' if c==cat }}>{{ c }}</option>{% endfor %}</select>
  <button class="btn">Search</button></form>
{% for e in events %}
<div class="card"><h3>{{ e.title }}</h3>
  <p class="meta"><span class="tag">{{ e.category }}</span>{{ e.date }} at {{ e.time }} &middot; {{ e.venue }}</p>
  <p>{{ e.description }}</p>
  <div class="meter"><i style="width:{{ [100, e.taken / e.seats * 100]|min }}%"></i></div>
  <div class="row" style="margin-top:10px"><span class="meta">{{ e.seats - e.taken }} of {{ e.seats }} seats left</span>
  {% if e.seats - e.taken > 0 %}<a class="btn" href="{{ url_for('register', event_id=e.id) }}">Register</a>
  {% else %}<span class="meta"><b>Event full</b></span>{% endif %}</div></div>
{% else %}<div class="empty">No events match your search.</div>{% endfor %}
{% endblock %}"""

REGISTER = """{% extends base %}{% block body %}
<h1>Register</h1><p class="sub">{{ e.title }} &middot; {{ e.date }} at {{ e.time }}, {{ e.venue }}</p>
<form method="post" class="card">
  <label>Full name</label><input name="name" value="{{ f.get('name','') }}" required>
  <label>Roll number</label><input name="roll" value="{{ f.get('roll','') }}" required>
  <label>College email</label><input name="email" type="email" value="{{ f.get('email','') }}" required>
  <div style="margin-top:16px"><button class="btn">Confirm registration</button>
  <a class="btn ghost" href="{{ url_for('home') }}">Cancel</a></div></form>
{% endblock %}"""

TICKETS = """{% extends base %}{% block body %}
<h1>My tickets</h1><p class="sub">Look up your registrations with your roll number.</p>
<form class="row" method="get" style="margin-bottom:18px"><input name="roll" value="{{ roll }}" placeholder="Roll number" required>
<button class="btn">Find tickets</button></form>
{% for t in rows %}<div class="card"><h3>{{ t.title }}</h3>
<p class="meta">{{ t.date }} at {{ t.time }} &middot; {{ t.venue }}</p>
<p>Ticket <b>{{ t.ticket }}</b> &middot; {{ t.name }}</p>
<form method="post" action="{{ url_for('cancel', ticket=t.ticket) }}" onsubmit="return confirm('Cancel this registration?')">
<input type="hidden" name="roll" value="{{ roll }}"><button class="btn ghost">Cancel registration</button></form></div>
{% else %}{% if roll %}<div class="empty">No tickets found for this roll number.</div>{% endif %}{% endfor %}
{% endblock %}"""

LOGIN = """{% extends base %}{% block body %}
<h1>Organizer login</h1><form method="post" class="card" style="max-width:380px">
<label>Password</label><input type="password" name="password" required autofocus>
<div style="margin-top:16px"><button class="btn">Log in</button></div></form>{% endblock %}"""

ADMIN = """{% extends base %}{% block body %}
<h1>Organizer desk</h1>
<p class="sub">{{ events|length }} events &middot; {{ total }} registrations</p>
<form method="post" action="{{ url_for('add_event') }}" class="card"><h3>New event</h3>
  <label>Title</label><input name="title" required maxlength="70">
  <div class="row"><div><label>Date</label><input type="date" name="date" required></div>
  <div><label>Time</label><input type="time" name="time" value="10:00" required></div></div>
  <div class="row"><div><label>Venue</label><input name="venue" required maxlength="50"></div>
  <div><label>Seats</label><input type="number" name="seats" min="1" value="100" required></div></div>
  <label>Category</label><select name="category">{% for c in cats %}<option>{{ c }}</option>{% endfor %}</select>
  <label>Description</label><textarea name="description" rows="2" maxlength="200"></textarea>
  <div style="margin-top:14px"><button class="btn">Publish event</button></div></form>
<h2>Registrations</h2>
{% for e in events %}<details class="card"><summary><b>{{ e.title }}</b> &mdash; {{ e.regs|length }}/{{ e.seats }}</summary>
{% if e.regs %}<table><tr><th>Name</th><th>Roll</th><th>Email</th></tr>
{% for r in e.regs %}<tr><td>{{ r.name }}</td><td>{{ r.roll }}</td><td>{{ r.email }}</td></tr>{% endfor %}</table>{% else %}<p class="meta">No registrations yet.</p>{% endif %}
<div class="row" style="margin-top:10px">
<a class="btn ghost" href="{{ url_for('export', event_id=e.id) }}">Export CSV</a>
<form method="post" action="{{ url_for('delete_event', event_id=e.id) }}" onsubmit="return confirm('Delete this event and its registrations?')">
<button class="btn ghost">Delete event</button></form></div></details>{% endfor %}
{% endblock %}"""


def render(tpl, **ctx):
    return render_template_string(tpl, base=BASE_TEMPLATE, cats=CATEGORIES, **ctx)


# Jinja needs the base as a named template for {% extends base %}
from jinja2 import DictLoader
BASE_TEMPLATE = "base.html"
app.jinja_loader = DictLoader({"base.html": BASE})


# ---------- public routes ----------
@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    cat = request.args.get("cat", "")
    sql = """SELECT e.*, (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id) AS taken
             FROM events e WHERE (e.title LIKE ? OR e.venue LIKE ?)"""
    args = [f"%{q}%", f"%{q}%"]
    if cat in CATEGORIES:
        sql += " AND e.category=?"
        args.append(cat)
    events = db().execute(sql + " ORDER BY e.date, e.time", args).fetchall()
    return render(HOME, events=events, q=q, cat=cat)


@app.route("/register/<int:event_id>", methods=["GET", "POST"])
def register(event_id):
    e = db().execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not e:
        flash("Event not found.", "error")
        return redirect(url_for("home"))
    f = request.form
    if request.method == "POST":
        name, roll, email = (f.get(k, "").strip() for k in ("name", "roll", "email"))
        taken = db().execute("SELECT COUNT(*) FROM registrations WHERE event_id=?", (event_id,)).fetchone()[0]
        if not (name and roll):
            flash("Enter your name and roll number.", "error")
        elif not re.match(r"^\S+@\S+\.\S+$", email):
            flash("Enter a valid email address.", "error")
        elif taken >= e["seats"]:
            flash("Sorry, this event is full.", "error")
        else:
            ticket = f"CB-{event_id}-{secrets.token_hex(2).upper()}"
            try:
                db().execute("INSERT INTO registrations(ticket,event_id,name,roll,email) VALUES(?,?,?,?,?)",
                             (ticket, event_id, name, roll, email))
                db().commit()
                flash(f"Registered! Your ticket ID is {ticket}.", "ok")
                return redirect(url_for("tickets", roll=roll))
            except sqlite3.IntegrityError:
                flash("This roll number is already registered for this event.", "error")
    return render(REGISTER, e=e, f=f)


@app.route("/tickets")
def tickets():
    roll = request.args.get("roll", "").strip()
    rows = []
    if roll:
        rows = db().execute("""SELECT r.ticket, r.name, e.title, e.date, e.time, e.venue
            FROM registrations r JOIN events e ON e.id=r.event_id
            WHERE LOWER(r.roll)=LOWER(?) ORDER BY e.date""", (roll,)).fetchall()
    return render(TICKETS, rows=rows, roll=roll)


@app.route("/cancel/<ticket>", methods=["POST"])
def cancel(ticket):
    roll = request.form.get("roll", "")
    db().execute("DELETE FROM registrations WHERE ticket=? AND LOWER(roll)=LOWER(?)", (ticket, roll))
    db().commit()
    flash("Registration cancelled.", "ok")
    return redirect(url_for("tickets", roll=roll))


# ---------- organizer routes ----------
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if secrets.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Wrong password.", "error")
    return render(LOGIN)


@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin():
    events = [dict(e) for e in db().execute("SELECT * FROM events ORDER BY date, time")]
    total = 0
    for e in events:
        e["regs"] = db().execute("SELECT name, roll, email FROM registrations WHERE event_id=?", (e["id"],)).fetchall()
        total += len(e["regs"])
    return render(ADMIN, events=events, total=total)


@app.route("/admin/add", methods=["POST"])
@admin_required
def add_event():
    f = request.form
    try:
        seats = max(1, int(f.get("seats", 0)))
    except ValueError:
        seats = 100
    cat = f.get("category") if f.get("category") in CATEGORIES else CATEGORIES[0]
    db().execute("INSERT INTO events(title,date,time,venue,category,seats,description) VALUES(?,?,?,?,?,?,?)",
                 (f["title"].strip(), f["date"], f["time"], f["venue"].strip(), cat, seats,
                  f.get("description", "").strip() or "Details coming soon."))
    db().commit()
    flash("Event published.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/delete/<int:event_id>", methods=["POST"])
@admin_required
def delete_event(event_id):
    db().execute("DELETE FROM registrations WHERE event_id=?", (event_id,))
    db().execute("DELETE FROM events WHERE id=?", (event_id,))
    db().commit()
    flash("Event deleted.", "ok")
    return redirect(url_for("admin"))


@app.route("/admin/export/<int:event_id>")
@admin_required
def export(event_id):
    rows = db().execute("SELECT ticket,name,roll,email FROM registrations WHERE event_id=?", (event_id,)).fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Ticket", "Name", "Roll", "Email"])
    w.writerows([tuple(r) for r in rows])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=event_{event_id}_registrations.csv"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)

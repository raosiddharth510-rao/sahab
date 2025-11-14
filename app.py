import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt, os

# -------------------------------------------------------------------
# LOCAL FALLBACK DB (if MongoDB not available)
# -------------------------------------------------------------------
class LocalDB:
    def __init__(self):
        self.users = [{"username": "admin", "password": bcrypt.hashpw("admin".encode(), bcrypt.gensalt()), "role": "admin"}]
        self.products = [
            {"_id": 1, "name": "Shirt", "price": 299},
            {"_id": 2, "name": "Shoes", "price": 999},
        ]
        self.orders = []

localdb = LocalDB()

@st.cache_resource
def get_db():
    uri = st.secrets.get("mongodb", {}).get("uri", None) or os.getenv("MONGODB_URI")

    if not uri:
        st.warning("⚠️ No MongoDB found — using Local In-Memory Database")
        return {"mode": "local", "users": localdb.users, "products": localdb.products, "orders": localdb.orders}

    client = MongoClient(uri)
    db = client.get_database("store_app")
    return {"mode": "mongo", "users": db.users, "products": db.products, "orders": db.orders}

db = get_db()
mode = db["mode"]
users_col = db["users"]
products_col = db["products"]
orders_col = db["orders"]

# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------
def hashpw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt())
def checkpw(p, h): return bcrypt.checkpw(p.encode(), h)

def get_user(username):
    if mode == "mongo": return users_col.find_one({"username": username})
    return next((u for u in users_col if u["username"] == username), None)

def create_user(username, password):
    if get_user(username): return False, "User exists!"
    u = {"username": username, "password": hashpw(password), "role": "user"}
    users_col.insert_one(u) if mode == "mongo" else users_col.append(u)
    return True, "User created ✔"

def list_products():
    return list(products_col.find()) if mode == "mongo" else products_col

def create_product(name, price):
    doc = {"name": name, "price": float(price)}
    products_col.insert_one(doc) if mode == "mongo" else products_col.append({"_id": len(products_col)+1, **doc})

def authenticate(username, password):
    u = get_user(username)
    if not u: return None
    if checkpw(password, u["password"]):
        u["_id"] = str(u.get("_id", username))
        return u
    return None

def place_order(uid, uname, items):
    total = sum(i["qty"] * i["price"] for i in items)
    order = {"user_id": uid, "username": uname, "items": items, "total": total}
    (orders_col.insert_one(order) if mode == "mongo" else orders_col.append(order))
    return order

# -------------------------------------------------------------------
# UI STATE
# -------------------------------------------------------------------
st.set_page_config(page_title="Mini Store", layout="wide")
if "page" not in st.session_state: st.session_state.page = "login"
if "user" not in st.session_state: st.session_state.user = None
if "cart" not in st.session_state: st.session_state.cart = []

def logout():
    st.session_state.page = "login"
    st.session_state.user = None
    st.session_state.cart = []

# -------------------------------------------------------------------
# HEADER
# -------------------------------------------------------------------
col1, col2, col3 = st.columns([1,4,2])
with col1: st.title("🛍️ Mini Store")
with col3:
    if st.session_state.user:
        st.write(f"Logged in as **{st.session_state.user['username']}**")
        if st.button("Logout"): logout()

# -------------------------------------------------------------------
# LOGIN PAGE
# -------------------------------------------------------------------
if st.session_state.page == "login":
    st.header("🔐 Login")
    tab1, tab2 = st.tabs(["Admin", "User"])

    # Admin
    with tab1:
        a = st.text_input("Admin Username")
        b = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin"):
            u = authenticate(a, b)
            if u and u.get("role") == "admin":
                st.session_state.user = u
                st.session_state.page = "admin"
                st.success("Admin Login ✔")
            else:
                st.error("Invalid Admin")

    # User
    with tab2:
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Login as User"):
            user = authenticate(u, p)
            if user:
                st.session_state.user = user
                st.session_state.page = "store"
                st.success("Login ✔")
            else:
                st.error("Invalid User Login")

# -------------------------------------------------------------------
# ADMIN PAGE
# -------------------------------------------------------------------
elif st.session_state.page == "admin":
    st.header("👨‍💼 Admin Dashboard")

    st.subheader("Create User")
    with st.form("f1"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Create"):
            ok, msg = create_user(u, p)
            st.success(msg) if ok else st.error(msg)

    st.subheader("Add Product")
    with st.form("f2"):
        n = st.text_input("Product Name")
        pr = st.number_input("Price", min_value=1.0)
        if st.form_submit_button("Add"):
            create_product(n, pr)
            st.success("Product Added ✔")

    st.subheader("Products")
    for p in list_products(): st.write(f"- {p['name']} — ₹{p['price']}")

    st.button("Back", on_click=logout)

# -------------------------------------------------------------------
# STORE PAGE
# -------------------------------------------------------------------
elif st.session_state.page == "store":
    st.header("🛒 Products")
    prods = list_products()

    cols = st.columns(3)
    for i, p in enumerate(prods):
        with cols[i % 3]:
            st.subheader(p["name"])
            st.write(f"₹{p['price']}")
            q = st.number_input(f"Qty {p['name']}", 1, key=f"qty{i}")
            if st.button(f"Add {p['name']}", key=f"b{i}"):
                st.session_state.cart.append({"name": p["name"], "price": p["price"], "qty": q})
                st.success("Added ✔")

    st.sidebar.header("🧺 Cart")
    if st.session_state.cart:
        total = sum(i["price"] * i["qty"] for i in st.session_state.cart)
        for i in st.session_state.cart:
            st.sidebar.write(f"{i['name']} × {i['qty']} = ₹{i['price']*i['qty']}")
        st.sidebar.write(f"**Total = ₹{total}**")
        if st.sidebar.button("Place Order"):
            o = place_order(st.session_state.user["_id"], st.session_state.user["username"], st.session_state.cart)
            st.session_state.cart = []
            st.success(f"Order Placed — ₹{o['total']}")
    else:
        st.sidebar.write("Empty Cart")

    st.button("Back", on_click=logout)

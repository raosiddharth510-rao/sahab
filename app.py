import streamlit as st
from pymongo import MongoClient
from bson.objectid import ObjectId
import bcrypt
import os

# ----------------------------------------------------
# MongoDB Connection Setup
# ----------------------------------------------------
@st.cache_resource
def get_db():
    # Prefer secrets.toml, fallback to environment variables
    mongodb_uri = None
    admin_user = None
    admin_password = None

    if "mongodb" in st.secrets:
        mongodb_uri = st.secrets["mongodb"].get("uri")
    else:
        mongodb_uri = os.environ.get("MONGODB_URI")

    if "admin" in st.secrets:
        admin_user = st.secrets["admin"].get("username")
        admin_password = st.secrets["admin"].get("password")
    else:
        admin_user = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASSWORD")

    if not mongodb_uri:
        st.error("❌ MongoDB URI not found. Please set it in Streamlit secrets or environment variable.")
        st.stop()

    client = MongoClient(mongodb_uri)
    db = client.get_database("streamlit_store")

    users = db.users
    products = db.products
    orders = db.orders

    # Create admin user if not exists
    if admin_user and admin_password:
        if users.find_one({"username": admin_user, "role": "admin"}) is None:
            hashed_pw = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt())
            users.insert_one({
                "username": admin_user,
                "password": hashed_pw,
                "role": "admin"
            })

    return {"db": db, "users": users, "products": products, "orders": orders}


# ----------------------------------------------------
# Initialize database and collections
# ----------------------------------------------------
dbs = get_db()
users_col = dbs["users"]
products_col = dbs["products"]
orders_col = dbs["orders"]

# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password: str, hashed: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed)
    except Exception:
        return False

def create_user(username: str, password: str, role: str = "user"):
    if users_col.find_one({"username": username}):
        return False, "User already exists!"
    hashed = hash_password(password)
    users_col.insert_one({"username": username, "password": hashed, "role": role})
    return True, "✅ User created successfully!"

def create_product(name: str, price: float):
    products_col.insert_one({"name": name, "price": float(price)})
    return True

def list_products():
    return list(products_col.find())

def authenticate(username: str, password: str):
    user = users_col.find_one({"username": username})
    if not user:
        return None
    if check_password(password, user["password"]):
        return {"_id": str(user["_id"]), "username": user["username"], "role": user.get("role", "user")}
    return None

def place_order(user_id, username, cart_items):
    total = sum(item["price"] * item.get("qty", 1) for item in cart_items)
    order = {
        "user_id": ObjectId(user_id),
        "username": username,
        "items": cart_items,
        "total": total,
        "status": "placed"
    }
    orders_col.insert_one(order)
    return order

# ----------------------------------------------------
# Streamlit App UI
# ----------------------------------------------------
st.set_page_config(page_title="Mini Store", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "login"
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []

def logout():
    st.session_state.user = None
    st.session_state.cart = []
    st.session_state.page = "login"

# ----------------------------------------------------
# Header / Top Bar
# ----------------------------------------------------
col1, col2, col3 = st.columns([1, 4, 2])
with col1:
    st.title("🛍️ Mini Store")
with col3:
    if st.session_state.user:
        st.markdown(f"**Logged in as:** {st.session_state.user['username']}")
        if st.button("Logout"):
            logout()

# ----------------------------------------------------
# LOGIN PAGE
# ----------------------------------------------------
if st.session_state.page == "login":
    st.header("🔐 Login")
    tab1, tab2 = st.tabs(["Admin Login", "User Login"])

    with tab1:
        st.subheader("Admin Login")
        admin_username = st.text_input("Admin Username")
        admin_password = st.text_input("Admin Password", type="password")
        if st.button("Login as Admin"):
            user = authenticate(admin_username, admin_password)
            if user and user["role"] == "admin":
                st.session_state.user = user
                st.session_state.page = "admin"
                st.success("✅ Admin login successful!")
            else:
                st.error("Invalid admin credentials.")

    with tab2:
        st.subheader("User Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login as User"):
            user = authenticate(username, password)
            if user and user["role"] == "user":
                st.session_state.user = user
                st.session_state.page = "store"
                st.success("✅ Login successful!")
            else:
                st.error("Invalid user credentials.")

# ----------------------------------------------------
# ADMIN PAGE
# ----------------------------------------------------
elif st.session_state.page == "admin":
    st.header("👨‍💼 Admin Dashboard")

    # Create new user
    st.subheader("Create a new user")
    with st.form("create_user_form"):
        new_user = st.text_input("Username")
        new_pass = st.text_input("Password", type="password")
        submitted_user = st.form_submit_button("Create User")
        if submitted_user:
            ok, msg = create_user(new_user, new_pass)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    # Create product
    st.subheader("Add Product")
    with st.form("create_product_form"):
        pname = st.text_input("Product Name")
        pprice = st.number_input("Price (₹)", min_value=0.0, format="%.2f")
        submitted_p = st.form_submit_button("Add Product")
        if submitted_p:
            if pname:
                create_product(pname, pprice)
                st.success(f"✅ Product '{pname}' added successfully!")
            else:
                st.error("Please enter a product name.")

    # List products
    st.subheader("🧾 Product List")
    prods = list_products()
    if prods:
        for p in prods:
            st.write(f"- **{p['name']}** — ₹{p['price']}")
    else:
        st.info("No products added yet.")

    if st.button("🔙 Back to Login"):
        logout()

# ----------------------------------------------------
# STORE PAGE (User View)
# ----------------------------------------------------
elif st.session_state.page == "store":
    st.header("🛒 Products Available")
    prods = list_products()

    if prods:
        cols = st.columns(3)
        for i, p in enumerate(prods):
            col = cols[i % 3]
            with col:
                st.subheader(p["name"])
                st.write(f"Price: ₹{p['price']}")
                qty = st.number_input(f"Quantity for {p['name']}", min_value=1, value=1, key=f"qty_{i}")
                if st.button(f"Add {p['name']} to Cart", key=f"add_{i}"):
                    st.session_state.cart.append({
                        "product_id": str(p["_id"]),
                        "name": p["name"],
                        "price": float(p["price"]),
                        "qty": int(qty),
                    })
                    st.success(f"Added {p['name']} to cart!")
    else:
        st.warning("No products available yet!")

    # Cart sidebar
    st.sidebar.header("🧺 Your Cart")
    if st.session_state.cart:
        total = 0
        for item in st.session_state.cart:
            subtotal = item["price"] * item["qty"]
            total += subtotal
            st.sidebar.write(f"{item['name']} × {item['qty']} — ₹{subtotal:.2f}")
        st.sidebar.write(f"**Total: ₹{total:.2f}**")
        if st.sidebar.button("✅ Place Order"):
            user = st.session_state.user
            order = place_order(user["_id"], user["username"], st.session_state.cart)
            st.session_state.cart = []
            st.success(f"🎉 Order placed successfully! Total ₹{order['total']:.2f}")
            st.balloons()
    else:
        st.sidebar.write("Your cart is empty.")

    if st.button("🔙 Back to Login"):
        logout()

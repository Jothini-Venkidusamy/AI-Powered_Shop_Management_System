import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import uuid
import plotly.express as px

# Initialize SQLite database
conn = sqlite3.connect('shop.db', check_same_thread=False)
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT,
        price REAL,
        quantity INTEGER
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        product_id TEXT,
        quantity_sold INTEGER,
        sale_date TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )
''')
conn.commit()

# Function to add a new product
def add_product(name, price, quantity):
    product_id = str(uuid.uuid4())
    cursor.execute('INSERT INTO products (id, name, price, quantity) VALUES (?, ?, ?, ?)',
                   (product_id, name, price, quantity))
    conn.commit()
    st.success(f"Product '{name}' added successfully!")

# Function to get all products
def get_products():
    cursor.execute('SELECT * FROM products')
    df = pd.DataFrame(cursor.fetchall(), columns=['ID', 'Name', 'Price', 'Quantity'])
    df['Stock Status'] = df['Quantity'].apply(
        lambda x: 'Out of Stock' if x == 0 else 'Low Stock' if x < 5 else 'In Stock'
    )
    return df

# Function to record a sale
def record_sale(product_id, quantity_sold):
    sale_id = str(uuid.uuid4())
    sale_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('INSERT INTO sales (id, product_id, quantity_sold, sale_date) VALUES (?, ?, ?, ?)',
                   (sale_id, product_id, quantity_sold, sale_date))
    cursor.execute('UPDATE products SET quantity = quantity - ? WHERE id = ?', (quantity_sold, product_id))
    conn.commit()
    st.success("Sale recorded successfully!")

# Function to get sales data
def get_sales():
    cursor.execute('''
        SELECT s.id, p.name, s.quantity_sold, s.sale_date, p.price
        FROM sales s
        JOIN products p ON s.product_id = p.id
    ''')
    df = pd.DataFrame(cursor.fetchall(), columns=['Sale ID', 'Name', 'Quantity Sold', 'Sale Date', 'Price'])
    df['Revenue'] = df['Quantity Sold'] * df['Price']
    return df

# Function to get weekly sales
def get_weekly_sales():
    sales = get_sales()
    sales['Sale Date'] = pd.to_datetime(sales['Sale Date'])
    sales['Week'] = sales['Sale Date'].dt.isocalendar().week
    sales['Year'] = sales['Sale Date'].dt.year
    weekly = sales.groupby(['Year', 'Week']).agg({
        'Quantity Sold': 'sum',
        'Revenue': 'sum'
    }).reset_index()
    weekly['Week Start'] = sales.groupby(['Year', 'Week'])['Sale Date'].min().dt.strftime('%Y-%m-%d').values
    return weekly

# AI-driven insights
def get_insights():
    products = get_products()
    sales = get_sales()

    top_products = sales.groupby('Name')['Quantity Sold'].sum().sort_values(ascending=False).head(3)
    low_stock = products[products['Quantity'] < 5][['Name', 'Quantity', 'Stock Status']]
    weekly_sales = get_weekly_sales()

    if len(weekly_sales) >= 2:
        weekly_sales['Trend'] = weekly_sales['Quantity Sold'].diff().apply(
            lambda x: 'Increasing' if x > 0 else 'Decreasing' if x < 0 else 'Stable'
        )
    else:
        weekly_sales['Trend'] = 'Insufficient Data'

    total_revenue = sales['Revenue'].sum()
    revenue_contribution = sales.groupby('Name')['Revenue'].sum() / total_revenue * 100

    sales['Sale Date'] = pd.to_datetime(sales['Sale Date'])
    recent_sales = sales[sales['Sale Date'] >= datetime.now() - timedelta(days=30)]
    sales_velocity = recent_sales.groupby('Name')['Quantity Sold'].sum() / 30
    restock_recommendations = products.merge(sales_velocity, on='Name', how='left').fillna(0)
    restock_recommendations['Days to Depletion'] = restock_recommendations['Quantity'] / restock_recommendations['Quantity Sold']
    restock_recommendations['Restock Urgency'] = restock_recommendations['Days to Depletion'].apply(
        lambda x: 'Urgent' if x < 7 else 'Moderate' if x < 14 else 'Low'
    )
    return top_products, low_stock, weekly_sales, revenue_contribution, restock_recommendations

# Streamlit app layout
st.set_page_config(page_title="AI Shop Manager", layout="wide")
st.title("🛒 AI-Powered Shop Management System")
st.markdown("Manage your shop's products and track sales with AI-powered analytics.")

# Sidebar Navigation
page = st.sidebar.radio("Navigation", ["Add Product", "View Products", "Record Sale", "View Sales", "Weekly Sales", "Insights"])

# Add Product Page
if page == "Add Product":
    st.header("Add a New Product")
    with st.form("add_product_form"):
        name = st.text_input("Product Name")
        price = st.number_input("Price ($)", min_value=0.01)
        quantity = st.number_input("Quantity", min_value=0)
        if st.form_submit_button("Add Product"):
            if name and price > 0 and quantity >= 0:
                add_product(name, price, quantity)
            else:
                st.error("Please fill all fields correctly.")

# View Products Page
elif page == "View Products":
    st.header("Product Inventory")
    products = get_products()
    search = st.text_input("Search Product")
    if search:
        products = products[products['Name'].str.contains(search, case=False)]
    st.dataframe(products, use_container_width=True)
    if st.button("Export Inventory to CSV"):
        products.to_csv("inventory_export.csv", index=False)
        st.success("Inventory exported to inventory_export.csv")

# Record Sale Page
elif page == "Record Sale":
    st.header("Record a Sale")
    products = get_products()
    product_dict = {row['Name']: row['ID'] for _, row in products.iterrows()}
    with st.form("record_sale_form"):
        product_name = st.selectbox("Select Product", list(product_dict.keys()))
        quantity_sold = st.number_input("Quantity Sold", min_value=1)
        if st.form_submit_button("Record Sale"):
            product_id = product_dict[product_name]
            available_quantity = products[products['ID'] == product_id]['Quantity'].iloc[0]
            if quantity_sold <= available_quantity:
                record_sale(product_id, quantity_sold)
            else:
                st.error(f"Insufficient stock! Available: {available_quantity}")

# View Sales Page
elif page == "View Sales":
    st.header("Sales History")
    sales = get_sales()
    st.dataframe(sales, use_container_width=True)
    if st.button("Export Sales to CSV"):
        sales.to_csv("sales_export.csv", index=False)
        st.success("Sales exported to sales_export.csv")

# Weekly Sales Page
elif page == "Weekly Sales":
    st.header("Weekly Sales")
    weekly_sales = get_weekly_sales()
    st.dataframe(weekly_sales, use_container_width=True)
    if not weekly_sales.empty:
        fig = px.line(weekly_sales, x='Week Start', y='Quantity Sold', title='Weekly Sales Trend')
        st.plotly_chart(fig, use_container_width=True)

# Insights Page
elif page == "Insights":
    st.header("AI Insights")
    top_products, low_stock, weekly_sales, revenue_contribution, restock_recommendations = get_insights()

    st.subheader("Top-Selling Products")
    st.write(top_products)

    st.subheader("Low Stock Alerts")
    if not low_stock.empty:
        st.dataframe(low_stock, use_container_width=True)
    else:
        st.info("No products are currently low on stock.")

    st.subheader("Weekly Sales Trend")
    st.dataframe(weekly_sales[['Year', 'Week', 'Quantity Sold', 'Revenue', 'Trend']], use_container_width=True)

    st.subheader("Revenue Contribution by Product")
    st.write(revenue_contribution)
    fig = px.pie(values=revenue_contribution, names=revenue_contribution.index, title='Revenue Share')
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Restock Recommendations")
    st.dataframe(restock_recommendations[['Name', 'Quantity', 'Days to Depletion', 'Restock Urgency']], use_container_width=True)

# Close DB connection at the end of app run
conn.close()

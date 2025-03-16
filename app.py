# app.py
import streamlit as st
import pandas as pd
import time
from PIL import Image
from io import BytesIO
import requests
import matplotlib.pyplot as plt
import seaborn as sns
import uuid  # Importing uuid for unique key generation

# Import the scraper model
from model.scraper import ECommerceComparisonModel

# Configure Streamlit page
st.set_page_config(
    page_title="E-commerce Product Comparison",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'current_results' not in st.session_state:
    st.session_state.current_results = None
if 'selected_tab' not in st.session_state:
    st.session_state.selected_tab = "Search"
if 'search_filters' not in st.session_state:
    st.session_state.search_filters = {
        'size': [],
        'color': [],
        'occasion': [],
        'min_price': 0,
        'max_price': 50000,
        'min_rating': 0.0
    }
# Add a product_keys dictionary to track unique keys for each product
if 'product_keys' not in st.session_state:
    st.session_state.product_keys = {}

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Search Products", "Search History", "Trend Analysis", "Settings", "About"])

# Load image from URL
def load_image(image_url):
    try:
        response = requests.get(image_url, timeout=5)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except:
        return None
    return None

# Function to apply filters
def apply_filters(products, filters):
    filtered_products = []
    for product in products:
        if product['price'] < filters['min_price'] or product['price'] > filters['max_price']:
            continue
        if product['rating'] < filters['min_rating']:
            continue
        if filters['size'] and product.get('available_sizes'):
            if not any(size in product['available_sizes'] for size in filters['size']):
                continue
        if filters['color'] and product.get('color'):
            if product['color'] not in filters['color']:
                continue
        if filters['occasion'] and product.get('occasion'):
            if product['occasion'] not in filters['occasion']:
                continue
        filtered_products.append(product)
    return filtered_products

# Function to search products
def search_products(query, progress_bar=None, filters=None):
    model = ECommerceComparisonModel()
    
    if progress_bar:
        progress_bar.progress(0.1)
        progress_bar.text("Searching Amazon...")
        amazon_products = model.search_amazon(query)

        progress_bar.progress(0.4)
        progress_bar.text("Searching Snapdeal...")
        snapdeal_products = model.search_snapdeal(query)

        progress_bar.progress(0.9)
        progress_bar.text("Comparing results...")

        all_products = amazon_products + snapdeal_products
        results = model.process_and_compare_products(all_products, query)

        progress_bar.progress(1.0)
        progress_bar.text("Search complete!")
    else:
        results = model.search_and_compare(query)

    if filters and results.get('all_products'):
        results['all_products'] = apply_filters(results['all_products'], filters)
        results['top_results'] = results['all_products'][:5]

        best_by_source = {}
        for product in results['all_products']:
            source = product['source']
            if source not in best_by_source:
                best_by_source[source] = product

        results['best_by_source'] = list(best_by_source.values())

    if query not in [item['query'] for item in st.session_state.search_history]:
        st.session_state.search_history.append({
            'query': query,
            'timestamp': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            'results_count': len(results.get('all_products', []))
        })

    return results

# Generate a unique product ID for consistent key generation
def get_product_id(product):
    # Create a unique identifier based on product attributes
    product_identifier = f"{product['title']}_{product['source']}_{product['price']}"
    
    # If we've seen this product before, return its existing ID
    if product_identifier in st.session_state.product_keys:
        return st.session_state.product_keys[product_identifier]
    
    # Otherwise, generate a new UUID and store it
    new_id = str(uuid.uuid4())
    st.session_state.product_keys[product_identifier] = new_id
    return new_id

# Modified display_product_card function with context parameter
def display_product_card(product, index, context="main"):
    col1, col2 = st.columns([1, 2])
    with col1:
        if product.get('image'):
            img = load_image(product['image'])
            if img:
                st.image(img, width=200)
            else:
                st.image("https://via.placeholder.com/200x250?text=No+Image", width=200)

    with col2:
        st.subheader(product['title'])
        st.write(f"**Price:** ₹{product['price']:.2f}")
        st.write(f"**Rating:** {'⭐' * int(product['rating'])} ({product['rating']:.1f})")
        st.write(f"**Reviews:** {product['reviews']}")
        st.write(f"**Source:** {product['source']}")
        if 'score' in product:
            st.write(f"**Overall Score:** {product['score']}%")
        st.markdown(f"[View Product]({product['link']})")

# Search Products Page
if page == "Search Products":
    st.title("E-commerce Product Comparison")
    st.header("Search for Products")

    # Search form with filters
    with st.form(key='search_form'):
        search_query = st.text_input("Enter product to search (e.g., 'black cocktail dress'): ")

        with st.expander("Advanced Filters"):
            col1, col2 = st.columns(2)
            with col1:
                size_filter = st.multiselect("Size", ["XS", "S", "M", "L", "XL", "XXL"], st.session_state.search_filters['size'])
                color_filter = st.multiselect("Color", ["Black", "White", "Red", "Blue", "Green", "Yellow", "Pink", "Purple", "Brown", "Gray", "Orange"], st.session_state.search_filters['color'])
                occasion_filter = st.multiselect("Occasion", ["Casual", "Formal", "Party", "Wedding", "Beach", "Office"], st.session_state.search_filters['occasion'])

            with col2:
                min_price = st.number_input("Min Price (₹)", 0, 50000, st.session_state.search_filters['min_price'])
                max_price = st.number_input("Max Price (₹)", 0, 50000, st.session_state.search_filters['max_price'])
                min_rating = st.slider("Minimum Rating", 0.0, 5.0, float(st.session_state.search_filters['min_rating']), step=0.1)

        search_button = st.form_submit_button("Search Products")

    if search_button and search_query:
        st.session_state.search_filters = {
            'size': size_filter,
            'color': color_filter,
            'occasion': occasion_filter,
            'min_price': min_price,
            'max_price': max_price,
            'min_rating': min_rating
        }

        progress = st.progress(0)
        status_text = st.empty()

        with st.spinner(f"Searching for '{search_query}' across platforms..."):
            status_text.text("Starting search...")
            results = search_products(search_query, progress, st.session_state.search_filters)
            st.session_state.current_results = results
            time.sleep(0.5)

        progress.empty()
        status_text.empty()

        if results and 'top_results' in results and results['top_results']:
            st.success(f"Found {len(results['all_products'])} products matching '{search_query}'")

            st.header("Best Overall Match")
            best_product = results['top_results'][0]
            display_product_card(best_product, 0, "best")
            
            st.header("All Results")
            for i, product in enumerate(results['all_products']):
                with st.expander(product['title']):
                    display_product_card(product, i, "expanded")
        else:
            st.warning(f"No products found matching '{search_query}'. Try a different search term.")

# Search History Page
elif page == "Search History":
    st.title("Search History")
    
    if not st.session_state.search_history:
        st.info("No search history yet. Search for products to build history.")
    else:
        st.write(f"You have searched for {len(st.session_state.search_history)} products.")
        
        history_df = pd.DataFrame(st.session_state.search_history)
        st.dataframe(history_df)
        
        if st.button("Clear History"):
            st.session_state.search_history = []
            st.success("Search history cleared!")
            st.experimental_rerun()

# Trend Analysis Page
elif page == "Trend Analysis":
    st.title("Product Trend Analysis")
    
    st.info("This feature analyzes patterns and trends from your search data and product comparisons.")
    
    if not st.session_state.search_history:
        st.warning("Not enough search data to analyze trends. Search for more products first.")
    else:
        st.subheader("Search Activity Over Time")
        
        # Convert timestamps to datetime
        history_df = pd.DataFrame(st.session_state.search_history)
        history_df['timestamp'] = pd.to_datetime(history_df['timestamp'])
        
        # Group by date and count searches
        date_counts = history_df.groupby(history_df['timestamp'].dt.date).count()['query']
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(date_counts.index, date_counts.values, marker='o')
        ax.set_xlabel("Date")
        ax.set_ylabel("Number of Searches")
        ax.set_title("Search Activity Trend")
        st.pyplot(fig)
        
        # Display most searched terms
        st.subheader("Most Searched Terms")
        query_counts = history_df['query'].value_counts().head(5)
        st.bar_chart(query_counts)

# Settings Page
elif page == "Settings":
    st.title("Settings")
    
    st.subheader("Search Preferences")
    
    with st.form("settings_form"):
        st.write("Default Search Filters")
        
        col1, col2 = st.columns(2)
        with col1:
            default_min_price = st.number_input("Default Min Price (₹)", 0, 50000, st.session_state.search_filters['min_price'])
            default_max_price = st.number_input("Default Max Price (₹)", 0, 50000, st.session_state.search_filters['max_price'])
        
        with col2:
            default_min_rating = st.slider("Default Minimum Rating", 0.0, 5.0, float(st.session_state.search_filters['min_rating']), step=0.1)
        
        default_sources = st.multiselect("Default Sources", ["Amazon", "Snapdeal", "Flipkart"], ["Amazon", "Snapdeal"])
        
        save_settings = st.form_submit_button("Save Settings")
        
        if save_settings:
            st.session_state.search_filters = {
                'size': st.session_state.search_filters['size'],
                'color': st.session_state.search_filters['color'],
                'occasion': st.session_state.search_filters['occasion'],
                'min_price': default_min_price,
                'max_price': default_max_price,
                'min_rating': default_min_rating
            }
            st.success("Settings saved successfully!")
    
    st.subheader("App Appearance")
    theme = st.selectbox("Theme", ["Light", "Dark", "System Default"], 0)
    
    if st.button("Apply Theme"):
        st.success(f"{theme} theme applied!")

# About Page
elif page == "About":
    st.title("About E-commerce Product Comparison")
    
    st.write(""" 
    This application helps you find the best products across multiple e-commerce platforms,
    compare prices, features, and ratings to make informed shopping decisions.
    
    ### Features:
    - **Search across multiple e-commerce platforms**: Compare products from Amazon, Snapdeal, and more.
    - **Filter products**: Narrow down results by price, rating, size, color, and occasion.
    - **Track search history**: Analyze your past searches and trends.
    - **Visualize data**: See price distributions and search activity over time.
    """)
    
    st.subheader("How to Use")
    st.write(""" 
    1. **Search Products**: Enter a product name in the search bar and apply filters to refine results.
    2. **View Trends**: Analyze your search history and product trends.
    3. **Customize Settings**: Adjust default filters and app appearance.
    """)
    
    st.subheader("Developed By")
    st.write(""" 
    - **ALPHA-CODE**
    - **Contact**: harishreddy.workmail@gmail.com
    - **GitHub**: [Our GitHub Profile](https://github.com/itsAcchu)
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.write("© 2025 E-commerce Product Comparison Application")
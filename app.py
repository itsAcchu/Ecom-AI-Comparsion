import streamlit as st
import pandas as pd
import time
from PIL import Image
from io import BytesIO
import requests
import matplotlib.pyplot as plt
import seaborn as sns

# Import the scraper model
from model.scraper import ECommerceComparisonModel

st.set_page_config(
    page_title="E-commerce Product Comparison",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
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

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Search Products", "Compare View", "Search History", "Trend Analysis", "Settings", "About"])

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
        progress_bar.text("Searching Flipkart...")
        flipkart_products = model.search_flipkart(query)

        progress_bar.progress(0.7)
        progress_bar.text("Searching Myntra...")
        myntra_products = model.search_myntra(query)

        progress_bar.progress(0.9)
        progress_bar.text("Comparing results...")

        all_products = amazon_products + flipkart_products + myntra_products
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

            col1, col2 = st.columns([1, 2])
            with col1:
                if best_product.get('image'):
                    img = load_image(best_product['image'])
                    if img:
                        st.image(img, width=200)
                    else:
                        st.image("https://via.placeholder.com/200x250?text=No+Image", width=200)

            with col2:
                st.subheader(best_product['title'])
                st.write(f"**Price:** ₹{best_product['price']:.2f}")
                st.write(f"**Rating:** {'⭐' * int(best_product['rating'])} ({best_product['rating']:.1f})")
                st.write(f"**Reviews:** {best_product['reviews']}")
                st.write(f"**Source:** {best_product['source']}")
                st.write(f"**Overall Score:** {best_product['score']}%")
                st.markdown(f"[View Product]({best_product['link']})")

        else:
            st.warning(f"No products found matching '{search_query}'. Try a different search term.")


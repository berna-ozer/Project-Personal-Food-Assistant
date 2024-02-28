import streamlit as st
from streamlit.components.v1 import html #For confetti
from PIL import Image
import requests
from io import BytesIO
import pandas as pd 

import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

import os
from os.path import join
import numpy as np

def get_api_key(file_path="gmaps_secrets.txt"):
    try:
        with open(file_path, "r") as file:
            api_key = file.read().strip()
        return api_key
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return None

api_key_param = {'apiKey': get_api_key("spoonacular_secrets.txt")}

map_api_key = get_api_key()

random_url = "https://api.spoonacular.com/recipes/random"

st.session_state.tagParams = []

def get_recipes():
    tags = ', '.join([st.session_state.meal_choice, st.session_state.diet_keyword])
    print('tags', tags)
    params = {
        'tags': tags,
        'number':3
    }
    params.update(api_key_param)
    response = requests.get(random_url, params=params)
    recipes = response.json()['recipes']
    return recipes

def showRecipes(recipes):
    image_url1 = recipes[0]['image']
    image_url2 = recipes[1]['image']
    image_url3 = recipes[2]['image']
    def textFor(id):
        return "Recipe: " + str(id + 1) + '\n' + recipes[id]['title'] + '\n' + 'Health Score: ' + str(recipes[id]['healthScore']) + '\n' + 'Preparation time: ' + str(recipes[id]['readyInMinutes']) + ' minutes'  

    text1 = textFor(0).replace('\n', '<br>')
    text2 = textFor(1).replace('\n', '<br>')
    text3 = textFor(2).replace('\n', '<br>')

    html_table = f"""
        <table>
        <tr>
            <td><img src="{image_url1}" alt="Image 1" style="width:300px;height:200px;"></td>
            <td><img src="{image_url2}" alt="Image 2" style="width:300px;height:200px;"></td>
            <td><img src="{image_url3}" alt="Image 2" style="width:300px;height:200px;"></td>
        </tr>
        <tr>
            <td>{text1}</td>
            <td>{text2}</td>
            <td>{text3}</td>
        </tr>
        </table>
        """
    # Display HTML table in Streamlit
    st.markdown(html_table, unsafe_allow_html=True)

def ingredient_data(recipe):
    ingredients = []
    amounts = []

    for ingredient in recipe['extendedIngredients']:
        ingredients.append(ingredient['name'])
        if ingredient['unit'] != None:
            amounts.append(f"{round(ingredient['amount'], 1):.1f} {ingredient['unit']}")
        else:
            amounts.append(f"{round(ingredient['amount'], 1):.1f}")
        

    data = [{'Ingredient': ingredient, 'Amount': amount} for ingredient, amount in zip(ingredients, amounts)]
    df = pd.DataFrame(data)
    df = df.reset_index(drop=True)
    return df

def map_price_level(price_level):
    if price_level == "N/A":
        return "Not available"
    elif price_level == 0:
        return "Free"
    elif price_level == 1:
        return "Inexpensive ($)"
    elif price_level == 2:
        return "Moderate ($$)"
    elif price_level == 3:
        return "Expensive ($$$)"
    elif price_level == 4:
        return "Very Expensive ($$$$)"
    else:
        return "Unknown"
    
def get_coordinates(api_key, address):
    # Google Maps API
    geocoding_api_url = "https://maps.googleapis.com/maps/api/geocode/json"

    # Parameters for the API
    params = {
        "key": api_key,
        "address": address,
    }

    # API request
    response = requests.get(geocoding_api_url, params=params)
    data = response.json()

    # API response
    if data["status"] == "OK" and data.get("results"):
        location = data["results"][0]["geometry"]["location"]
        return location["lat"], location["lng"]
    else:
        print("Error: Unable to retrieve coordinates for the provided address.")
        return None
    
def get_restaurants(api_key, diet_keyword, address, radius=5000): # No further than 5km
    # Get coordinates
    location = get_coordinates(api_key, address)

    if location is not None:
        # Define the Google Maps Places API endpoint
        places_api_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

        # parameters for the API
        params = {
            "key": api_key,
            "location": f"{location[0]},{location[1]}",  # Latitude and longitude from geocoding
            "radius": radius,
            "keyword": diet_keyword,
            "type": "restaurant",
        }

        # API request
        response = requests.get(places_api_url, params=params)
        data = response.json()

        # Process the API response
        restaurants = []
        for details_data in data.get("results", []):
            restaurant = {
                "name": details_data["name"],
                "price_level": details_data.get("price_level", "N/A"),
                "user_ratings_total": details_data.get("user_ratings_total", 0),
                "rating": details_data.get("rating", 0.0),
            }
            restaurants.append(restaurant)

        return restaurants

def show_restaurants(restaurants, address, search_text):
    if restaurants :
        st.text(f"\nTop {len(restaurants[:5])} restaurants near {address} for {search_text} \n")
        for i, restaurant in enumerate(restaurants[:5]):
            st.text(f"Restaurant {i + 1}: {restaurant['name']}")
            st.text(f"Price Level: {map_price_level(restaurant['price_level'])}")
            st.text(f"Average Rating: {restaurant['rating']} ({restaurant['user_ratings_total']} reviews)")
            st.divider()
    else:
        st.text(f"No restaurants found for {search_text}")

def search_market(ingredients):
    ingredient_dataframes = {}
    
    # Open Aldi web
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get('https://groceries.aldi.co.uk/en-GB/groceries')
    
    def search_and_scrape(ingredient):
        search_icon = driver.find_element(By.XPATH, '//*[@id="search-input"]')

        # Use JavaScript to clear the input field
        driver.execute_script("arguments[0].value = '';", search_icon)

        # Type the new ingredient and press Enter
        search_icon.send_keys(ingredient)
        search_icon.send_keys(Keys.ENTER)
        time.sleep(3)  # Wait for the search results to load
        


        ingredient_names = []
        ingredient_prices = []

        # Find all elements with product names and prices
        products = driver.find_elements(By.XPATH, '//*[@data-qa="search-product-title"]')

        for product in products:
            ingredient_names.append(product.get_attribute('title'))

        # Find all prices
        prices = driver.find_elements(By.XPATH, '//span[@class="h4"]')
        for price in prices:
            ingredient_prices.append(price.text)

        # Find the first product name and price
        first_product_name = ingredient_names[0] if ingredient_names else None
        first_product_price = ingredient_prices[0] if ingredient_prices else None

        # Create a DataFrame with the first product
        df = pd.DataFrame({
            'Name': [first_product_name],
            'Price': [first_product_price]
        })

        # Print the DataFrame
        print(df)

        return df

    def find_cheapest_and_total(dataframes):
        cheapest_ingredients = []
        total_price = 0

        for df in dataframes:
            # Replace '£' with an empty string
            df['Price'] = df['Price'].replace('[^\d.]', '', regex=True)

            # Replace empty strings with NaN
            df['Price'] = df['Price'].replace('', np.nan)

            # Convert price to numeric
            df['Price'] = pd.to_numeric(df['Price'], errors='coerce')

            # Drop NaN values for Price
            df = df.dropna(subset=['Price'])

            df['Price'] = round(df['Price'], 2)

            # Find the first ingredient for each dataframe
            first_row = df.iloc[0] if not df.empty else None
            cheapest_ingredients.append(first_row)

            # Add the price of the first ingredient to the total
            total_price += first_row['Price'] if first_row is not None else 0

        # DataFrame with the first ingredients
        cheapest_df = pd.DataFrame(cheapest_ingredients)

        # Add the total price
        total_price = round(total_price, 2)

        # Create a DataFrame with the total price
        total_row = {'Price': total_price}

        return cheapest_df, total_row

    # Loop through each ingredient
    for ingredient in ingredients:
        df = search_and_scrape(ingredient)
        ingredient_dataframes[ingredient] = df
        time.sleep(5)  # Add a delay between searches

    # Combine dataframes of ingredient searches into a list
    dataframes = list(ingredient_dataframes.values())

    # Find the cheapest ingredients and total price
    result_df = find_cheapest_and_total(dataframes)

    # Close the browser after all searches are done
    driver.quit()

    return result_df



def main():
    st.title('Yummy Food')

    # Initialize session_state
    if 'selected_page' not in st.session_state:
        st.session_state.selected_page = "Welcome"

    def update_page(page):
        st.session_state.selected_page = page

    def welcome_page():
        st.header("Your Personal Food Assistant 🍽️")
        st.text(
            """
            🤖 Hello! Greetings and welcome to the Recipe Advisor Assistant, Yummy! 
            Before we start, I have some questions about your preferences. 
            """
        )
        st.button('Begin', on_click=lambda: update_page('Meal'))

    def meal_selection_page():
        st.header("Meal Preference 🎯")

        meal_options = ['Main course', 'Side dish', 'Dessert']
        meal_choice = st.radio('What is your meal type preference?', meal_options)
        st.session_state.meal_choice = meal_choice.lower()


        st.button('Next', on_click=lambda: update_page("Diet"))

    def diet_selection_page():
        st.header("Diet Preference 🍽️")

        diet_options = ['Gluten Free', 'Ketogenic', 'Vegetarian', 'Vegan']
        diet_choice = st.radio('What is your diet type preference?', diet_options)
        st.session_state.diet_keyword = diet_choice

        st.button('Next', on_click=lambda: recipe_flow())

    def recipe_flow():
        st.session_state.recipes = get_recipes()
        update_page('Recipes')

    def recipe_selection_page():
        st.header("Recipes")
        showRecipes(st.session_state.recipes)
        st.session_state.recipe_choice = st.radio('What is your recipe preference?', [1, 2, 3]) - 1
        st.button('Ingredients', on_click=lambda: update_page('Ingredients'))
    
    def ingredients_page():
        recipes = st.session_state.recipes
        recipe_choice = st.session_state.recipe_choice
        st.header("Ingredients")
        st.text(f"Great! you've chosen {recipes[recipe_choice]['title']}")

        st.text("Let's prepare the ingredients before cooking!")

        data = ingredient_data(recipes[recipe_choice])

        st.session_state.ingredients = data['Ingredient'].to_list()

        st.table(data)

        col1, col2 = st.columns(2)

        if col1.button('Ingredient Prices', on_click=lambda: update_page('Ingredient Prices')):
            pass
        if col2.button('Instructions', on_click=lambda: update_page('Instructions')):
            pass

    def ingredient_price_page():
        st.header("Ingredient shopping cart")

        df, total = search_market(st.session_state.ingredients)

        st.table(df)

        st.text('Total Cart Price')
        st.table(total)

        # GON Display Aldi logo
        image_url = "https://corporate.aldi.us/fileadmin/fm-dam/logos/ALDI_2017.png"
        image = Image.open(requests.get(image_url, stream=True).raw)

        # Calculate the new dimensions for resizing (adjust the factors as needed)
        new_width = int(image.width / 3)
        new_height = int(image.height / 4)

        resized_image = image.resize((new_width, new_height))

        st.image(resized_image, caption='Aldi Logo', use_column_width=True)
        
        st.button('Instructions', on_click=lambda: update_page('Instructions'))
    
    def instructions_page():
        st.header("Instructions 📄")
        st.subheader("Preparation steps:")

        recipe = st.session_state.recipes[st.session_state.recipe_choice]

        if len(recipe['analyzedInstructions']) > 0:
            for step in recipe['analyzedInstructions'][0]['steps']:
                st.text(f"Step {str(step['number'])}:")
                st.markdown(step['step'])
                st.divider()
        else:
            st.markdown(recipe['instructions'])

        st.button('Restaurants', on_click=lambda: update_page('Restaurant Search'))
    
    def restaurant_search_page():
        st.header("Restaurant Search 🛎️")

        st.session_state.address = st.text_input('Your Address 📍')
        st.button('Search', on_click=lambda: update_page('Restaurant Result'))

    def restaurant_result_page():
        recipe = st.session_state.recipes[st.session_state.recipe_choice]
        st.header("Restaurant Results")
        st.subheader(f"For {recipe['title']}")

        restaurants = get_restaurants(map_api_key, recipe['title'], st.session_state.address)

        show_restaurants(restaurants, st.session_state.address, f"{recipe['title']} recipe")

        st.button('Search For Diet Type', on_click=lambda: update_page('Restaurant Result Diet'))
    
    def restaurant_result_diet_page():
        recipe = st.session_state.recipes[st.session_state.recipe_choice]
        st.header("Restaurant Results")
        st.subheader(f"For {st.session_state.diet_keyword} diet")

        restaurants = get_restaurants(map_api_key, st.session_state.diet_keyword, st.session_state.address)

        show_restaurants(restaurants, st.session_state.address, f"{st.session_state.diet_keyword} diet")

        st.subheader('Enjoy Your Meal 😃')

        st.markdown('<div style="text-align:center;"><img src="https://media.giphy.com/media/1wmtmO7JsAPytaogcL/giphy.gif" alt="confetti" width="300"/></div>', unsafe_allow_html=True)

    if st.session_state.selected_page == "Welcome":
        welcome_page()
    elif st.session_state.selected_page == "Meal":
        meal_selection_page()
    elif st.session_state.selected_page == "Diet":
        diet_selection_page()
    elif st.session_state.selected_page == "Recipes":
        recipe_selection_page()
    elif st.session_state.selected_page == 'Ingredients':
        ingredients_page()
    elif st.session_state.selected_page == 'Instructions':
        instructions_page()
    elif st.session_state.selected_page == 'Restaurant Search':
        restaurant_search_page()
    elif st.session_state.selected_page == 'Restaurant Result':
        restaurant_result_page()
    elif st.session_state.selected_page == 'Restaurant Result Diet':
        restaurant_result_diet_page()
    elif st.session_state.selected_page == 'Ingredient Prices':
        ingredient_price_page()




    
if __name__ == '__main__':
    main()

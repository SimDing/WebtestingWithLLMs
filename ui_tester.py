import click
import os.path
import time
import openai
from pathlib import Path
import urllib.parse
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
from bs4 import BeautifulSoup


def filter_html(html_string):
    soup = BeautifulSoup(html_string, "html.parser")

    # Remove all script and style elements
    for script in soup(["script", "style"]):
        script.decompose()

    # Remove the div with id 'coverage'
    coverage_div = soup.find(id="coverage")
    if coverage_div:
        coverage_div.decompose()

    # Convert HTML object back to a string without additional newlines
    text = str(soup)

    return text


@click.command()
@click.option(
    "--url",
    default="https://sea-lion-app-q6nwz.ondigitalocean.app/sample1",
    help="The URL of the web application to test.",
)
@click.option(
    "--delay",
    default=0.5,
    help="The time delay (in seconds) between actions on the web application.",
)
@click.option(
    "--interactions",
    default=100,
    help="The number of interactions to perform on the web application.",
)
@click.option(
    "--load-wait-time",
    default=10,
    help="The maximum time to wait (in seconds) for the page to load.",
)
@click.option(
    "--test-type",
    type=click.Choice(["monkey", "gpt4"], case_sensitive=False),
    default="monkey",
    help="The type of testing to perform.",
)
def main(url, delay, interactions, load_wait_time, test_type):
    # Check if the given URL is a local file path
    if os.path.isfile(url):
        # If it is a local file, convert the file path to a proper URL
        url = Path(url).as_uri()
    elif not urllib.parse.urlsplit(url).scheme:
        # If it's a relative file path, convert it to an absolute path first, then to a proper URL
        url = Path(os.path.abspath(url)).as_uri()

    print(f"Starting the test on URL: {url}")

    # OpenAI key loading would be required here
    with open("openai_key.json", "r") as file:
        openai.api_key = json.load(file)["key"]

    # Open the web browser and navigate to the app's URL
    browser = webdriver.Chrome()
    browser.get(url)

    # Wait for the elements to load
    WebDriverWait(browser, load_wait_time).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    print("Web page loaded successfully.")

    # Get the filtered HTML source code of the page
    filtered_html = filter_html(browser.page_source)

    # Find all buttons
    buttons = browser.find_elements(By.XPATH, "//button")

    print(f"Found {len(buttons)} clickable elements (buttons).")

    # Start testing
    for i in range(interactions):
        element = None  # We declare element variable here
        if test_type == "monkey":
            # Choose a random button
            element = random.choice(buttons)
        else:
            past_actions = []
            clickable_elements_data = []
            for i, button in enumerate(buttons):
                button_outerHTML = button.get_attribute("outerHTML")
                clickable_elements_data.append(
                    {"index": i, "outerHTML": button_outerHTML, "tag": "button"}
                )

            # Create the prompt for the GPT model with task description
            prompt = (
                f"Your task is to test a web application using Python and Selenium. "
                f"Here is the filtered HTML source code of the page: '{filtered_html}'. "
                f"Here are the available buttons: {clickable_elements_data}. "
                f"Here are the past actions: {past_actions}. "
                f"Please select the index of the action to perform by enclosing it in brackets like this: [3]."
            )

            # Ask the GPT model for the next action
            response = openai.ChatCompletion.create(
                model="gpt-4", messages=[{"role": "user", "content": prompt}]
            )

            action_string = response["choices"][0]["message"]["content"]
            match = re.search(r"\[(\d+)\]", action_string)

            if match:
                action_index = int(match.group(1))
                print(
                    f"Action {i+1}: Received action index from GPT-4: '{action_index}'."
                )
                element = buttons[action_index]
                past_actions.append(element.get_attribute("outerHTML"))
            else:
                print(
                    f"Did not find a valid action index in the response from GPT-4: {action_string}"
                )
                # handle the missing action index, for example, skip this interaction
                continue

        print(
            f"Action {i+1}: Clicking button with outerHTML: '{element.get_attribute('outerHTML')}'."
        )
        element.click()

        # Check for alert and accept it if present
        try:
            alert = browser.switch_to.alert
            print(f"Alert found with message: {alert.text}. Accepting it.")
            alert.accept()
        except Exception as e:
            pass  # no alert, so pass

        time.sleep(delay)  # Wait a bit between actions for the page to update

    # Close the driver
    print("Closing the browser.")
    browser.quit()


if __name__ == "__main__":
    main()

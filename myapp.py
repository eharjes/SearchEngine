from flask import Flask, request, render_template
from Levenshtein import distance
from english_dictionary.scripts.read_pickle import get_dict
from searchengine import SearchEngine  # Assuming your search engine code is in search_engine.py

app = Flask(__name__)
search_engine = SearchEngine('https://vm009.rz.uos.de/crawl/index.html', 4000)
search_engine.build_index()

history = []
english_dict = get_dict()

def get_recommendation(query):
    """Returns closest (Levenshtein distance) word to the given word

    query (string)          = word to get recommendation for

    current_rec (string)    = recommended word (can match the given word)
    """
    # initialize recommendation as empty string
    recommendation = ""
    # initialize best distance as very high so the first word checked always becomes the first recommendation
    best_dist = 99999999
    # look through all words in the english dictionary and track which word has the currently lowest distance to the query
    for word in english_dict:
        current_dist = distance(query, word)
        # if the current distance is smaller than the previously best distance update the recommendation and the best distance
        if current_dist < best_dist:
            best_dist = current_dist
            recommendation = word
    return recommendation

@app.route('/')
def home():

    return render_template('home_page_template2.html', history = history)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query not in history:
        history.append(query)
    if len(history) > 10:
        history.pop(0)
    recommendation = get_recommendation(query)
    if query:
        urls = search_engine.search(query.split())
        return render_template('search_results_template.html', urls=urls, query=query, recommendation = recommendation)
    else:
        return '<p>Please enter a search term.</p>', 400



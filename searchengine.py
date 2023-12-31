from crawler import Crawler
import os
from whoosh.index import create_in, open_dir, exists_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser, AndGroup
from bs4 import BeautifulSoup
import re
from typing import List, Tuple, Optional



class SearchEngine:
    def __init__(self, start_url: str, max_pages: int, index_dir: str = 'indexdir', create_index: bool = False) -> None:
        self.crawler = Crawler(start_url, max_pages)
        self.max_pages = max_pages
        self.index_dir = index_dir
        # Define the schema for indexing
        self.schema = Schema(
            url=ID(stored=True, unique=True),
            content=TEXT(stored=True),
            title=TEXT(stored=True)

        )
        # Create or open the index directory
        if create_index:
            os.makedirs(self.index_dir)
            self.ix = create_in(self.index_dir, self.schema)
        else:
            self.ix = open_dir(self.index_dir)

    def build_index(self) -> None:
        """
        Builds an index for web pages by crawling and then indexing their content
        initializes an index writer, starts or continues web crawling, retrieves web page content, and adds the content to the index

        :param: none specified, the intern parameters will be used
        :return:initializes an index writer, starts or continues web crawling, retrieves web page content, and adds the content to the index
        """
        # build index only if it does not exist yet
        if not self.is_index_built():
            writer = self.ix.writer()
            self.crawler.crawl()
            # extract all information for the index from the url
            for url in self.crawler.visited:
                content = self.crawler.get_content(url)
                soup = BeautifulSoup(content, 'html.parser')
                content = self.clean_text(content)
                # Extract the title and convert to a plain string
                # add str() to avoid max depth recursion error
                title = soup.title.string if soup.title else 'No Title'
                title = str(title).strip()
                # and add information to the index directory
                if content is not None:                                   
                    writer.add_document(url=url, content=content, title = title)
            writer.commit()
    
    def is_index_built(self) -> bool:
        """
        Checks if the index directory exists and if there are documents in it

        :param: none specified, the intern parameters will be used
        :return:
        """
        if exists_in(self.index_dir):
            ix = open_dir(self.index_dir)
            with ix.searcher() as searcher:
                return searcher.doc_count() > 0
        return False
    
    def search(self, words: List[str]) -> List[Tuple[int, str, str, str]]:
        """
        Searches the indexed web pages for the specified words and returns a list of pages where these words occur.

        This method performs a search using the provided list of words. It searches for pages where all these words occur, 
        counts the number of occurrences of these words on each page, and retrieves the context around these occurrences. 
        It then returns a sorted list of tuples, each containing the count of word occurrences, the context snippet, 
        the URL, and the title of the page.

        The results are sorted in descending order based on the number of word occurrences.

        :param words: A list of words to search for in the indexed content.
        :return: A list of tuples, each tuple containing the count of word occurrences, a context snippet, 
                the URL, and the title of the page where the words were found. The list is sorted by the count of 
                word occurrences in descending order.
        """
        # Open the existing index directory
        ix = open_dir(self.index_dir)

        # Use Whoosh's searcher
        with ix.searcher() as searcher:
            # Using the AndGroup to require all words in the query
            parser = QueryParser("content", ix.schema, group=AndGroup)
            # Create a query string that includes all words
            query_str = ' AND '.join(words)
            # Parse the query string
            query = parser.parse(query_str)

            # Perform the search
            results = searcher.search(query,limit=self.max_pages)

            # Collect the URLs and titles from the results
            urls = [result['url'] for result in results]
            titles = [result['title'] for result in results]
            # initialize context and word_occurences for displayed information on search results
            word_occurrences = [0] * len(urls)
            context = [0] * len(urls)

            # Iterate through the results and count word occurrences
            for indx, result in enumerate(results):

                # Convert content to lowercase and split into words
                soup = BeautifulSoup(result['content'], 'html.parser')
                text_content = soup.get_text(separator=' ', strip=True)
                content_for_context = re.findall(r"[\w']+|[.,!?;]", text_content)
                content = re.findall(r"[\w']+|[.,!?;]", text_content.lower())

                # count the word occurrences
                for spot, word in enumerate(content):
                    if word in words:
                        word_occurrences[indx] += 1
                        context[indx] = content_for_context[spot-4: spot+5]
                        context[indx] = (" ".join(context[indx])).replace(' .','.').replace(' ,',',')


            # zip information into one to search through
            context_urls_titles = zip(context, urls, titles)
            word_con_urls_tit = [0] * len(word_occurrences)

            # search through pages to find the pages with occurrences of the query
            for i, (context_word, url, title) in enumerate(context_urls_titles):

                # record pages on which the query was found with all information
                if word_occurrences[i] > 0:
                    word_con_urls_tit[i] = [word_occurrences[i], context_word, url, title]
            
            # filter out duplicates from found results and choose the shortest url for each duplicate
            compare_titles = [0] * len(word_con_urls_tit)
            compare_urls = [0] * len(word_con_urls_tit)

            for i, entry in enumerate(word_con_urls_tit):
                # ignore empty entries as they will be removed later anyway
                if entry != 0:
                    # build list filled with unique titles and urls
                    if entry[3] not in compare_titles:
                        compare_titles[i] = entry[3]
                        compare_urls[i] = entry[2]
                    # if a duplicate website is found
                    else:
                        # determine which entry in the results should be removed based on url length
                        for idx, title in enumerate(compare_titles):
                            # at the spot where the duplicate is located
                            if title == entry[3]:
                                # remove the entry with the longer url from the results
                                if len(entry[2]) < len(compare_urls[idx]):
                                    word_con_urls_tit[idx] = 0
                                else:
                                    word_con_urls_tit[i] = 0
            
            # Convert the dictionary to a list of tuples and sort by count in descending order
            word_con_urls_tit = [elem for elem in word_con_urls_tit if elem != 0]
            word_con_urls_tit = sorted(word_con_urls_tit, reverse = True)

        return word_con_urls_tit
    
    def clean_text(self, html_content: str) -> str:
        """
        Clean the HTML content and extract human-readable text.

        :param html_content: The HTML content to be cleaned.
        :return: Cleaned, human-readable text.
        """
        # Parse HTML content
        # only execute if there is any content at all
        if html_content is not None:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script_or_style in soup(['script', 'style']):
                script_or_style.decompose()

            # Get text and replace HTML entities
            html_content = soup.get_text()

            # Replace multiple spaces with a single space and strip leading/trailing whitespace
            html_content = re.sub(r'\s+', ' ', html_content).strip()

        return html_content
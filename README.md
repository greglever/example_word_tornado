Running the Word Tornado example app
====================================

Requirements: 
* `docker`
* `docker-compose`

If the requirements are installed on your machine then after cloning this
repo you can run the app with `docker-compose up`.

Then please open http://localhost:8888/ in your web browser.
You will see a form where you can enter a URL to any webpage and a word cloud of the 
most 100 common terms on that page will be displayed.

Then you can navigate to http://localhost:8888/admin to view a list all words entered into the DB, 
ordered by frequency of usage.
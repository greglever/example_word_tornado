import aiopg
import os.path
import psycopg2
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.locks
import tornado.options
import tornado.web


from bs4 import BeautifulSoup
from collections import Counter
import string

from tornado.httpclient import AsyncHTTPClient
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)
define("db_host", default="127.0.0.1", help="wordtornado database host")
define("db_port", default=5432, help="wordtornado database port")
define("db_database", default="wordtornado", help="wordtornado database name")
define("db_user", default="wordtornado", help="wordtornado database user")
define("db_password", default="wordtornado", help="wordtornado database password")


STOP_WORDS = [
    "function", "var", "a", "about", "above", "above", "across", "after", "afterwards", "again", "against", "all", "almost", "alone", "along", "already", "also","although","always","am","among", "amongst", "amoungst", "amount",  "an", "and", "another", "any","anyhow","anyone","anything","anyway", "anywhere", "are", "around", "as",  "at", "back","be","became", "because","become","becomes", "becoming", "been", "before", "beforehand", "behind", "being", "below", "beside", "besides", "between", "beyond", "bill", "both", "bottom","but", "by", "call", "can", "cannot", "cant", "co", "con", "could", "couldnt", "cry", "de", "describe", "detail", "do", "done", "down", "due", "during", "each", "eg", "eight", "either", "eleven","else", "elsewhere", "empty", "enough", "etc", "even", "ever", "every", "everyone", "everything", "everywhere", "except", "few", "fifteen", "fify", "fill", "find", "fire", "first", "five", "for", "former", "formerly", "forty", "found", "four", "from", "front", "full", "further", "get", "give", "go", "had", "has", "hasnt", "have", "he", "hence", "her", "here", "hereafter", "hereby", "herein", "hereupon", "hers", "herself", "him", "himself", "his", "how", "however", "hundred", "ie", "if", "in", "inc", "indeed", "interest", "into", "is", "it", "its", "itself", "keep", "last", "latter", "latterly", "least", "less", "ltd", "made", "many", "may", "me", "meanwhile", "might", "mill", "mine", "more", "moreover", "most", "mostly", "move", "much", "must", "my", "myself", "name", "namely", "neither", "never", "nevertheless", "next", "nine", "no", "nobody", "none", "noone", "nor", "not", "nothing", "now", "nowhere", "of", "off", "often", "on", "once", "one", "only", "onto", "or", "other", "others", "otherwise", "our", "ours", "ourselves", "out", "over", "own","part", "per", "perhaps", "please", "put", "rather", "re", "same", "see", "seem", "seemed", "seeming", "seems", "serious", "several", "she", "should", "show", "side", "since", "sincere", "six", "sixty", "so", "some", "somehow", "someone", "something", "sometime", "sometimes", "somewhere", "still", "such", "system", "take", "ten", "than", "that", "the", "their", "them", "themselves", "then", "thence", "there", "thereafter", "thereby", "therefore", "therein", "thereupon", "these", "they", "thickv", "thin", "third", "this", "those", "though", "three", "through", "throughout", "thru", "thus", "to", "together", "too", "top", "toward", "towards", "twelve", "twenty", "two", "un", "under", "until", "up", "upon", "us", "very", "via", "was", "we", "well", "were", "what", "whatever", "when", "whence", "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "whereupon", "wherever", "whether", "which", "while", "whither", "who", "whoever", "whole", "whom", "whose", "why", "will", "with", "within", "without", "would", "yet", "you", "your", "yours", "yourself", "yourselves", "the"
]


class NoResultError(Exception):
    pass


async def maybe_create_tables(db):
    try:
        with (await db.cursor()) as cur:
            await cur.execute("SELECT COUNT(*) FROM words LIMIT 1")
            await cur.fetchone()
    except psycopg2.ProgrammingError:
        with open('schema.sql') as f:
            schema = f.read()
        with (await db.cursor()) as cur:
            await cur.execute(schema)


class Application(tornado.web.Application):
    def __init__(self, db):
        self.db = db
        handlers = [
            (r"/", HomeHandler),
            (r"/admin", AdminHandler),
            # (r"/archive", ArchiveHandler),
            # (r"/feed", FeedHandler),
            # (r"/entry/([^/]+)", EntryHandler),
            # (r"/compose", ComposeHandler),
            # (r"/auth/create", AuthCreateHandler),
            # (r"/auth/login", AuthLoginHandler),
            # (r"/auth/logout", AuthLogoutHandler),
        ]
        # settings = dict(
        #     blog_title=u"Word Tornado",
            # template_path=os.path.join(os.path.dirname(__file__), "templates"),
            # static_path=os.path.join(os.path.dirname(__file__), "static"),
            # ui_modules={"Entry": EntryModule},
            # xsrf_cookies=True,
            # cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            # login_url="/auth/login",
            # debug=True,
        # )
        super(Application, self).__init__(handlers)  # , **settings)


class BaseHandler(tornado.web.RequestHandler):
    def row_to_obj(self, row, cur):
        """Convert a SQL row to an object supporting dict and attribute access."""
        obj = tornado.util.ObjectDict()
        for val, desc in zip(row, cur.description):
            obj[desc.name] = val
        return obj

    async def execute(self, stmt, *args):
        """Execute a SQL statement.

        Must be called with ``await self.execute(...)``
        """
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)

    async def query(self, stmt, *args):
        """Query for a list of results.

        Typical usage::

            results = await self.query(...)

        Or::

            for row in await self.query(...)
        """
        with (await self.application.db.cursor()) as cur:
            await cur.execute(stmt, args)
            return [self.row_to_obj(row, cur)
                    for row in await cur.fetchall()]

    # async def queryone(self, stmt, *args):
    #     """Query for exactly one result.
    #
    #     Raises NoResultError if there are no results, or ValueError if
    #     there are more than one.
    #     """
    #     results = await self.query(stmt, *args)
    #     if len(results) == 0:
    #         raise NoResultError()
    #     elif len(results) > 1:
    #         raise ValueError("Expected 1 result, got %d" % len(results))
    #     return results[0]

    # async def prepare(self):
    #     # get_current_user cannot be a coroutine, so set
    #     # self.current_user in prepare instead.
    #     user_id = self.get_secure_cookie("blogdemo_user")
    #     if user_id:
    #         self.current_user = await self.queryone("SELECT * FROM authors WHERE id = %s",
    #                                                 int(user_id))
    #
    # async def any_author_exists(self):
    #     return bool(await self.query("SELECT * FROM authors LIMIT 1"))


class HomeHandler(BaseHandler):

    async def get(self):
        self.write(
            '<html><body><form action="/" method="POST">'
            '<input type="text" name="message">'
            '<input type="submit" value="Submit">'
            '</form></body></html>'
        )

    async def post(self):
        http = AsyncHTTPClient()
        url = self.get_body_argument("message")
        response = await http.fetch(url)
        html = await self.generate_html_word_cloud(response=response)
        self.write(html)

    async def persist_words_into_db(self, words):
        """
        Iterate through the words nd frequencies
        Check if the word already exists in the db and UPDATE
        Otherwise INSERT
        :param words:
        :return: None, executes query
        """
        for word in words:
            count_result = await self.query("SELECT COUNT(*) FROM words WHERE word = %s", word[0])
            count = count_result[0]["count"]

            if count > 0:
                await self.execute(
                    "UPDATE words SET frequency = %s "
                    "WHERE word = %s", word[1], word[0])

            else:

                await self.execute(
                    "INSERT INTO words (word, frequency)"
                    "VALUES (%s,%s)",
                    word[0], word[1])

    async def generate_html_word_cloud(self, response):
        soup = BeautifulSoup(response.body, 'html.parser')
        whitespace_split_list = soup.body.get_text().split(" ")
        result_list = [e for e in whitespace_split_list if not any([p in e for p in string.punctuation])]
        result_list = [e for e in result_list if e != "" and e not in STOP_WORDS]
        most_common_words = Counter(result_list).most_common(100)
        await self.persist_words_into_db(words=most_common_words)

        html = """<!DOCTYPE html>
                <html>
                <head lang="en">
                <meta charset="UTF-8">
                <title>Tag Cloud Generator</title>
                </head>
                <body>
                <div style="text-align: center; vertical-align: middle; font-family:
                arial; color: red; background-color:blue; border:1px solid black">"""
        for w in most_common_words:
            html += """<span style="font-size: {size}px">""".format(size=5 * w[1]) + w[0] + """</span> """ + "\n"

        html += """</div>
            </body>
            </html>"""
        return html



class AdminHandler(BaseHandler):

    async def get(self):
        entries = await self.query("SELECT word, frequency FROM words ORDER BY frequency DESC")
        self.write({"words": [e['word'] for e in entries]})


# class EntryHandler(BaseHandler):
#     async def get(self, slug):
#         entry = await self.queryone("SELECT * FROM entries WHERE slug = %s", slug)
#         if not entry:
#             raise tornado.web.HTTPError(404)
#         self.render("entry.html", entry=entry)
#
#
# class ArchiveHandler(BaseHandler):
#     async def get(self):
#         entries = await self.query("SELECT * FROM entries ORDER BY published DESC")
#         self.render("archive.html", entries=entries)
#
#
# class FeedHandler(BaseHandler):
#     async def get(self):
#         entries = await self.query("SELECT * FROM entries ORDER BY published DESC LIMIT 10")
#         self.set_header("Content-Type", "application/atom+xml")
#         self.render("feed.xml", entries=entries)
#
#
# class ComposeHandler(BaseHandler):
#     @tornado.web.authenticated
#     async def get(self):
#         id = self.get_argument("id", None)
#         entry = None
#         if id:
#             entry = await self.queryone("SELECT * FROM entries WHERE id = %s", int(id))
#         self.render("compose.html", entry=entry)
#
#     @tornado.web.authenticated
#     async def post(self):
#         id = self.get_argument("id", None)
#         title = self.get_argument("title")
#         text = self.get_argument("markdown")
#         html = markdown.markdown(text)
#         if id:
#             try:
#                 entry = await self.queryone("SELECT * FROM entries WHERE id = %s", int(id))
#             except NoResultError:
#                 raise tornado.web.HTTPError(404)
#             slug = entry.slug
#             await self.execute(
#                 "UPDATE entries SET title = %s, markdown = %s, html = %s "
#                 "WHERE id = %s", title, text, html, int(id))
#         else:
#             slug = unicodedata.normalize("NFKD", title)
#             slug = re.sub(r"[^\w]+", " ", slug)
#             slug = "-".join(slug.lower().strip().split())
#             slug = slug.encode("ascii", "ignore").decode("ascii")
#             if not slug:
#                 slug = "entry"
#             while True:
#                 e = await self.query("SELECT * FROM entries WHERE slug = %s", slug)
#                 if not e:
#                     break
#                 slug += "-2"
#             await self.execute(
#                 "INSERT INTO entries (author_id,title,slug,markdown,html,published,updated)"
#                 "VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
#                 self.current_user.id, title, slug, text, html)
#         self.redirect("/entry/" + slug)
#
#
# class AuthCreateHandler(BaseHandler):
#     def get(self):
#         self.render("create_author.html")
#
#     async def post(self):
#         if await self.any_author_exists():
#             raise tornado.web.HTTPError(400, "author already created")
#         hashed_password = await tornado.ioloop.IOLoop.current().run_in_executor(
#             None, bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
#             bcrypt.gensalt())
#         author = await self.queryone(
#             "INSERT INTO authors (email, name, hashed_password) "
#             "VALUES (%s, %s, %s) RETURNING id",
#             self.get_argument("email"), self.get_argument("name"),
#             tornado.escape.to_unicode(hashed_password))
#         self.set_secure_cookie("blogdemo_user", str(author.id))
#         self.redirect(self.get_argument("next", "/"))
#
#
# class AuthLoginHandler(BaseHandler):
#     async def get(self):
#         # If there are no authors, redirect to the account creation page.
#         if not await self.any_author_exists():
#             self.redirect("/auth/create")
#         else:
#             self.render("login.html", error=None)
#
#     async def post(self):
#         try:
#             author = await self.queryone("SELECT * FROM authors WHERE email = %s",
#                                          self.get_argument("email"))
#         except NoResultError:
#             self.render("login.html", error="email not found")
#             return
#         hashed_password = await tornado.ioloop.IOLoop.current().run_in_executor(
#             None, bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
#             tornado.escape.utf8(author.hashed_password))
#         hashed_password = tornado.escape.to_unicode(hashed_password)
#         if hashed_password == author.hashed_password:
#             self.set_secure_cookie("blogdemo_user", str(author.id))
#             self.redirect(self.get_argument("next", "/"))
#         else:
#             self.render("login.html", error="incorrect password")
#
#
# class AuthLogoutHandler(BaseHandler):
#     def get(self):
#         self.clear_cookie("blogdemo_user")
#         self.redirect(self.get_argument("next", "/"))
#
#
# class EntryModule(tornado.web.UIModule):
#     def render(self, entry):
#         return self.render_string("modules/entry.html", entry=entry)


async def main():
    tornado.options.parse_command_line()

    # Create the global connection pool.
    async with aiopg.create_pool(
            host=options.db_host,
            port=options.db_port,
            user=options.db_user,
            password=options.db_password,
            dbname=options.db_database) as db:
        await maybe_create_tables(db)
        app = Application(db)
        app.listen(options.port)

        # In this demo the server will simply run until interrupted
        # with Ctrl-C, but if you want to shut down more gracefully,
        # call shutdown_event.set().
        shutdown_event = tornado.locks.Event()
        await shutdown_event.wait()


if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().run_sync(main)

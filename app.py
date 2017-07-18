#!/usr/bin/env python3

# The MIT License (MIT)

# Copyright (c) 2016 RascalTwo @ therealrascaltwo@gmail.com

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
import re
import json
import time
import praw
import random
import logging
import logging.handlers
import requests
import threading

class Thread():
    def __init__(self, function, name=None, args=None):
        self.function = function
        thread = threading.Thread(target=self.function, name=name, args=args)
        thread.daemon = True
        thread.start()


class WeDidItReddit(object):
    def __init__(self):
        self.processed = self._load_file("data/processed.json")
        self.messages = self._load_file("messages.json")
        self.config = self._load_file("config.json")

        if "comments" not in self.processed:
            self.processed["comments"] = []

        self.io = {
            "data/processed.json": {
                "save": False,
                "attribute": "processed"
            }
        }

        self.uptime = 0

        self.reply_to = []

        self.reddit = praw.Reddit(self.config["user_agent"])
        self.reddit.login(self.config["username"],
                          self.config["password"],
                          disable_warning="True")

    def _load_file(self, name):
        try:
            with open(name, "r") as reading_file:
                return json.loads(reading_file.read())
        except Exception as exception:
            logger.exception(exception)
            return {}

    def _save_file(self, name, attribute):
        with open(name, "w") as writing_file:
            writing_file.write(json.dumps(getattr(self, attribute)))

    def mark_for_saving(self, name):
        if not self.io[name]["save"]:
            self.io[name]["save"] = True

    def start(self):
        self.running = True
        rates = {}
        for process in self.config["rates"]:
            if self.config["rates"][process] in rates:
                rates[self.config["rates"][process]].append(process.capitalize())
            else:
                rates[self.config["rates"][process]] = [process.capitalize()]

        log(self.messages["thread_init"],
            {"num": 1, "thread_name": "Comments"})

        for rate in rates:
            rates[rate].sort()
            thread_name = "-".join(rates[rate])
            log(self.messages["thread_init"],
                {"num": list(rates.keys()).index(rate) + 2, "thread_name": thread_name})
            Thread(self._loop_runner,
                   thread_name,
                   [[getattr(self, "_{}_loop".format(loop.lower())) for loop in rates[rate]], rate])


        for comment in praw.helpers.comment_stream(self.reddit, "all+" + "+".join(self.config["subreddits"]), verbosity=0):
            if not self.running:
                break
            if comment.id in self.processed["comments"]:
                continue
            if self.should_reply_to(comment):
                log(self.messages["phrase_found"], {"comment": comment})
                self.reply_to.append(comment)
            self.add_comment_id(comment.id)
            self.mark_for_saving("data/processed.json")

    def stop(self):
        self.running = False

    def _loop_runner(self, loops, rate):
        while self.running:
            for loop in loops:
                loop()
            time.sleep(rate)

    def _io_loop(self):
        for file in self.io:
            if self.io[file]["save"]:
                self._save_file(file, self.io[file]["attribute"])
                self.io[file]["save"] = False

    def _uptime_loop(self):
        log(self.messages["uptime"], {"uptime": self.uptime})
        self.uptime += self.config["rates"]["uptime"]

    def add_comment_id(self, id):
        self.processed["comments"].append(id)
        if len(self.processed["comments"]) > 10000:
            self.processed["comments"] = self.processed["comments"][5000:-1]

    def should_reply_to(self, comment):
        if comment.author.name in self.config["ignored_users"]:
            return False
        if comment.subreddit.display_name in self.config["ignored_subreddits"]:
            return False
        for phrase in self.config["phrases"]:
            if phrase.lower() in comment.body.lower():
                return True
        return False

    def get_formated_message(self, comment):
        return ("\n".join(self.config["reply_message"])
                .format(comment=comment))

def log(message, args=None):
    if args is None:
        logger.info(message)
    else:
        logger.info(message.format(**args))


if __name__ == "__main__":
    logging_format = logging.Formatter("[%(asctime)s] [%(threadName)s]: %(message)s")
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    file_logger = logging.handlers.TimedRotatingFileHandler("logs/output.log",
                                                            when="midnight",
                                                            interval=1)
    file_logger.setFormatter(logging_format)
    logger.addHandler(file_logger)

    console_logger = logging.StreamHandler()
    console_logger.setFormatter(logging_format)
    logger.addHandler(console_logger)

    bot = WeDidItReddit()
    try:
        bot.start()
    except (KeyboardInterrupt, SystemExit):
        bot.stop()
        for file in bot.io:
            if bot.io[file]["save"]:
                log(bot.messages["saving"])
                bot._save_file(file, bot.io[file]["attribute"])
                log(bot.messages["saved"])
        log(bot.messages["shutdown"])

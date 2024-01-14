from datetime import date


class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.preferred_text_length = None
        self.completed_retellings = 0
        self.reg_date = date.today()
        self.scores = []
        self.seen_ids = []
        self.current_title = []

    def get_average_score(self):
        return sum(self.scores) // self.completed_retellings

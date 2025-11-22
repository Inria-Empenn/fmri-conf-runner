class TaskService:

    def get_task_contrasts(self, name: str):
        if name.lower() == "auditory":
            return self.get_auditory_contrasts()
        if name.lower() == "motor":
            return self.get_motor_contrasts()

    def get_auditory_contrasts(self):
        return [
            ('listening > rest', 'T', ['listening'], [1])
        ]

    def get_motor_contrasts(self):
        return [
            # ('left_foot', 'T', ['lf'], [1]),
            # ('left_hand', 'T', ['lh'], [1]),
            # ('right_foot', 'T', ['rf'], [1]),
            # ('right_hand', 'T', ['rh'], [1]),
            ('tongue', 'T', ['t'], [1])
        ]

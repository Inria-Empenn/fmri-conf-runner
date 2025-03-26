class DataDescriptor:
    data_path: str = ""
    input = {}
    result_path: str = ""
    work_path: str = ""
    task: str = ""
    subjects: list = []
    slices_nb: int = 0
    tr: float = 0.0
    units: str = ""

    def __init__(self, data: {}):
        self.data_path = data["data_path"]
        self.input = data["input"]
        self.result_path = data["result_path"]
        self.work_path = data["work_path"]
        self.task = data["task"]
        self.subjects = data["subjects"]
        self.slices_nb = data["slices_nb"]
        self.tr = data["tr"]
        self.units = data["units"]

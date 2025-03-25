class DataDescriptor:
    data_path = ""
    input = {}
    result_path = ""
    work_path = ""
    task = ""
    subjects = []
    slices_nb = 0
    tr = 0
    units = ""

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

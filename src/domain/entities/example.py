class Example:

    def __init__(self, id: str, name: str):

        if not name:
            raise ValueError("Name cannot be empty")

        self.id = id
        self.name = name

    def rename(self, new_name: str):

        if not new_name:
            raise ValueError("New name cannot be empty")

        self.name = new_name
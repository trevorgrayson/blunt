class Employee:
    def __init__(self, name=None, **kwargs):
        if '@' in name:
            self.email = name
            self.name = name.lower().split("@")[0].replace('.', ' ')
        else:
            self.name = name

        self.title = kwargs.get('Title')
        self.manager = kwargs.get('Manager') # TODO
        self.org = kwargs.get('Eng_Org')
        self.team = kwargs.get('Team')
        self.subteam = kwargs.get('Subteam')
        self.team_role = kwargs.get('Team Role')
        self.subteam_role = kwargs.get('Subteam Role')
        self.rest = kwargs

    def match(self, name):
        return name in self.name

    def __repr__(self):
        return f"{self.name} <{self.email}> {self.title}\n\t" +\
                f"{self.team}, {self.subteam}\n\t" +\
                f"{self.org} {self.subteam_role}\n\t" +\
                f"Reports to: {self.manager.name}"
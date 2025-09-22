class PagerDutyException(Exception):
    pass


class Incident:
    def __init__(self, **kwargs):
        """
        AI is super lazy
        :param kwargs:
        """
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def new(cls, kwargs):
        kwargs = dict(kwargs)
        if 'self' in kwargs:
            del kwargs['self']

        return Incident(**kwargs)

    def __str__(self):
        return "\t".join((
            self.status,
            self.urgency,
            self.created_at,
            self.title
        ))


from clients import databricks
from tbd.models import ImpactReport


def impact(*args, **kwargs) -> ImpactReport:
    """

    :param args:
    :param kwargs:
    :return: generator of results
    """
    return databricks.impact(*args, **kwargs)
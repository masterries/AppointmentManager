import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that can handle Decimal objects
    Used for properly serializing money values and other decimal data
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)
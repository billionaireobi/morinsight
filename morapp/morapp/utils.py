import uuid
import random
import string

def generate_order_number():
    """Generate a unique order number (ORD- + 12 chars)"""
    chars = string.ascii_uppercase + string.digits
    unique_id = ''.join(random.choices(chars, k=12))
    return f'ORD-{unique_id}'

def generate_transaction_id():
    """Generate a unique transaction ID (TXN- + 16 chars)"""
    return f'TXN-{uuid.uuid4().hex[:16]}'
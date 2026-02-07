from flask import Blueprint

payments_bp = Blueprint('payment', __name__, url_prefix='/payment')
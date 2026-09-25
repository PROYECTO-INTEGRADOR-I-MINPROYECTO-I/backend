from rest_framework.exceptions import APIException
from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ya existe un recurso con esos datos."
    default_code = "CONFLICT"

def custom_exception_handler(exc, context):
    # Call DRF's default exception handler first to get the standard response
    response = exception_handler(exc, context)

    if response is not None:
        # Customize DRF's standard error response format
        custom_data = {
            "success": False,
            "error": {
                "type": exc.__class__.__name__,
                "details": response.data
            }
        }
        response.data = custom_data
    else:
        # Handle standard Python / uncaught exceptions (e.g., ValueError, KeyError, Database errors)
        custom_data = {
            "success": False,
            "error": {
                "type": exc.__class__.__name__,
                "details": "An unexpected server error occurred."
            }
        }
        response = Response(custom_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
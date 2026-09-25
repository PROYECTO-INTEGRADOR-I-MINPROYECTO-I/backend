from rest_framework.exceptions import APIException
from rest_framework import status


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Ya existe un recurso con esos datos."
    default_code = "CONFLICT"

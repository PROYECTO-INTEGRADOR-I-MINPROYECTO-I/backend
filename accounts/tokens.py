import time

from rest_framework_simplejwt.tokens import RefreshToken


def issue_tokens(user, auth_time=None):
    """Return (refresh, access) strings for a user.

    Built by hand because RefreshToken.for_user assumes auth.User attributes.
    The access token copies the custom claims (user_id, ver, auth_time) from
    the refresh. auth_time is the original login (epoch seconds): pass it on
    refresh rotation so the session keeps its absolute age.
    """
    refresh = RefreshToken()
    refresh["user_id"] = user.user_id
    refresh["ver"] = user.token_version
    refresh["auth_time"] = int(time.time()) if auth_time is None else int(auth_time)
    return str(refresh), str(refresh.access_token)

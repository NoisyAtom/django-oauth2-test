import base64
import re
from functools import wraps

from django.utils.decorators import available_attrs
from django.core.validators import validate_email
from django.conf import settings

import logging

stdlogger = logging.getLogger(__name__)

from apps.credentials.models import (
    OAuthClient,
    OAuthUser,
    ValidationError,
)
from apps.tokens.models import (
    OAuthAuthorizationCode,
    OAuthAccessToken,
    OAuthRefreshToken,
    OAuthScope,
)
from proj.exceptions import (
    GrantTypeRequiredException,
    InvalidGrantTypeException,
    CodeRequiredException,
    UsernameRequiredException,
    PasswordRequiredException,
    RefreshTokenRequiredException,
    AccessTokenRequiredException,
    InvalidAccessTokenException,
    ExpiredAccessTokenException,
    InsufficientScopeException,
    ClientCredentialsRequiredException,
    InvalidClientCredentialsException,
    UserAccountLockedException,
    InvalidUserCredentialsException,
    AuthorizationCodeNotFoundException,
    RefreshTokenNotFoundException,
    DuplicateUserException,
)





def validate_request(func):
    """
    Validates that request contains all required data for creating, updating and deleting an OAuth User account. It
    looks for a valid client and client_id. It then validates the username and password for size and duplicate accounts.
    If scope parameters are given they will be set if part of the system.
    If account active is set, the account will be set as active, otherwise it will be set as deactivated.
    If the first name or last name are provided they will be set as part of the create request
    :param func:
    :return: decorator
    """

    stdlogger.info("Validate request decorator being called")


    def _extract_client(request):
        """
        Tries to extract client_id and client_secret from the request.
        It first looks for Authorization header, then tries POST data.
        Assigns client object to the request for later use.
        :param request:
        :return:
        """
        client_id, client_secret = None, None

        # First, let's check Authorization header if present
        if 'HTTP_AUTHORIZATION' in request.META:
            stdlogger.debug("We have a HTTP_AUTHORIZATION request ***. Which is: {}".format(request.META['HTTP_AUTHORIZATION']))
            auth_header = request.META['HTTP_AUTHORIZATION']
            auth_method, auth = re.split(':|;|,| ', auth_header)
            #auth_method, auth = request.META['HTTP_AUTHORIZATION'].split(':')
            if auth_method.lower() == 'basic':
                client_id, client_secret = base64.b64decode(auth).split(':')
                stdlogger.debug("client id is: {} , and client secret is: {}".format(client_id, client_secret))

        # Fallback to POST and then to GET
        if not client_id or not client_secret:
            stdlogger.info("Hit client check for a missing variable")
            try:
                client_id = request.POST['client_id']
                client_secret = request.POST['client_secret']
            except KeyError:
                try:
                    client_id = request.GET['client_id']
                    client_secret = request.GET['client_secret']
                except KeyError:
                    stdlogger.warning("Client ID and Client Secret is missing from the POST and GET method")
                    raise ClientCredentialsRequiredException()

        # Check client exists
        try:
            client = OAuthClient.objects.get(client_id=client_id)
        except OAuthClient.DoesNotExist:
            raise InvalidClientCredentialsException()

        # And that client secret is correct
        if not client.verify_password(client_secret):
            raise InvalidClientCredentialsException()

        request.client = client

    def _extract_username(request):
        """
        Tries to extract username and password from the request.
        It first looks for Authorization header, then tries POST data.
        Assigns client object to the request for later use.
        :param request:
        :return:
        """

        stdlogger.debug(" In _extract_username method for validating a request")

        username, password = None, None

        try:
            username = request.POST['username']
            stdlogger.info( "username from POST is: {}".format(username))
        except KeyError:
            try:
                username = request.GET['username']
            except KeyError:
                raise UsernameRequiredException()

        try:
            validate_email(username)

        except ValidationError:
            stdlogger.warning("email failed validation check for validating a user")
            raise InvalidUserCredentialsException

        try:
            password = request.POST['password']
            stdlogger.debug( "password from POST is: {}".format(password) )
        except KeyError:
            try:
                password = request.GET['password']
                stdlogger.debug( "password from GET is: {}".format(password))
            except KeyError:
                raise PasswordRequiredException()

        # Check username does not exist in the DB
        try:
            # Try create an OAuthUser object and validate that it's unique. Hence we just instantiate the object.
            stdlogger.info("Trying to create user: {}".format(username))
            user = OAuthUser(email=username, password=password, first_name="No name given", last_name="No name given")
            user.validate_unique()

        except ValidationError:
            stdlogger.warning( "we failed username check for creating a user")
            raise DuplicateUserException

        # OK we pass all validation checks pass the user object back in the request
        request.user = user

    def _extract_firstname(request):
        stdlogger.info( "Running extracting firstname method to extract users first name")

        """
        Tries to extract users first name from the request.
        It first looks for Authorization header, then tries POST data.
        Assigns client object to the request for later use. The user object needs to be present in the request object
        already for this to work, which should have been added by extracting the OAuth2 user name from the GET/POST
        message.

        This is an optional parameter. So if it is not present we don't care.
        :param request:
        :return:
        """

        try:
            first_name = request.POST['first_name']
            request.user.first_name = first_name
            stdlogger.info("User has a first name of: {}".format(first_name))
        except KeyError:
            try:
                first_name = request.GET['first_name']
                request.user.first_name = first_name
                stdlogger.info("User has a first name of: {}".format(first_name))
            except KeyError:
                #raise UsernameRequiredException()
                # This is an optional parameter so set it as false if it is not present
                request.user.first_name = "No name given"
                stdlogger.info("User has no first name being set")

    def _extract_lastname(request):
        stdlogger.info( "Running extracting lastname method to extract users last name")

        """
        Tries to extract users last name from the request.
        It first looks for Authorization header, then tries POST data.
        Assigns client object to the request for later use. The user object needs to be present in the request object
        already for this to work, which should have been added by extracting the OAuth2 user name from the GET/POST
        message.

        This is an optional parameter. So if it is not present we don't care.
        :param request:
        :return:
        """

        try:
            last_name = request.POST['last_name']
            request.user.last_name = last_name
            stdlogger.info("User has a last name of: {}".format(last_name))
        except KeyError:
            try:
                last_name = request.GET['last_name']
                request.user.last_name = last_name
                stdlogger.info("User has a last name of: {}".format(last_name))
            except KeyError:
                #raise UsernameRequiredException()
                # This is an optional parameter so set it as false if it is not present
                request.user.last_name = "No name given"
                stdlogger.info("User has no last name being set")

    def _extract_active(request):
        stdlogger.info( "Running extracting active method to extract if the account is active or not")

        """
        Tries to extract the 'Active' flag. Active means the account is active and has been verified. If the flag is
        not present or set as FALSE then the account has not been verified.
        It first looks for Authorization header, then tries POST data.
        Assigns client object to the request for later use. This is an optional parameter. If it is not present then the
        account is deemed to be not active. i.e. not verified
        :param request:
        :return:
        """

        try:
            accountVerified = request.POST['account_verified']
            request.user.account_is_verified = accountVerified
        except KeyError:
            try:
                accountVerified = request.GET['account_verified']
                request.user.account_is_verified = accountVerified
            except KeyError:
                #raise UsernameRequiredException()
                # This is an optional parameter so set it as false if it is not present
                request.user.account_is_verified = False
                request.account_verified = False

    def _extract_scope(request):
        """
        Tries to extract authorization scope from the request.
        Appropriate scope models are fetched from the database
        and assigned to the request.
        :param request:
        :return:
        """

        stdlogger.info( "Running Extracting scope method from the request to validate a user")

        if request.grant_type not in ('client_credentials', 'password'):
            return

        if settings.OAUTH2_SERVER['IGNORE_CLIENT_REQUESTED_SCOPE']:
            request.scopes = OAuthScope.objects.filter(is_default=True)
            return

        try:
            scopes = request.POST['scope'].split(' ')
        except KeyError:
            try:
                scopes = request.GET['scope'].split(' ')
            except KeyError:
                scopes = []

        request.scopes = OAuthScope.objects.filter(scope__in=scopes)

        # Fallback to the default scope if no scope sent with the request
        if len(request.scopes) == 0:
            request.scopes = OAuthScope.objects.filter(is_default=True)

    def decorator(request, *args, **kwargs):
        stdlogger.debug( "decorator is hit for administration REST interface...")
        _extract_client(request=request)
        _extract_username(request=request)
        _extract_active(request=request)
        _extract_firstname(request=request)
        _extract_lastname(request=request)
        #_extract_scope(request=request)

        return func(request, *args, **kwargs)

    return decorator


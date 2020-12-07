from __future__ import absolute_import
from . import *
from udsoncan.Response import Response
from udsoncan.exceptions import *

class SecurityAccess(BaseService):
    _sid = 0x27

    supported_negative_response = [	Response.Code.SubFunctionNotSupported, 
                                                    Response.Code.IncorrectMessageLengthOrInvalidFormat,
                                                    Response.Code.ConditionsNotCorrect,
                                                    Response.Code.RequestSequenceError,
                                                    Response.Code.RequestOutOfRange,
                                                    Response.Code.InvalidKey,
                                                    Response.Code.ExceedNumberOfAttempts,
                                                    Response.Code.RequiredTimeDelayNotExpired
                                                    ]

    class Mode(object):
        RequestSeed=0
        SendKey=1

    @classmethod 
    def normalize_level(cls, mode, level):
        cls.validate_mode(mode)
        ServiceHelper.validate_int(level, min=0, max=0x7F, name=u'Security level')

        if mode == cls.Mode.RequestSeed:
            return level if level % 2 == 1 else level-1
        elif mode == cls.Mode.SendKey:
            return level if level % 2 == 0 else level+1

    @classmethod
    def make_request(cls, level, mode, key=None):
        u"""
        Generates a request for SecurityAccess

        :param level: Service subfunction. The security level to unlock. Value ranging from 0 to 7F 
                For mode=``RequestSeed`` (0), level must be an even value. For mode=``SendKey`` (1), level must be an odd value.
                If the even/odd constraint is not respected, the level value will be corrected to properly set the LSB.
        :type level: int

        :param mode: Type of request to perform. ``SecurityAccess.Mode.RequestSeed`` or ``SecurityAccess.Mode.SendKey`` 
        :type mode: SecurityAccess.Mode, int

        :param key: When mode=``SendKey``, this value must be provided.
        :type key: bytes

        :raises ValueError: If parameters are out of range, missing or wrong type
        """		
        from udsoncan import Request
        cls.validate_mode(mode)

        ServiceHelper.validate_int(level, min=0, max=0x7F, name=u'Security level')
        req = Request(service=cls, subfunction=cls.normalize_level(mode=mode, level=level))

        if mode == cls.Mode.SendKey:
            if not isinstance(key, str):
                raise ValueError(u'key must be a valid bytes object')
            req.data = key

        return req

    @classmethod
    def interpret_response(cls, response, mode):
        u"""
        Populates the response ``service_data`` property with an instance of :class:`SecurityAccess.ResponseData<udsoncan.services.SecurityAccess.ResponseData>`

        :param response: The received response to interpret
        :type response: :ref:`Response<Response>`

        :raises InvalidResponseException: If length of ``response.data`` is too short
        :raises ValueError: If mode is not ``RequestSeed`` or ``SendKey``
        """

        cls.validate_mode(mode)

        response.service_data = cls.ResponseData()
        minlength = 2 if mode == cls.Mode.RequestSeed else 1

        if len(response.data) < minlength:
            raise InvalidResponseException(response, u"Response data must be at least %d bytes" % (minlength))

        response.service_data.security_level_echo = ord(response.data[0])

        if mode == cls.Mode.RequestSeed:
            response.service_data.seed = response.data[1:]

    @classmethod
    def validate_mode(cls, mode):
        if mode not in [cls.Mode.RequestSeed, cls.Mode.SendKey]:
            raise ValueError(u'Given mode must be either be RequestSeed (0) or SendKey (1).')

    class ResponseData(BaseResponseData):
        u"""
        .. data:: security_level_echo

                Requests subfunction echoed back by the server

        .. data:: seed

                Seed value. Only present if request mode was ``RequestSeed`` (even subfunction)
        """		
        def __init__(self):
            super(SecurityAccess.ResponseData, self).__init__(SecurityAccess)

            self.security_level_echo = None
            self.seed = None

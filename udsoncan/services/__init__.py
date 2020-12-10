from __future__ import absolute_import
from udsoncan.Response import Response
from udsoncan.exceptions import *
import inspect
import sys
from abc import ABCMeta

ABC = ABCMeta(str('ABC'), (), {})

def to_bytes(n, length, endianess='big'):
    u"""
    https://stackoverflow.com/questions/16022556/has-python-3-to-bytes-been-back-ported-to-python-2-7
    """
    h = '%x' % n
    s = ('0'*(len(h) % 2) + h).zfill(length*2).decode('hex')
    return s if endianess == 'big' else s[::-1]

def cls_from_request_id(given_id):
    return BaseService.from_request_id(given_id)

def cls_from_response_id(given_id):
    return BaseService.from_response_id(given_id)

class BaseSubfunction(object):

    @classmethod
    def get_name(cls, subfn_id):
        attributes = inspect.getmembers(cls, lambda a:not(inspect.isroutine(a)))
        subfn_list = [a for a in attributes if not(a[0].startswith(u'__') and a[0].endswith(u'__'))]

        for subfn in subfn_list:
            if isinstance(subfn[1], (int, long)):
                if subfn[1] == subfn_id:     # [1] is value
                    return unicode(subfn[0]) # [0] is property name
            elif isinstance(subfn[1], tuple):
                if subfn_id >= subfn[1][0] or subfn_id <= subfn[1][1]:
                    return unicode(subfn[0])
        name = cls.__name__ if not hasattr(cls, u'__pretty_name__') else cls.__pretty_name__
        return u'Custom %s' % name

class BaseService(ABC):

    always_valid_negative_response = [
            Response.Code.GeneralReject,
            Response.Code.ServiceNotSupported,
            Response.Code.ResponseTooLong,
            Response.Code.BusyRepeatRequest,
            Response.Code.NoResponseFromSubnetComponent,
            Response.Code.FailurePreventsExecutionOfRequestedAction,
            Response.Code.SecurityAccessDenied, # ISO-14229:2006 Table A.1:  "Besides the mandatory use of this negative response code as specified in the applicable services within ISO 14229, this negative response code can also be used for any case where security is required and is not yet granted to perform the required service."
            Response.Code.RequestCorrectlyReceived_ResponsePending,
            Response.Code.ServiceNotSupportedInActiveSession
    ]

    @classmethod	# Returns the service ID used for a client request
    def request_id(cls):
        return cls._sid

    @classmethod	# Returns the service ID used for a server response
    def response_id(cls):
        return cls._sid + 0x40

    @classmethod	# Returns an instance of the service identified by the service ID (Request)
    def from_request_id(cls, given_id):
        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if hasattr(obj, u"__bases__") and cls in obj.__bases__:
                if obj.request_id() == given_id:
                    return obj

    @classmethod	# Returns an instance of the service identified by the service ID (Response)
    def from_response_id(cls, given_id):

        for name, obj in inspect.getmembers(sys.modules[__name__]):
            if hasattr(obj, u"__bases__") and cls in obj.__bases__:
                if obj.response_id() == int(given_id):
                    return obj

    #Default subfunction ID for service that does not implement subfunction_id().
    def subfunction_id(self):
        return 0

    @classmethod	# Tells if this service includes a subfunction byte
    def use_subfunction(cls):
        if hasattr(cls, u'_use_subfunction'):
            return cls._use_subfunction
        else:
            return True
    @classmethod
    def has_response_data(cls):
        if hasattr(cls, u'_no_response_data'):
            return False if cls._no_response_data else True
        else:
            return True

    @classmethod	# Returns the service name. Shortcut that works on class and instances
    def get_name(cls):
        return unicode(cls.__name__)

    @classmethod	# Tells if the given response code is expected for this service according to UDS standard.
    def is_supported_negative_response(cls, code):
        supported = False
        if code in cls.supported_negative_response:
            supported = True

        if code in cls.always_valid_negative_response:
            supported = True

        # As specified by Annex A, negative response code ranging above 0x7F can be used anytime if the service can return ConditionNotCorrect
        if code >= 0x80 and code < 0xFF and Response.Code.ConditionsNotCorrect in cls.supported_negative_response:
            supported = True

        # ISO-14229:2006 Table A.1 : "This response code shall be supported by each diagnostic service with a subfunction parameter"
        if code == Response.Code.SubFunctionNotSupportedInActiveSession and cls.use_subfunction():
            supported = True

        return supported

def is_valid_service(service_cls):
    return issubclass(service_cls, BaseService)

class ServiceHelper(object):

    @staticmethod
    def validate_int(value, min=0, max=0xFF, name=u'value'):
        if not isinstance(value, (int, long)):
            raise ValueError(u"%s must be a valid integer" % (name))
        if value < min or value > max:
            raise ValueError(u"%s must be an integer between 0x%X and 0x%X" % (name, min, max))

    # Make sure that the actual client configuration contains valid definitions for given Data Identifiers
    @staticmethod
    def check_did_config(didlist, didconfig):
        didlist = [didlist] if not isinstance(didlist, list) else didlist
        if u'data_identifiers' in didconfig:
            didconfig = config[u'data_identifiers']

        for did in didlist:
            if did not in didconfig:
                raise ConfigError(did, msg=u'Actual data identifier configuration contains no definition for data identifier 0x%04x' % did)

        return didconfig

    # Make sure that the actual client configuration contains valid definitions for given Input/Output Data Identifiers
    @staticmethod
    def check_io_config(didlist, ioconfig):
        didlist = [didlist] if not isinstance(didlist, list) else didlist
        if u'input_output' in ioconfig:
            ioconfig = ioconfig[u'input_output']

        if not isinstance(ioconfig, dict):
            raise ConfigError(u'input_output', msg=u'Configuration of Input/Output section must be a dict.')

        for did in didlist:
            if did not in ioconfig:
                raise ConfigError(key=did, msg=u'Actual Input/Output configuration contains no definition for data identifier 0x%04x' % did)
            if isinstance(ioconfig[did], dict):	# IO Control services has that concept of composite DID. We define them with dicts.
                if u'codec'not in ioconfig[did]:
                    raise ConfigError(u'codec', msg=u'Configuration for Input/Output identifier 0x%04x is missing a codec')

                if u'mask' in ioconfig[did]:
                    mask_def = ioconfig[did][u'mask']
                    for mask_name in mask_def:
                        if not isinstance(mask_def[mask_name], (int, long)):
                            raise ValueError(u'In Input/Output configuration for did 0x%04x, mask "%s" is not an integer' % (did, mask_name))

                        if mask_def[mask_name] < 0:
                            raise ValueError(u'In Input/Output configuration for did 0x%04x, mask "%s" is not a positive integer' % (did, mask_name))


                if u'mask_size' in ioconfig[did]:
                    if not isinstance(ioconfig[did][u'mask_size'], (int, long)):
                        raise ValueError(u'mask_size in Input/Output configuration for did 0x%04x must be a valid integer' % (did))

                    if ioconfig[did][u'mask_size'] < 0:
                        raise ValueError(u'mask_size in Input/Output configuration for did 0x%04x must be greater than 0' % (did))

                    if u'mask' in ioconfig[did]:
                        mask_def = ioconfig[did][u'mask']
                        for mask_name in mask_def:
                            if mask_def[mask_name] > 2**(ioconfig[did][u'mask_size']*8)-1:
                                raise ValueError(u'In Input/Output configuration for did 0x%04x, mask "%s" cannot fit in %d bytes (defined by mask_size)' % (did, mask_name,ioconfig[did][u'mask_size']))

        return ioconfig

class BaseResponseData(object):
    def __init__(self, service_class):
        if not issubclass(service_class, BaseService):
            raise ValueError(u'service_class must be a service class')

        self.service_class = service_class

    def __repr__(self):
        return u'<%s (%s) at 0x%08x>' % (self.__class__.__name__, self.service_class.__name__, id(self))

from .DiagnosticSessionControl import DiagnosticSessionControl
from .ECUReset import ECUReset
from .SecurityAccess import SecurityAccess
from .CommunicationControl import CommunicationControl
from .AccessTimingParameter import AccessTimingParameter
from .SecuredDataTransmission import SecuredDataTransmission
from .TesterPresent import TesterPresent
from .ControlDTCSetting import ControlDTCSetting
from .ResponseOnEvent import ResponseOnEvent
from .LinkControl import LinkControl
from .ReadDataByIdentifier import ReadDataByIdentifier
from .WriteDataByIdentifier import WriteDataByIdentifier
from .ReadMemoryByAddress import ReadMemoryByAddress
from .InputOutputControlByIdentifier import InputOutputControlByIdentifier
from .RoutineControl import RoutineControl
from .ReadScalingDataByIdentifier import ReadScalingDataByIdentifier
from .ReadDataByPeriodicIdentifier import ReadDataByPeriodicIdentifier
from .WriteMemoryByAddress import WriteMemoryByAddress
from .DynamicallyDefineDataIdentifier import DynamicallyDefineDataIdentifier
from .ClearDiagnosticInformation import ClearDiagnosticInformation
from .ReadDTCInformation import ReadDTCInformation
from .RequestDownload import RequestDownload
from .RequestUpload import RequestUpload
from .TransferData import TransferData
from .RequestTransferExit import RequestTransferExit
from .RequestFileTransfer import RequestFileTransfer

from enum import Enum

class ResponseSignals(Enum):
    SUCCESS = "Success"
    ERROR = "Error"
    NOT_FOUND = "Not Found"
    UNAUTHORIZED = "Unauthorized"
    FORBIDDEN = "Forbidden"
    BAD_REQUEST = "Bad Request"
    FILE_SIZE_EXCEEDED = "File size exceeded"
    FILE_TYPE_NOT_ALLOWED = "File type not allowed"
    FILE_UPLOAD_FAILED = "File upload failed"
    FILE_UPLOAD_SUCCESS = "File uploaded successfully"
    FILE_PROCESS_FAILED = "File processing failed"
    FILE_PROCESS_SUCCESS = "File processed successfully"
    NO_FILES_FOUND = "No files found for the project"
    FILE_NOT_SUPPORTED = "File type not supported"
    
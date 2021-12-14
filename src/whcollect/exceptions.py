class BadResponse(Exception):
    """Exception indicating that a request has produced an undesirable response.

    This is necessary because in functions that suppress exceptions raised from
    a request that is tried multiple times, the caller needs to be alerted if all
    the tries failed, and also let the caller access the last exception thrown
    from the requests.

    The latter is stored in the exception instance to prevent printing its trace-
    back in case this exception goes unhandled.
    """

    def __init__(self, *args, last_exception_caught: Exception | None = None):
        super().__init__(*args)
        self.last_exception_caught = last_exception_caught

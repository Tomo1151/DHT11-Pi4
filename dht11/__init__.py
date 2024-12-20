#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Simple DHT11 sensor reader class

Usage:
    >>> sensor = DHT11(signal_pin=26)
    >>> response = sensor.read()
    >>> if response.is_valid():
    >>>     print(f"Temperature: {response.temperature}, Humidity: {response.humidity}")
    >>> else:
    >>>     print(f"Invalid data: {response}")
"""


import RPi.GPIO as GPIO
import time

# MARK: Exceptions
class DHT11Error(Exception):
    """
    Base class for DHT11 exceptions

    Attributes:
        message (str): error message
    """
    def __init__(self, message: str) -> None:
        self.message = message
    def __str__(self):
        return self.message

class DHT11ChecksumError(DHT11Error):
    """
    Exception raised when the checksum validation fails
    """
    def __init__(self) -> None:
        super().__init__("Checksum validation failed")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"

class DHT11TimeoutError(DHT11Error):
    """
    Exception raised when the maximum number of retries is reached
    """
    def __init__(self) -> None:
        super().__init__("Timeout error")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"

class DHT11InvalidDataError(DHT11Error):
    """
    Exception raised when the data is invalid
    """
    def __init__(self) -> None:
        super().__init__("Invalid data")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


# MARK: DHT11Response
class DHT11Response:
    """
    DHT11 sensor response class

    Attributes:
        STATUS_OK (int): status code for a successful response
        STATUS_ERROR_CHECKSUM (int): status code for a checksum error
        STATUS_ERROR_TIMEOUT (int): status code for a timeout error

        status (int): status code
        temperature (float): temperature value
        humidity (float): humidity value
    """
    STATUS_OK: int = 0
    STATUS_ERROR_CHECKSUM: int = 1
    STATUS_ERROR_TIMEOUT: int = 2

    status: int = STATUS_OK
    temperature: float = -1
    humidity: float = -1

    def __init__(self, status: int, temperature: float = -1, humidity: float = -1) -> None:
        self.status = status
        self.temperature = temperature
        self.humidity = humidity


    def is_valid(self) -> bool:
        return self.status == DHT11Response.STATUS_OK


    def __str__(self) -> str:
        return f"Response(status={self.status}, temperature={self.temperature}, humidity={self.humidity})"

    def __repr__(self) -> str:
        return self.__str__()


# MARK: DHT11
class DHT11:
    """
    DHT11 sensor reader class

    Attributes:
        signal_pin (int): GPIO pin number (BCM) where the sensor is connected
        max_tries (int): maximum number of retries to read data
        min_interval (int | float): minimum interval between reads in seconds
        raise_error (bool): whether to raise an exception when an error occurs

    """
    MIN_INTERVAL: int = 2

    def __init__(self, signal_pin: int, max_tries: int = 10, min_interval: int | float = MIN_INTERVAL, raise_error: bool = False) -> None:
        self.signal_pin = signal_pin
        self.max_tries = max_tries
        self.min_interval = min_interval


    def __send_signal(self, signal: bool, timeout: int = 0) -> None:
        """
        Send a signal to the sensor

        Args:
            signal (bool): signal to send
            timeout (int | float): time to wait after sending the signal

        Returns:
            None
        """
        GPIO.output(self.signal_pin, signal)
        time.sleep(timeout)


    def __collect_input(self) -> list[bool]:
        """
        Collect input data from the sensor

        Returns:
            list[bool]: input data
        """
        unchanged_count: int = 0
        unchanged_threshold: int = 200
        last: int = -1
        data: list[bool] = []

        GPIO.setup(self.signal_pin, GPIO.IN)

        while unchanged_count < unchanged_threshold:
            current: bool = GPIO.input(self.signal_pin)
            data.append(current)

            if last != current:
                unchanged_count = 0
                last = current
            unchanged_count += 1

        return data


    def __parse_input_data(self, data: list[bool]) -> list[int]:
        """
        Parse input data from the sensor

        Args:
            data (list[bool]): input data

        Returns:
            list[int]: parsed signals
        """
        signals: list[int] = []
        input_length: int = len(data)
        pattern: int = 0

        # find the beginning of the data
        for i in range(input_length):
            if pattern == 0 and data[i] == GPIO.LOW:
                pattern = 1
            if pattern == 1 and data[i] == GPIO.HIGH:
                pattern = 2
            if pattern == 2 and data[i] == GPIO.LOW:
                break
        if i >= input_length:
            return signals

        high_signal_length: int = 0
        for j in range(i, input_length):
            if data[j] == GPIO.HIGH:
                high_signal_length += 1
            elif data[j] == GPIO.LOW:
                if high_signal_length > 0:
                    signals.append(high_signal_length)
                    high_signal_length = 0

        return signals


    def __calculate_bits(self, signals: list[int]) -> list[int]:
        """
        Calculate bits from signals

        Args:
            signals (list[int]): signals

        Returns:
            list[int]: bytes

        Notes:
            bytes[0] - integral part of humidity  
            bytes[1] - decimal part of humidity  
            bytes[2] - integral part of temperature  
            bytes[3] - decimal part of temperature  
            bytes[4] - checksum  
        """
        half_length: int = (min(signals) + max(signals)) / 2
        bits = 0

        for signal in signals:
            bits <<= 1
            if signal > half_length:
                bits |= 1

        bytes: list[int] = [
            (bits >> 32) & 0xFF,
            (bits >> 24) & 0xFF,
            (bits >> 16) & 0xFF,
            (bits >>  8) & 0xFF,
            (bits      ) & 0xFF
        ]

        return bytes


    def __validate_checksum(self, bytes: list[int]) -> bool:
        """
        Validate checksum

        Args:
            bytes (list[int]): bytes

        Returns:
            bool: True if the checksum is valid, False otherwise
        """
        return bytes[4] == (bytes[0] + bytes[1] + bytes[2] + bytes[3]) & 0xFF


    # MARK: Public methods
    def read(self) -> DHT11Response:
        """
        Read data from the sensor.

        Returns:
            DHT11Response: Response.

        Raises:
            DHT11TimeoutError: If the maximum number of retries is reached.
            DHT11InvalidDataError: If the data is invalid.
            DHT11ChecksumError: If the checksum is invalid.

        Examples:
            >>> sensor = DHT11(signal_pin=26)
            >>> response = sensor.read()  
            >>> if response.is_valid():  
            >>>     print(f"Temperature: {response.temperature}, Humidity: {response.humidity}")  
            >>> else:  
            >>>     print(f"Invalid data: {response}")  
        """
        try_count: int = 0

        while self.max_tries > try_count:
            try:
                GPIO.setup(self.signal_pin, GPIO.OUT, initial=GPIO.HIGH)
                time.sleep(.5)

                # initial signal
                self.__send_signal(GPIO.HIGH, .05) # HIGH 50ms
                self.__send_signal(GPIO.LOW, .02) # LOW 20ms

                # wait for sensor response
                input_data: list[bool] = self.__collect_input()
                signals: list[int] = self.__parse_input_data(input_data)

                if len(signals) != 40:
                    raise DHT11InvalidDataError

                bytes: list[int] = self.__calculate_bits(signals)

                if not self.__validate_checksum(bytes):
                    raise DHT11ChecksumError

                humidity = bytes[0] + bytes[1] / 10
                temperature = bytes[2] + (bytes[3] & 0x7F) / 10

                if bytes[3] & 0x80:
                    temperature *= -1

                status = DHT11Response.STATUS_OK
                return DHT11Response(status, temperature, humidity)

            except DHT11Error as e:
                try_count += 1
                time.sleep(self.min_interval)

        if self.raise_error:
            raise DHT11TimeoutError
        return DHT11Response(DHT11Response.STATUS_ERROR_TIMEOUT)

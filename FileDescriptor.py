# Descriptor of a FITS file to be processed.  Name and other attributes that we'll
# display in the file table in the main UI
import os


class FileDescriptor:
    # Code for file type - corresponds to the numbers TheSkyX uses for same.
    # These can't be changed, since they are used in JavaScript commands send to the TheSkyX server.
    FILE_TYPE_UNKNOWN = 0
    FILE_TYPE_LIGHT = 1
    FILE_TYPE_BIAS = 2
    FILE_TYPE_DARK = 3
    FILE_TYPE_FLAT = 4

    def __init__(self, absolute_path: str):
        """
        Initialize file descriptor object, with given path name and default values.
        :param absolute_path:   Absolute path to file in flie system
        """
        self._absolute_path: str = absolute_path
        self._type: int = self.FILE_TYPE_UNKNOWN
        self._binning: int = 0
        self._x_size: int = 0
        self._y_size: int = 0
        self._filter_name: str = "(unknown)"
        self._exposure: float = 0.0
        self._temperature: float = 0.0
        self._average_adus: int = -1    # -1 is "not set" value

    def get_absolute_path(self) -> str:
        return self._absolute_path

    def get_name(self) -> str:
        return os.path.basename(self._absolute_path)

    def get_type(self) -> int:
        assert self.FILE_TYPE_UNKNOWN <= self._type <= self.FILE_TYPE_FLAT
        return self._type

    def set_type(self, file_type: int):
        assert self.FILE_TYPE_UNKNOWN <= file_type <= self.FILE_TYPE_FLAT
        self._type = file_type

    def get_type_name(self) -> str:
        if self._type == self.FILE_TYPE_LIGHT:
            result = "Light"
        elif self._type == self.FILE_TYPE_FLAT:
            result = "Flat"
        elif self._type == self.FILE_TYPE_DARK:
            result = "Dark"
        elif self._type == self.FILE_TYPE_BIAS:
            result = "Bias"
        else:
            result = "Unknown"
        return result

    def get_binning(self) -> int:
        return self._binning

    def set_binning(self, x_binning: int, y_binning: int):
        assert x_binning == y_binning
        self._binning = x_binning

    def get_dimensions(self) -> (int, int):
        return self._x_size, self._y_size

    def get_x_dimension(self) -> int:
        return self._x_size

    def get_y_dimension(self) -> int:
        return self._y_size

    def get_size_key(self):
        """
        Get the "size key" used for grouping files.
        Clustering algorithm clusters on a single value, but size is 2-dimensional,
        so size key is a string with x and y dimensions and binning joined by a delimiter
        :return:    String uniquely encoding the height and width, suitable for clustering
        """
        return f"binned {self._binning} x {self._binning}, dimensions " \
               f"{self._x_size} x {self._y_size}"

    def set_dimensions(self, x_size: int, y_size: int):
        self._x_size = x_size
        self._y_size = y_size

    def get_filter_name(self) -> str:
        return self._filter_name

    # Filter name in all lower-case to facilitate case insensitive comparisons
    def get_filter_name_lower(self) -> str:
        return self._filter_name.lower()

    def set_filter_name(self, name: str):
        self._filter_name = name

    def get_exposure(self) -> float:
        return self._exposure

    def set_exposure(self, exposure: float):
        self._exposure = exposure

    def get_temperature(self) -> float:
        return self._temperature

    def set_temperature(self, temperature: float):
        self._temperature = temperature

    def get_average_adus(self) -> int:
        return self._average_adus

    def set_average_adus(self, adus: int):
        self._average_adus = adus

    def __str__(self) -> str:
        return f"{self.get_name()}: {self._binning} {self._exposure} {self._temperature}"

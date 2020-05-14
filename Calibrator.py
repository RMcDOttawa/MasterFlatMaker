#
#   Class to handle calibration of images using specified method (including none)
#
import sys
from typing import Optional

import numpy
from numpy import ndarray

import MasterMakerExceptions
from Console import Console
from Constants import Constants
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from RmFitsUtil import RmFitsUtil
from SessionController import SessionController
from SharedUtils import SharedUtils


class Calibrator:
    #
    #   Create calibration object against the given data model's settings
    #
    def __init__(self, data_model: DataModel):
        self._data_model = data_model

    def calibrate_images(self, file_data: [ndarray],
                         descriptors: [FileDescriptor],
                         console: Console,
                         session_controller: SessionController) -> [ndarray]:
        assert len(descriptors) > 0
        sample_file = descriptors[0]
        calibration_type = self._data_model.get_precalibration_type()
        if calibration_type == Constants.CALIBRATION_NONE:
            return file_data
        elif calibration_type == Constants.CALIBRATION_PEDESTAL:
            return self.calibrate_with_pedestal(file_data,
                                                self._data_model.get_precalibration_pedestal(),
                                                console,
                                                session_controller)
        elif calibration_type == Constants.CALIBRATION_FIXED_FILE:
            return self.calibrate_with_file(file_data,
                                            self._data_model.get_precalibration_fixed_path(),
                                            console,
                                            session_controller)
        else:
            assert calibration_type == Constants.CALIBRATION_AUTO_DIRECTORY
            return self.calibrate_with_auto_directory(file_data,
                                                      self._data_model.get_precalibration_auto_directory(),
                                                      descriptors,
                                                      console,
                                                      session_controller)

    def calibrate_with_pedestal(self,
                                file_data: [ndarray],
                                pedestal: int,
                                console: Console,
                                session_controller: SessionController) -> [ndarray]:
        result = file_data.copy()
        console.message(f"Calibrate with pedestal = {pedestal}", 0)
        for index in range(len(result)):
            if session_controller.thread_cancelled():
                raise MasterMakerExceptions.SessionCancelled
            reduced_by_pedestal: ndarray = result[index] - pedestal
            result[index] = reduced_by_pedestal.clip(0, 0xFFFF)
        return result

    def calibrate_with_file(self, file_data: [ndarray], calibration_file_path: str, console: Console,
                            session_controller: SessionController) -> [ndarray]:
        console.message(f"Calibrate with file: {calibration_file_path}", 0)
        result = file_data.copy()
        calibration_image = RmFitsUtil.fits_data_from_path(calibration_file_path)
        (calibration_x, calibration_y) = calibration_image.shape
        for index in range(len(result)):
            if session_controller.thread_cancelled():
                raise MasterMakerExceptions.SessionCancelled
            (layer_x, layer_y) = result[index].shape
            if (layer_x != calibration_x) or (layer_y != calibration_y):
                raise MasterMakerExceptions.IncompatibleSizes
            difference = result[index] - calibration_image
            result[index] = difference.clip(0, 0xFFFF)
        return result

    # Calibrate the given files' contents, each with the best-matching calibration file
    # from a directory.  "Best" is measured by trying to match both the exposure time
    # and temperature, with more weight to the exposure time.  A separate file is chosen
    # for each input image, since the exposure times of collected flats often vary
    # during the collection session, to keep the ADU level constant as the light changes.

    def calibrate_with_auto_directory(self, file_data: [ndarray], auto_directory_path: str,
                                      descriptors: [FileDescriptor], console: Console,
                                      session_controller: SessionController) -> [ndarray]:
        assert len(file_data) > 0
        assert len(file_data) == len(descriptors)

        # Get all calibration files from directory so we only have to read it once
        directory_files = self.all_descriptors_from_directory(auto_directory_path,
                                                              self._data_model.get_auto_directory_recursive())
        if session_controller.thread_cancelled():
            raise MasterMakerExceptions.SessionCancelled
        if len(directory_files) == 0:
            # No files in that directory, raise exception
            raise MasterMakerExceptions.AutoCalibrationDirectoryEmpty(auto_directory_path)

        console.message(f"Calibrating from directory containing {len(directory_files)} files.", +1)
        result = file_data.copy()
        for input_index in range(len(descriptors)):
            if session_controller.thread_cancelled():
                raise MasterMakerExceptions.SessionCancelled
            this_file: FileDescriptor = descriptors[input_index]
            calibration_file = self.get_best_calibration_file(directory_files,
                                                              this_file,
                                                              session_controller, console)
            if session_controller.thread_cancelled():
                raise MasterMakerExceptions.SessionCancelled
            calibration_image = RmFitsUtil.fits_data_from_path(calibration_file)
            (calibration_x, calibration_y) = calibration_image.shape
            (layer_x, layer_y) = result[input_index].shape
            if (layer_x != calibration_x) or (layer_y != calibration_y):
                raise MasterMakerExceptions.IncompatibleSizes
            difference = result[input_index] - calibration_image
            result[input_index] = difference.clip(0, 0xFFFF)
        return result

    #
    # Get the best matched calibration file in the auto directory.  Only BIAS files
    # of the correct size will be selected
    # If no suitable file, raise exception
    #
    #   Exceptions thrown:
    #       NoSuitableAutoBias

    def get_best_calibration_file(self, directory_files, sample_file: FileDescriptor,
                                  session_controller: SessionController,
                                  console: Console) -> Optional[str]:
        # Filter to Bias or Dark files if option and give exception if none
        if self._data_model.get_auto_directory_bias_only():
            all_descriptors = list((d for d in directory_files
                                    if (d.get_type() == FileDescriptor.FILE_TYPE_BIAS
                                        or d.get_type() == FileDescriptor.FILE_TYPE_DARK)))
            if len(all_descriptors) == 0:
                raise MasterMakerExceptions.AutoCalibrationNoBiasFiles
        else:
            all_descriptors = directory_files

        # Get the subset that are the correct size and binning
        correct_size_files = self.filter_to_correct_size(all_descriptors, sample_file)
        if session_controller.thread_cancelled():
            raise MasterMakerExceptions.SessionCancelled
        if len(correct_size_files) == 0:
            # No files in that directory are the correct size
            raise MasterMakerExceptions.NoSuitableAutoBias

        # From the correct-sized files, find the one closest to the sample file temperature and exposure
        closest_match = self.closest_match(correct_size_files,
                                           sample_file.get_exposure(),
                                           sample_file.get_temperature(),
                                           console)
        return closest_match.get_absolute_path()

    def all_descriptors_from_directory(self, directory_path: str,
                                       recursive: bool) -> [FileDescriptor]:
        paths: [str] = SharedUtils.files_in_directory(directory_path, recursive)
        descriptors = RmFitsUtil.make_file_descriptions(paths)
        return descriptors

    def filter_to_correct_size(self, all_descriptors: [FileDescriptor], sample_file: FileDescriptor) \
            -> [FileDescriptor]:
        x_dimension = sample_file.get_x_dimension()
        y_dimension = sample_file.get_y_dimension()
        binning = sample_file.get_binning()
        d: FileDescriptor
        filtered = [d for d in all_descriptors
                    if d.get_x_dimension() == x_dimension
                    and d.get_y_dimension() == y_dimension
                    and d.get_binning() == binning]
        return filtered

    # Calibrate the given files, each with the closest-matching calibration file found
    # in a given directory.  We try to match both the exposure time and the temperature,
    # giving more weight to the exposure time.

    def closest_match(self, descriptors: [FileDescriptor],
                      target_exposure: float,
                      target_temperature: float,
                      console: Console) -> FileDescriptor:
        # Assign a score to each possible calibration file, based on exposure and temperature
        f: FileDescriptor
        file_temperatures = numpy.array([f.get_temperature() for f in descriptors])
        file_exposures = numpy.array([f.get_exposure() for f in descriptors])
        scores = numpy.abs(file_temperatures - target_temperature) \
                 + numpy.abs(file_exposures - target_exposure) * Constants.AUTO_CALIBRATION_EXPOSURE_WEIGHT
        # The score is the deviation from the target, so the smallest score is the best choice
        minimum_score = numpy.min(scores)
        indices = numpy.where(scores == minimum_score)
        assert len(indices) > 0  # Min was from the list, so there must be at least one
        match_index = indices[0].tolist()[0]
        best_match = descriptors[match_index]

        if self._data_model.get_display_auto_select_results():
            console.message(f"Target {target_exposure:.1f}s at {target_temperature:.1f} C,"
                            f" best match is {best_match.get_exposure():.1f}s at"
                            f" {best_match.get_temperature():.1f} C: "
                            f"{best_match.get_name()}", +1, temp=True)

        return best_match


    # Get a small text tag about calibration to include in the FITs file comment

    def fits_comment_tag(self) -> str:
        calibration_type = self._data_model.get_precalibration_type()
        if calibration_type == Constants.CALIBRATION_NONE:
            return "(no calibration)"
        elif calibration_type == Constants.CALIBRATION_AUTO_DIRECTORY:
            return "(auto-selected bias file calibration)"
        elif calibration_type == Constants.CALIBRATION_PEDESTAL:
            return f"(pedestal {self._data_model.get_precalibration_pedestal()} calibration)"
        elif calibration_type == Constants.CALIBRATION_FIXED_FILE:
            return "(fixed bias file calibration)"

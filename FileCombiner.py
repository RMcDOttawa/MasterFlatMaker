#
#   Object for combining FITS files using different algorithms
#
from itertools import groupby
from typing import Callable

import numpy
import mean_shift as ms

import MasterMakerExceptions
from Calibrator import Calibrator
from Console import Console
from Constants import Constants
from DataModel import DataModel
from FileDescriptor import FileDescriptor
from ImageMath import ImageMath
from RmFitsUtil import RmFitsUtil
from SessionController import SessionController
from SharedUtils import SharedUtils


class FileCombiner:

    def __init__(self, session_controller: SessionController,
                 file_moved_callback: Callable[[str], None]):
        """
        Initialize this object
        :param session_controller:      Controller the parent uses to control this subtask
        :param file_moved_callback:     Callback method to inform that we have moved a processed file
        """
        self.callback_method = file_moved_callback
        self._session_controller = session_controller
    
    def original_non_grouped_processing(self, selected_files: [FileDescriptor],
                                        data_model: DataModel,
                                        output_file: str,
                                        console: Console):
        """
        Process one set of files to a single output file.
        Output to the given path, if provided.  If not provided, prompt the user for it.
        :param selected_files:      List of descriptions of files to be combined
        :param data_model:          Data model that gives combination method and other options
        :param output_file:         Path for the combined output file
        :param console:             Re-directable console output object
        """
        console.push_level()
        console.message("Using single-file processing", +1)
        # We'll use the first file in the list as a sample for things like image size
        assert len(selected_files) > 0
        # Confirm that these are all flat frames, and can be combined (same binning and dimensions)
        if FileCombiner.all_compatible_sizes(selected_files):
            self.check_cancellation()
            if data_model.get_ignore_file_type() or FileCombiner.all_of_type(selected_files,
                                                                             FileDescriptor.FILE_TYPE_FLAT):
                # Get (most common) filter name in the set
                # What filter should we put in the metadata for the output file?
                filter_name = SharedUtils.most_common_filter_name(selected_files)

                # Do the combination
                self.combine_files(selected_files, data_model, filter_name, output_file, console)
                self.check_cancellation()
                # Files are combined.  Put away the inputs?
                # Return list of any that were moved, in case the UI needs to be adjusted
                substituted_folder_name = SharedUtils.substitute_date_time_filter_in_string(
                    data_model.get_disposition_subfolder_name())
                self.handle_input_files_disposition(data_model.get_input_file_disposition(),
                                                    substituted_folder_name,
                                                    selected_files, console)
            else:
                raise MasterMakerExceptions.NotAllFlatFrames
        else:
            raise MasterMakerExceptions.IncompatibleSizes
        console.message("Combining complete", 0)
        console.pop_level()

    def process_groups(self, data_model: DataModel,
                       selected_files: [FileDescriptor],
                       output_directory: str,
                       console: Console):
        """
        Process the given selected files in groups by size, exposure, or temperature (or any combination)
        Exceptions thrown:
            NoGroupOutputDirectory      Output directory does not exist and unable to create it
        :param data_model:          Data model specifying options for the current run
        :param selected_files:      List of descriptions of files to be grouped then processed
        :param output_directory:    Directory to contain output files from processed groups
        :param console:             Re-directable console output object
        """
        console.push_level()
        temperature_bandwidth = data_model.get_temperature_group_bandwidth()
        disposition_folder = data_model.get_disposition_subfolder_name()
        substituted_folder_name = SharedUtils.substitute_date_time_filter_in_string(disposition_folder)
        console.message("Process groups into output directory: " + output_directory, +1)
        if not SharedUtils.ensure_directory_exists(output_directory):
            raise MasterMakerExceptions.NoGroupOutputDirectory(output_directory)
        minimum_group_size = data_model.get_minimum_group_size() \
            if data_model.get_ignore_groups_fewer_than() else 0

        #  Process size groups, or all sizes if not grouping
        groups_by_size = self.get_groups_by_size(selected_files, data_model.get_group_by_size())
        group_by_size = data_model.get_group_by_size()
        group_by_temperature = data_model.get_group_by_temperature()
        group_by_filter = data_model.get_group_by_filter()
        for size_group in groups_by_size:
            self.check_cancellation()
            console.push_level()
            # Message about this group only if this grouping was requested
            if len(size_group) < minimum_group_size:
                if group_by_size:
                    console.message(f"Ignoring one size group: {len(size_group)} "
                                    f"files {size_group[0].get_size_key()}", +1)
            else:
                if group_by_size:
                    console.message(f"Processing one size group: {len(size_group)} "
                                    f"files {size_group[0].get_size_key()}", +1)
                # Within this size group, process temperature groups, or all temperatures if not grouping
                groups_by_temperature = \
                    self.get_groups_by_temperature(size_group,
                                                   data_model.get_group_by_temperature(),
                                                   temperature_bandwidth)
                for temperature_group in groups_by_temperature:
                    self.check_cancellation()
                    console.push_level()
                    (_, mean_temperature) = ImageMath.mean_exposure_and_temperature(
                        temperature_group)
                    if len(temperature_group) < minimum_group_size:
                        if group_by_temperature:
                            console.message(f"Ignoring one temperature group: {len(temperature_group)} "
                                            f"files with mean temperature {mean_temperature:.1f}", +1)
                    else:
                        if group_by_temperature:
                            console.message(f"Processing one temperature group: {len(temperature_group)} "
                                            f"files with mean temperature {mean_temperature:.1f}", +1)
                        # Within this temperature group, process filter groups, or all filters if not grouping
                        groups_by_filter = \
                            self.get_groups_by_filter(temperature_group,
                                                      data_model.get_group_by_filter())
                        for filter_group in groups_by_filter:
                            self.check_cancellation()
                            console.push_level()
                            filter_name = filter_group[0].get_filter_name()
                            if len(filter_group) < minimum_group_size:
                                if group_by_filter:
                                    console.message(f"Ignoring one filter group: {len(filter_group)} "
                                                    f"files with {filter_name} filter ", +1)
                            else:
                                if group_by_filter:
                                    console.message(f"Processing one filter group: {len(filter_group)} "
                                                    f"files with {filter_name} filter ", +1)
                                self.process_one_group(data_model, filter_group,
                                                       output_directory,
                                                       data_model.get_master_combine_method(),
                                                       substituted_folder_name,
                                                       console)
                            console.pop_level()
                        self.check_cancellation()
                    console.pop_level()
            console.pop_level()
        console.message("Group combining complete", 0)
        console.pop_level()


    def process_one_group(self,
                          data_model: DataModel,
                          descriptor_list: [FileDescriptor],
                          output_directory: str,
                          combine_method: int,
                          disposition_folder_name,
                          console: Console):
        """
        Process one group of files, output to the given directory
        Exceptions thrown:
            NotAllFlatFrames        The given files are not all flat frames
            IncompatibleSizes       The given files are not all the same dimensions

        :param data_model:                  Data model giving options for current run
        :param descriptor_list:             List of all the files in one group, for processing
        :param output_directory:            Path to directory to receive the output file
        :param combine_method:              Code saying how these files should be combined
        :param disposition_folder_name:     If files to be moved after processing, name of receiving folder
        :param console:                     Re-directable console output object
        """
        assert len(descriptor_list) > 0
        sample_file: FileDescriptor = descriptor_list[0]
        console.push_level()
        self.describe_group(data_model, len(descriptor_list), sample_file, console)

        # Make up a file name for this group's output, into the given directory
        file_name = SharedUtils.get_file_name_portion(combine_method, sample_file,
                                                      data_model.get_sigma_clip_threshold(),
                                                      data_model.get_min_max_number_clipped_per_end())
        output_file = f"{output_directory}/{file_name}"

        # Confirm that these are all flat frames, and can be combined (same binning and dimensions)
        if self.all_compatible_sizes(descriptor_list):
            if data_model.get_ignore_file_type() \
                    or FileCombiner.all_of_type(descriptor_list, FileDescriptor.FILE_TYPE_FLAT):
                # Get (most common) filter name in the set
                # Get filter name to go in the output FITS metadata.
                # All the files should be the same filter, but in case there are stragglers,
                # get the most common filter from the set
                filter_name = SharedUtils.most_common_filter_name(descriptor_list)

                # Do the combination
                self.combine_files(descriptor_list, data_model, filter_name, output_file, console)
                self.check_cancellation()
                # Files are combined.  Put away the inputs?
                # Return list of any that were moved, in case the UI needs to be adjusted
                self.handle_input_files_disposition(data_model.get_input_file_disposition(),
                                                    disposition_folder_name,
                                                    descriptor_list, console)
                self.check_cancellation()
            else:
                raise MasterMakerExceptions.NotAllFlatFrames
        else:
            raise MasterMakerExceptions.IncompatibleSizes

        console.pop_level()

    def handle_input_files_disposition(self,
                                       disposition_type: int,
                                       sub_folder_name: str,
                                       descriptors: [FileDescriptor],
                                       console: Console):
        """
        Move the given files if the given disposition type requests it.
        Return a list of any files that were moved so the UI can be adjusted if necessary

        :param disposition_type:        Code for what to do with file after processing
        :param sub_folder_name:         Where to put file if we're moving it
        :param descriptors:             List of files for potential processing
        :param console:                 Redirectable console output option
        """
        if disposition_type == Constants.INPUT_DISPOSITION_NOTHING:
            # User doesn't want us to do anything with the input files
            return
        else:
            assert (disposition_type == Constants.INPUT_DISPOSITION_SUBFOLDER)
            console.message("Moving processed files to " + sub_folder_name, 0)
            # User wants us to move the input files into a sub-folder
            for descriptor in descriptors:
                if SharedUtils.dispose_one_file_to_sub_folder(descriptor, sub_folder_name):
                    # Successfully moved the file;  tell the user interface
                    self.callback_method(descriptor.get_absolute_path())

    @classmethod
    def all_of_type(cls,
                    selected_files: [FileDescriptor],
                    type_code: int) -> bool:
        """
        Determine if all the files in the list are of the given type

        :param selected_files:  List of files to be checked
        :param type_code:       Type code files are to be tested against
        :return:                True if all files in list are of given type
        """
        for descriptor in selected_files:
            if descriptor.get_type() != type_code:
                return False
        return True

    @classmethod
    def all_compatible_sizes(cls,
                             selected_files: [FileDescriptor]) -> bool:
        """
        Confirm that the given list of files are combinable by being compatible sizes
        This means their x,y dimensions are the same and their binning is the same
        :param selected_files:  List of files (FileDescriptors) to be checked for combinability
        :return:                True if all files are compatible
        """
        if len(selected_files) == 0:
            return True
        (x_dimension, y_dimension) = selected_files[0].get_dimensions()
        binning = selected_files[0].get_binning()
        for descriptor in selected_files:
            (this_x, this_y) = descriptor.get_dimensions()
            if this_x != x_dimension or this_y != y_dimension or descriptor.get_binning() != binning:
                return False
        return True

    @staticmethod
    def all_same_filter(selected_files: [FileDescriptor]) -> bool:
        """
        Determine if all files in list use the same filter
        :param selected_files:      List of FileDescriptors of files to be tested
        :return:                    True if all use the same filter
        """
        if len(selected_files) == 0:
            return True
        filter_name = selected_files[0].get_filter_name()
        for descriptor in selected_files:
            if descriptor.get_filter_name() != filter_name:
                return False
        return True

    @classmethod
    def validate_file_dimensions(cls,
                                 descriptors: [FileDescriptor],
                                 data_model: DataModel) -> bool:
        """
        Determine if the dimensions of all the supplied files are the same.
        All selected files must be the same size and the same binning.
        Include the precalibration bias or dark file in this test if that method is selected.

        :param descriptors:     Files to be checked for compatibility
        :param data_model:      Data model gives precalibration type and file if needed
        :return:                True if all files are the same size and binning, so compatible
        """
        # Get list of paths of selected files
        if len(descriptors) > 0:

            # If precalibration file is in use, add that name to the list
            if data_model.get_precalibration_type() == Constants.CALIBRATION_FIXED_FILE:
                calibration_descriptor = \
                    RmFitsUtil.make_file_descriptor(data_model.get_precalibration_fixed_path())
                descriptors.append(calibration_descriptor)

            # Get binning and dimension of first to use as a reference
            assert len(descriptors) > 0
            reference_file: FileDescriptor = descriptors[0]
            reference_binning = reference_file.get_binning()
            reference_x_size = reference_file.get_x_dimension()
            reference_y_size = reference_file.get_y_dimension()

            # Check all files in the list against these specifications
            descriptor: FileDescriptor
            for descriptor in descriptors:
                if descriptor.get_binning() != reference_binning:
                    return False
                if descriptor.get_x_dimension() != reference_x_size:
                    return False
                if descriptor.get_y_dimension() != reference_y_size:
                    return False

        return True

    @staticmethod
    def get_groups_by_size(selected_files: [FileDescriptor],
                           is_grouped: bool) -> [[FileDescriptor]]:
        """
        Given list of file descriptors, return a list of lists, where each outer list is all the
        file descriptors with the same size (dimensions and binning).  If "is_grouped" is False,
        just return all the files in one group.

        :param selected_files:      List of files to be grouped
        :param is_grouped:          Flag whether size grouping is to be performed
        :return:                    List of lists - one outer list per size group
        """
        if is_grouped:
            descriptors_sorted = sorted(selected_files, key=FileDescriptor.get_size_key)
            descriptors_grouped = groupby(descriptors_sorted, FileDescriptor.get_size_key)
            result: [[FileDescriptor]] = []
            for key, sub_group in descriptors_grouped:
                sub_list = list(sub_group)
                result.append(sub_list)
            return result
        else:
            return [selected_files]   # One group with all the files


    @staticmethod
    def get_groups_by_filter(selected_files: [FileDescriptor],
                             is_grouped: bool) -> [[FileDescriptor]]:
        """
        Given list of file descriptors, return a list of lists, where each outer list is all the
        file descriptors with the same filter name (case insensitive).  If "is_grouped" is False,
        just return all the files in one group.

        :param selected_files:      List of files to be grouped
        :param is_grouped:          Flag whether size grouping is to be performed
        :return:                    List of lists - one outer list per filter group
        """
        if is_grouped:
            descriptors_sorted = sorted(selected_files, key=FileDescriptor.get_filter_name_lower)
            descriptors_grouped = groupby(descriptors_sorted, FileDescriptor.get_filter_name_lower)
            result: [[FileDescriptor]] = []
            for key, sub_group in descriptors_grouped:
                sub_list = list(sub_group)
                result.append(sub_list)
            return result
        else:
            return [selected_files]   # One group with all the files

    def get_groups_by_temperature(self,
                                  selected_files: [FileDescriptor],
                                  is_grouped: bool,
                                  bandwidth: float) -> [[FileDescriptor]]:
        """
        Given list of file descriptors, return a list of lists, where each outer list is all the
        file descriptors with the same temperature within a given tolerance
        Note that, because of the "tolerance" comparison, this is a clustering analysis, not
        a simple python "groupby", which assumes the values are exact.

        :param selected_files:      List of files to be grouped
        :param is_grouped:          Flag whether size grouping is to be performed
        :param bandwidth:           Bandwidth of sensitivity of clustering algorithm
        :return:                    List of lists - one outer list per temperature group
        """
        # For this simple 1-dimensional clustering we can use the MeanShift function from
        # the machine learning package, sklearn

        if is_grouped:
            # We'll get the indices of the temperature clusters, then use those indices
            # on the file descriptors
            temperatures: [float] = [file.get_temperature() for file in selected_files]
            result_array: [[FileDescriptor]] = self.cluster_descriptors_by_values(bandwidth,
                                                                                  temperatures,
                                                                                  selected_files)

            # The groups array is in arbitrary order - determined by the clustering algorithm
            # We'd like to have it in a predictable order.  Sort by first temperature in each group
            result_array.sort(key=lambda g: g[0].get_temperature())
            return result_array

        else:
            return [selected_files]   # One group with all the files

    @staticmethod
    def cluster_descriptors_by_values(bandwidth: float,
                                      cluster_values: [float],
                                      selected_files: [FileDescriptor]) -> [[FileDescriptor]]:
        """
        Cluster a list of file descriptors into groups by clustering given float values

        :param bandwidth:       Bandwidth of the cluster search algorithm
        :param cluster_values:  List of values (temperatures, exposure times, etc) to be clustered
        :param selected_files:  List of file descriptors corresponding to those values, also to be clustered
        :return:                Clusters as list of lists - one outer list per cluster-value group
        """
        result_array: [[FileDescriptor]] = []
        data_to_cluster = numpy.array(cluster_values).reshape(-1, 1)
        mean_shifter = ms.MeanShift()
        mean_shift_result = mean_shifter.cluster(data_to_cluster, kernel_bandwidth=bandwidth)
        arbitrary_cluster_labels = mean_shift_result.cluster_ids
        # cluster_labels is an array of integers, with each "cluster" having the same integer label
        unique_labels = numpy.unique(arbitrary_cluster_labels)
        # So if we gather the unique label values, that is gathering the clusters
        for label in unique_labels:
            # Flag the items in this cluster
            cluster_membership: [bool] = arbitrary_cluster_labels == label
            # Get the indices of the items in this cluster
            member_indices: [int] = numpy.where(cluster_membership)[0].tolist()
            # Get the descriptors in this cluster and add to the output array
            this_cluster_descriptors: [FileDescriptor] = [selected_files[i] for i in member_indices]
            result_array.append(this_cluster_descriptors)
        return result_array

    # Following is the original version of this method, that used the sklearn.cluster package
    # version of MeanShift.  I stopped using this, and used the Matt Nedrich version of mean_shift
    # instead, because I couldn't get the sklearn-based system to package to a Windows executable
    # with pyinstaller. There is a known problem with sklearn and pyinstaller - it has hidden dependencies
    # with a multiprocessing windows dll that don't resolve properly.
    # @staticmethod
    # def cluster_descriptors_by_values(bandwidth, cluster_values, selected_files):
    #     result_array: [[FileDescriptor]] = []
    #     data_to_cluster = numpy.array(cluster_values).reshape(-1, 1)
    #     mean_shift = MeanShift(bandwidth=bandwidth)
    #     mean_shift.fit(data_to_cluster)
    #     arbitrary_cluster_labels = mean_shift.labels_
    #     # cluster_labels is an array of integers, with each "cluster" having the same integer label
    #     unique_labels = numpy.unique(arbitrary_cluster_labels)
    #     # So if we gather the unique label values, that is gathering the clusters
    #     for label in unique_labels:
    #         # Flag the items in this cluster
    #         cluster_membership: [bool] = arbitrary_cluster_labels == label
    #         # Get the indices of the items in this cluster
    #         member_indices: [int] = numpy.where(cluster_membership)[0].tolist()
    #         # Get the descriptors in this cluster and add to the output array
    #         this_cluster_descriptors: [FileDescriptor] = [selected_files[i] for i in member_indices]
    #         result_array.append(this_cluster_descriptors)
    #     return result_array

    #----------------------------------------

    def combine_files(self, input_files: [FileDescriptor],
                      data_model: DataModel,
                      filter_name: str,
                      output_path: str,
                      console: Console):
        """
        Combine the given files, output to the given output file using the combination
        method defined in the data model.

        :param input_files:     List of files to be combined
        :param data_model:      Data model with options for this run
        :param filter_name:     Human-readable filter name (for output file name and FITS comment)
        :param output_path:     Path for output fiel to be created
        :param console:         Redirectable console output object
        """
        console.push_level()    # Stack console indentation level to easily restore when done
        substituted_file_name = SharedUtils.substitute_date_time_filter_in_string(output_path)
        file_names = [d.get_absolute_path() for d in input_files]
        combine_method = data_model.get_master_combine_method()
        # Get info about any precalibration that is to be done
        calibrator = Calibrator(data_model)
        calibration_tag = calibrator.fits_comment_tag()
        assert len(input_files) > 0
        binning: int = input_files[0].get_binning()
        (mean_exposure, mean_temperature) = ImageMath.mean_exposure_and_temperature(input_files)
        if combine_method == Constants.COMBINE_MEAN:
            mean_data = ImageMath.combine_mean(file_names, calibrator, console, self._session_controller)
            self.check_cancellation()
            RmFitsUtil.create_combined_fits_file(substituted_file_name, mean_data,
                                                 FileDescriptor.FILE_TYPE_FLAT,
                                                 "Flat Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 f"Master Flat MEAN combined {calibration_tag}")
        elif combine_method == Constants.COMBINE_MEDIAN:
            median_data = ImageMath.combine_median(file_names, calibrator, console, self._session_controller)
            self.check_cancellation()
            RmFitsUtil.create_combined_fits_file(substituted_file_name, median_data,
                                                 FileDescriptor.FILE_TYPE_FLAT,
                                                 "Flat Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 f"Master Flat MEDIAN combined {calibration_tag}")
        elif combine_method == Constants.COMBINE_MINMAX:
            number_dropped_points = data_model.get_min_max_number_clipped_per_end()
            min_max_clipped_mean = ImageMath.combine_min_max_clip(file_names, number_dropped_points,
                                                                  calibrator, console,
                                                                  self._session_controller)
            self.check_cancellation()
            assert min_max_clipped_mean is not None
            RmFitsUtil.create_combined_fits_file(substituted_file_name, min_max_clipped_mean,
                                                 FileDescriptor.FILE_TYPE_FLAT,
                                                 "Flat Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 f"Master Flat Min/Max Clipped "
                                                 f"(drop {number_dropped_points}) Mean combined"
                                                 f" {calibration_tag}")
        else:
            assert combine_method == Constants.COMBINE_SIGMA_CLIP
            sigma_threshold = data_model.get_sigma_clip_threshold()
            sigma_clipped_mean = ImageMath.combine_sigma_clip(file_names, sigma_threshold,
                                                              calibrator, console, self._session_controller)
            self.check_cancellation()
            assert sigma_clipped_mean is not None
            RmFitsUtil.create_combined_fits_file(substituted_file_name, sigma_clipped_mean,
                                                 FileDescriptor.FILE_TYPE_FLAT,
                                                 "Flat Frame",
                                                 mean_exposure, mean_temperature, filter_name, binning,
                                                 f"Master Flat Sigma Clipped "
                                                 f"(threshold {sigma_threshold}) Mean combined"
                                                 f" {calibration_tag}")
        console.pop_level()

    @staticmethod
    def describe_group(data_model: DataModel,
                       number_files: int,
                       sample_file: FileDescriptor,
                       console: Console):
        """
        Display, on the console, a descriptive text string for the group being processed, using a given sample file
        :param data_model:      Data model giving the processing options
        :param number_files:    Number of files in the group being processed
        :param sample_file:     Sample file, representative of the characterstics of files in the group
        :param console:         Redirectable output console
        """
        binning = sample_file.get_binning()
        temperature = sample_file.get_temperature()
        message_parts: [str] = []
        if data_model.get_group_by_size():
            message_parts.append(f"binned {binning} x {binning}")
        if data_model.get_group_by_filter():
            message_parts.append(f"with {sample_file.get_filter_name()} filter")
        if data_model.get_group_by_temperature():
            message_parts.append(f"at {temperature} degrees")
        processing_message = ", ".join(message_parts)
        console.message(f"Processing {number_files} files {processing_message}.", +1)

    def check_cancellation(self):
        """
        Check back with the parent of this subtask to see if we have been cancelled.
        Raise a "cancelled" exception if so.
        """
        if self._session_controller.thread_cancelled():
            raise MasterMakerExceptions.SessionCancelled

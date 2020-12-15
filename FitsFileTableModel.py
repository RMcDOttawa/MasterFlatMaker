from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant
from PyQt5.QtWidgets import QTableView

from FileDescriptor import FileDescriptor


#   Model for the file table shown on the main UI.  The table consists of one row per file
#   identified in the "open" dialog, and the user will select the rows in the table that
#   are to be processed.

#   Columns in the table are:
#       0:  Name            Name of the file
#       1:  Type            Image type (Dark, Light, Bias, Flat, Unknown)
#       2:  Filter          Name of filter used for this frame
#       3:  Dimensions      Width, Height of image in pixels
#       4:  Binning         The binning value (1x1, 2x2, etc., or Unknown)
#       5:  Filter          Name of filter if light or flat frame
#       6:  Exposure        Exposure time of frame in seconds


class FitsFileTableModel(QAbstractTableModel):
    headings = ["Name", "Type", "Filter", "Dimensions", "Binning", "Exp.", "Temp.", "Avg ADUs"]

    def __init__(self, table: QTableView, ignore_file_type: bool, display_average_adus: bool):
        """
        Constructor for empty fits file table model
        :param table:                   The table view for which this is the data model
        :param ignore_file_type:        Flag whether file types are being ignored
        :param display_average_adus:    Flag whether the "display ADUs" option is on
        """
        QAbstractTableModel.__init__(self)
        self._files_list: [FileDescriptor] = []
        self._ignore_file_type = ignore_file_type
        self._table = table
        self._display_average_adus = display_average_adus

    def set_ignore_file_type(self, ignore: bool):
        self._ignore_file_type = ignore

    def get_file_descriptors(self) -> [FileDescriptor]:
        return self._files_list

    def set_file_descriptors(self, file_descriptors: [FileDescriptor]):
        self.beginResetModel()
        self._files_list = file_descriptors
        self.endResetModel()

    # noinspection PyMethodOverriding
    def rowCount(self, parent: QModelIndex) -> int:
        """
        Return how many rows (not including the header row) to display.  Called internally
        by the table management code, not expected to be called by program code, though it can be.
        :param parent:  QmodelIndex value, ignored for this simple table
        :return:        Number of rows, not including header row - i.e. number of data rows
        """
        return len(self._files_list)

    # noinspection PyMethodOverriding
    def columnCount(self, parent: QModelIndex) -> int:
        """
        Return how many columns to display.  ONe per data column, possibly including the ADU values
        :param parent:
        :return:
        """
        return len(self.headings) if self._display_average_adus else len(self.headings) - 1

    # noinspection PyMethodOverriding
    def data(self, index: QModelIndex, role: Qt.DisplayRole):
        """
        Get data element to display in a table cell
        :param index:   Row and column of the cell in question
        :param role:    Type of operation for which this value is being retrieved
        :return:        String to be displayed
        """
        row_index: int = index.row()
        column_index: int = index.column()
        if role == Qt.DisplayRole:
            descriptor = self._files_list[row_index]
            if column_index == 0:
                result = descriptor.get_name()
            elif column_index == 1:
                result = descriptor.get_type_name()
            elif column_index == 2:
                result = descriptor.get_filter_name()
            elif column_index == 3:
                (x_size, y_size) = descriptor.get_dimensions()
                result = f"{x_size} x {y_size}"
            elif column_index == 4:
                binning = descriptor.get_binning()
                result = f"{binning} x {binning}"
            elif column_index == 5:
                result = f"{descriptor.get_exposure():.3f}"
            elif column_index == 6:
                result = str(descriptor.get_temperature())
            elif column_index == 7:
                result = f"{descriptor.get_average_adus():,}"
            else:
                result = f"<{row_index},{column_index}>"
        # elif role == Qt.FontRole:
        # elif role == Qt.BackgroundRole:
        else:
            result = QVariant()
        return result

    # noinspection PyMethodOverriding
    def headerData(self, item_number, orientation, role):
        """
        Return the value to be displayed as a header over a given column
        :param item_number:     Column number
        :param orientation:     Table header orientation (only Horizontal is used)
        :param role:            Function asking - only Display is used
        :return:                Header for the specified column
        """
        result = QVariant()
        if (role == Qt.DisplayRole) and (orientation == Qt.Horizontal):
            if 0 <= item_number < len(self.headings):
                return self.headings[item_number]
            else:
                return f"Head-{item_number}"
        # elif (role == Qt.DisplayRole) and (orientation == Qt.Vertical):
        # elif (role == Qt.FontRole) and (orientation == Qt.Vertical):
        # elif (role == Qt.FontRole) and (orientation == Qt.Horizontal):
        return result

    # noinspection PyMethodOverriding
    def sort(self, column_index: int, sort_order: int):
        """
        Sort the stored table data rows in response to a column being clicked.
        Any selected rows are un-selected.
        :param column_index:    Column on which to sort the rows
        :param sort_order:      Sort ascending or descending?
        """
        self.beginResetModel()
        reverse_flag = sort_order == Qt.DescendingOrder
        if column_index == 0:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_name,
                                      reverse=reverse_flag)
        elif column_index == 1:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_type_name,
                                      reverse=reverse_flag)
        elif column_index == 2:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_filter_name_lower,
                                      reverse=reverse_flag)
        elif column_index == 3:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_x_dimension,
                                      reverse=reverse_flag)
        elif column_index == 4:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_binning,
                                      reverse=reverse_flag)
        elif column_index == 5:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_exposure,
                                      reverse=reverse_flag)
        elif column_index == 6:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_temperature,
                                      reverse=reverse_flag)
        elif column_index == 7:
            self._files_list = sorted(self._files_list,
                                      key=FileDescriptor.get_average_adus,
                                      reverse=reverse_flag)
        self.endResetModel()
        self._table.clearSelection()

    def flags(self, index: QModelIndex) -> int:
        """
        Filter row selection clicks so that we only allow the selection of files that are known to be FLAT frames.
        Or, if the "ignore file type" flag is on, then we allow the selection of any files
        :param index:   Row that has been clicked, potentially to be selected
        :return:        Option bits indicating if item is selectable
        """
        selectable_option: int
        if self._ignore_file_type:
            # We're ignoring internal FITS file type, so all rows are selectable
            selectable_option = Qt.ItemIsSelectable
        else:
            # We're honouring FITS file type, so we allow selection only of FLAT files
            row_index = index.row()
            descriptor = self._files_list[row_index]
            selectable_option = Qt.ItemIsSelectable if descriptor.get_type() == FileDescriptor.FILE_TYPE_FLAT else 0
        return selectable_option | Qt.ItemIsEnabled

    def clear_table(self):
        """
        Clear all the data from the table - delete all rows
        """
        self.beginResetModel()
        self._files_list = []
        self.endResetModel()

    def remove_files(self, descriptors: [FileDescriptor]):
        """
        Remove the given files (by name) from the table (probably because we have moved them
        so the file path is no longer valid)
        :param descriptors:     List of file descriptors to be removed
        """
        descriptor: FileDescriptor
        for descriptor in descriptors:
            name_to_remove = descriptor.get_name()
            # Find occurrence of this (there is only one) and remove that row
            for row_index in range(len(self._files_list)):
                if self._files_list[row_index].get_name() == name_to_remove:
                    model_index = self.createIndex(row_index, 0)
                    self.beginRemoveRows(model_index.parent(), row_index, row_index)
                    del self._files_list[row_index]
                    self.endRemoveRows()
                    break

    def remove_file_path(self, path_to_remove: str):
        """
        Find and remove the file descriptor with the given absolute path name
        :param path_to_remove:      Absolute path name of file to be removed
        :return:
        """
        # Get index in the list of this path
        for row_index, descriptor in enumerate(self._files_list):
            if descriptor.get_absolute_path() == path_to_remove:
                # Found it, remove this row from the table model, telling the UI to update
                model_index = self.createIndex(row_index, 0)
                self.beginRemoveRows(model_index.parent(), row_index, row_index)
                del self._files_list[row_index]
                self.endRemoveRows()
                break

    def adu_display_changed(self, display: bool):
        """
        Take note of the fact that the "display average adus" flag has changed, update appropriately
        :param display:     Display flag - being set to true or false
        """
        self.beginResetModel()
        self._display_average_adus = display
        self.endResetModel()



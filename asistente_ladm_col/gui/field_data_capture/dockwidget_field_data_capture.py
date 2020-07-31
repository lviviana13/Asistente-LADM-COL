# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              Asistente LADM-COL
                             --------------------
        begin                : 2020-07-22
        git sha              : :%H$
        copyright            : (C) 2020 by Germán Carrillo (SwissTierras Colombia)
        email                : gcarrillo@linuxmail.org
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License v3.0 as          *
 *   published by the Free Software Foundation.                            *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import (Qt,
                              QCoreApplication,
                              QObject,
                              pyqtSignal)
from qgis.core import Qgis
from qgis.gui import QgsDockWidget

from asistente_ladm_col.app_interface import AppInterface
from asistente_ladm_col.gui.field_data_capture.allocate_parcels_initial_panel import AllocateParcelsFieldDataCapturePanelWidget
from asistente_ladm_col.gui.field_data_capture.allocate_parcels_to_surveyor_panel import \
    AllocateParcelsToSurveyorPanelWidget
from asistente_ladm_col.gui.field_data_capture.configure_surveyors_panel import ConfigureSurveyorsPanelWidget
from asistente_ladm_col.utils import get_ui_class

from asistente_ladm_col.lib.logger import Logger
from asistente_ladm_col.utils.qt_utils import OverrideCursor

DOCKWIDGET_UI = get_ui_class('field_data_capture/dockwidget_field_data_capture.ui')


class DockWidgetFieldDataCapture(QgsDockWidget, DOCKWIDGET_UI):
    def __init__(self, iface, db, ladm_data, allocate_mode=True):
        super(DockWidgetFieldDataCapture, self).__init__(None)
        self.setupUi(self)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.logger = Logger()
        self.logger.clear_message_bar()  # Clear QGIS message bar

        self.controller = FieldDataCaptureController(iface, db, ladm_data)
        self.controller.field_data_capture_layer_removed.connect(self.layer_removed)

        # Configure panels
        self.configure_surveyors_panel = None
        self.lst_configure_surveyors_panel = list()

        self.allocate_parcels_to_surveyor_panel = None
        self.lst_allocate_parcels_to_surveyor_panel = list()

        if allocate_mode:
            self.allocate_panel = AllocateParcelsFieldDataCapturePanelWidget(self, self.controller)
            self.widget.setMainPanel(self.allocate_panel)
            self.add_layers()
            self.allocate_panel.fill_data()
        else:  # Synchronize mode
            # self.synchronize_panel = ChangesPerParcelPanelWidget(self, self.utils)
            # self.widget.setMainPanel(self.synchronize_panel)
            # self.lst_parcel_panels.append(self.synchronize_panel)
            pass

    def show_configure_surveyors_panel(self):
        with OverrideCursor(Qt.WaitCursor):
            if self.lst_configure_surveyors_panel:
                for panel in self.lst_configure_surveyors_panel:
                    try:
                        self.widget.closePanel(panel)
                    except RuntimeError as e:  # Panel in C++ could be already closed...
                        pass

                self.lst_configure_surveyors_panel = list()
                self.configure_surveyors_panel = None

            self.configure_surveyors_panel = ConfigureSurveyorsPanelWidget(self)
            self.widget.showPanel(self.configure_surveyors_panel)
            self.lst_configure_surveyors_panel.append(self.configure_surveyors_panel)

    def show_allocate_parcels_to_surveyor_panel(self):
        with OverrideCursor(Qt.WaitCursor):
            if self.lst_allocate_parcels_to_surveyor_panel:
                for panel in self.lst_allocate_parcels_to_surveyor_panel:
                    try:
                        self.widget.closePanel(panel)
                    except RuntimeError as e:  # Panel in C++ could be already closed...
                        pass

                self.lst_allocate_parcels_to_surveyor_panel = list()
                self.allocate_parcels_to_surveyor_panel = None

            self.allocate_parcels_to_surveyor_panel = AllocateParcelsToSurveyorPanelWidget(self)
            self.widget.showPanel(self.allocate_parcels_to_surveyor_panel)
            self.lst_allocate_parcels_to_surveyor_panel.append(self.allocate_parcels_to_surveyor_panel)

    def closeEvent(self, event):
        # Close here open signals in other panels (if needed)
        self.close_dock_widget()

    def add_layers(self):
        self.controller.add_layers()

    def layer_removed(self):
        self.logger.info_msg(__name__, QCoreApplication.translate("DockWidgetFieldDataCapture",
                                                                  "'Field data capture' has been closed because you just removed a required layer."))
        self.close_dock_widget()

    def update_db_connection(self, db, ladm_col_db, db_source):
        self.close_dock_widget()  # New DB: the user needs to use the menus again, which will start FDC from scratch

    def close_dock_widget(self):
        try:
            self.controller.field_data_capture_layer_removed.disconnect()  # disconnect layer signals
        except:
            pass

        self.close()  # The user needs to use the menus again, which will start everything from scratch

    def initialize_layers(self):
        self.controller.initialize_layers()


class FieldDataCaptureController(QObject):

    field_data_capture_layer_removed = pyqtSignal()

    def __init__(self, iface, db, ladm_data):
        QObject.__init__(self)
        self.iface = iface
        self._db = db
        self.ladm_data = ladm_data

        self.app = AppInterface()

        self._layers = dict()
        self.initialize_layers()

        self.allocated_parcels = dict()  # {t_id: {parcel_number: t_id_surveyor}}

    def initialize_layers(self):
        self._layers = {
            self._db.names.FDC_PLOT_T: None,
            self._db.names.FDC_PARCEL_T: None,
            self._db.names.FDC_SURVEYOR_T: None
        }

    def add_layers(self):
        # We can pick any required layer, if it is None, no prior load has been done, otherwise skip...
        if self._layers[self._db.names.FDC_PLOT_T] is None:
            self.app.gui.freeze_map(True)

            self.app.core.get_layers(self._db, self._layers, load=True, emit_map_freeze=False)
            if not self._layers:
                return None

            self.iface.setActiveLayer(self._layers[self._db.names.FDC_PLOT_T])
            self.iface.zoomToActiveLayer()

            self.app.gui.freeze_map(False)

            for layer_name in self._layers:
                if self._layers[layer_name]:  # Layer was loaded, listen to its removal so that we can react properly
                    try:
                        self._layers[layer_name].willBeDeleted.disconnect(self.field_data_capture_layer_removed)
                    except:
                        pass
                    self._layers[layer_name].willBeDeleted.connect(self.field_data_capture_layer_removed)

    def get_parcel_surveyor_data(self):
        for fid, parcel_number in self.ladm_data.get_fdc_parcel_data(self._db, self._layers[self._db.names.FDC_PARCEL_T]).items():
            self.allocated_parcels[fid] = (parcel_number, None)

        return self.allocated_parcels


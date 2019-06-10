# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              Asistente LADM_COL
                             --------------------
        begin                : 2019-05-16
        git sha              : :%H$
        copyright            : (C) 2019 by Germán Carrillo (BSF Swissphoto)
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
from functools import partial

import qgis

from qgis.PyQt.QtGui import QMouseEvent
from qgis.PyQt.QtCore import QCoreApplication, Qt, QEvent, QPoint
from qgis.PyQt.QtWidgets import QTableWidgetItem
from qgis.core import (QgsWkbTypes,
                       Qgis,
                       QgsMessageLog,
                       QgsFeature,
                       QgsFeatureRequest,
                       QgsExpression,
                       QgsRectangle)

from qgis.gui import QgsPanelWidget
from ...config.symbology import OFFICIAL_STYLE_GROUP
from asistente_ladm_col.config.general_config import (OFFICIAL_DB_PREFIX,
                                                      OFFICIAL_DB_SUFFIX,
                                                      PREFIX_LAYER_MODIFIERS,
                                                      SUFFIX_LAYER_MODIFIERS,
                                                      STYLE_GROUP_LAYER_MODIFIERS)
from asistente_ladm_col.config.table_mapping_config import (PARCEL_NUMBER_FIELD,
                                                            PARCEL_NUMBER_BEFORE_FIELD,
                                                            FMI_FIELD,
                                                            ID_FIELD, PARCEL_TABLE, PLOT_TABLE, UEBAUNIT_TABLE)
from asistente_ladm_col.utils import get_ui_class

WIDGET_UI = get_ui_class('change_detection/changes_per_parcel_panel_widget.ui')

class ChangesPerParcelPanelWidget(QgsPanelWidget, WIDGET_UI):
    def __init__(self, parent, utils, parcel_number=None):
        QgsPanelWidget.__init__(self, None)
        self.setupUi(self)
        self.parent = parent
        self.utils = utils

        self.setDockMode(True)

        self._current_official_substring = ""
        self._current_substring = ""

        self.parent.add_layers()
        self.fill_combos()

        # Set connections
        self.btn_alphanumeric_query.clicked.connect(self.alphanumeric_query)
        self.chk_show_all_plots.toggled.connect(self.show_all_plots)
        self.cbo_parcel_fields.currentIndexChanged.connect(self.field_search_updated)
        self.panelAccepted.connect(self.initialize_tools_and_layers)

        self.initialize_field_values_line_edit()
        self.initialize_tools_and_layers()

        if parcel_number is not None:
            self.txt_alphanumeric_query.setValue(parcel_number)
            self.search_data(parcel_number=parcel_number)

    def field_search_updated(self, index=None):
        self.initialize_field_values_line_edit()

    def initialize_field_values_line_edit(self):
        self.txt_alphanumeric_query.setLayer(self.parent._official_layers[PARCEL_TABLE]['layer'])
        idx = self.parent._official_layers[PARCEL_TABLE]['layer'].fields().indexOf(self.cbo_parcel_fields.currentData())
        self.txt_alphanumeric_query.setAttributeIndex(idx)

    def fill_combos(self):
        self.cbo_parcel_fields.clear()

        if self.parent._official_layers[PARCEL_TABLE]['layer'] is not None:
            self.cbo_parcel_fields.addItem(QCoreApplication.translate("DockWidgetChanges", "Parcel Number"), PARCEL_NUMBER_FIELD)
            self.cbo_parcel_fields.addItem(QCoreApplication.translate("DockWidgetChanges", "Previous Parcel Number"), PARCEL_NUMBER_BEFORE_FIELD)
            self.cbo_parcel_fields.addItem(QCoreApplication.translate("DockWidgetChanges", "Folio de Matrícula Inmobiliaria"), FMI_FIELD)
        else:
            self.parent.add_layers()

    def search_data(self, **kwargs):
        # TODO: optimize QgsFeatureRequest

        self.chk_show_all_plots.setEnabled(False)
        self.chk_show_all_plots.setChecked(True)

        self.initialize_tools_and_layers()

        # Get official parcel's t_id and get related plot(s)
        search_field = self.cbo_parcel_fields.currentData()
        search_value = list(kwargs.values())[0]

        official_parcels = [feature for feature in self.parent._official_layers[PARCEL_TABLE]['layer'].getFeatures(
                            "{}='{}'".format(search_field, search_value))]

        if len(official_parcels) > 1:
            # TODO: Show dialog to select only one
            pass
        elif len(official_parcels) == 0:
            print("No parcel found!", search_field, search_value)
            return

        self.fill_table({search_field: search_value})

        official_plot_t_ids = self.utils.ladm_data.get_plots_related_to_parcels(self.utils._official_db,
                                                                          [official_parcels[0][ID_FIELD]],
                                                                          field_name = ID_FIELD,
                                                                          plot_layer = self.parent._official_layers[PLOT_TABLE]['layer'],
                                                                          uebaunit_table = self.parent._official_layers[UEBAUNIT_TABLE]['layer'])

        print(official_plot_t_ids)

        if official_plot_t_ids:
            #self.qgis_utils.map_freeze_requested.emit(True)

            self._current_official_substring = "\"{}\" IN ('{}')".format(ID_FIELD, "','".join([str(t_id) for t_id in official_plot_t_ids]))
            #self._official_plot_layer.setSubsetString(self._current_official_substring)
            self.parent.request_zoom_to_features(self.parent._official_layers[PLOT_TABLE]['layer'], list(), official_plot_t_ids)
            #self.iface.zoomToActiveLayer()

            # Get parcel's t_id and get related plot(s)
            parcels = self.parent._layers[PARCEL_TABLE]['layer'].getFeatures("{}='{}'".format(search_field, search_value))
            parcel = QgsFeature()
            res = parcels.nextFeature(parcel)
            if res:
                plot_t_ids = self.utils.ladm_data.get_plots_related_to_parcels(self.utils._db,
                                                                         [parcel[ID_FIELD]],
                                                                         field_name=ID_FIELD,
                                                                         plot_layer=self.parent._layers[PLOT_TABLE]['layer'],
                                                                         uebaunit_table=None)
                self._current_substring = "{} IN ('{}')".format(ID_FIELD, "','".join([str(t_id) for t_id in plot_t_ids]))
                #self._plot_layer.setSubsetString(self._current_substring)

            self.utils.qgis_utils.activate_layer_requested.emit(self.parent._official_layers[PLOT_TABLE]['layer'])
            #self.qgis_utils.map_freeze_requested.emit(False)

            # Activate Swipe Tool and send mouse event
            self.parent.activate_mapswipe_tool()

            if res: # plot_t_ids found
                plots = self.utils.ladm_data.get_features_from_t_ids(self.parent._layers[PLOT_TABLE]['layer'], plot_t_ids, True)
                plots_extent = QgsRectangle()
                for plot in plots:
                    plots_extent.combineExtentWith(plot.geometry().boundingBox())

                print(plots_extent)
                coord_x = plots_extent.xMaximum() - (plots_extent.xMaximum() - plots_extent.xMinimum()) / 9
                coord_y = plots_extent.yMaximum() - (plots_extent.yMaximum() - plots_extent.yMinimum()) / 2

                coord_transform = self.utils.iface.mapCanvas().getCoordinateTransform()
                map_point = coord_transform.transform(coord_x, coord_y)
                widget_point = map_point.toQPointF().toPoint()
                global_point = self.utils.canvas.mapToGlobal(widget_point)

                print(coord_x, coord_y, global_point)
                #cursor = self.iface.mainWindow().cursor()
                #cursor.setPos(global_point.x(), global_point.y())

                self.utils.canvas.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, global_point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                # mc.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, gp, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
                self.utils.canvas.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, widget_point + QPoint(1,0), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
                # QApplication.processEvents()
                self.utils.canvas.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, widget_point + QPoint(1,0), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                # QApplication.processEvents()

                # Once the query is done, activate the checkbox to alternate all plots/only selected plot
                self.chk_show_all_plots.setEnabled(True)

    def fill_table(self, search_criterion):
        dict_collected_parcels = self.utils.ladm_data.get_parcel_data_to_compare_changes(self.utils._db, search_criterion)

        # Custom layer modifiers
        layer_modifiers = {
            PREFIX_LAYER_MODIFIERS: OFFICIAL_DB_PREFIX,
            SUFFIX_LAYER_MODIFIERS: OFFICIAL_DB_SUFFIX,
            STYLE_GROUP_LAYER_MODIFIERS: OFFICIAL_STYLE_GROUP
        }

        dict_official_parcels = self.utils.ladm_data.get_parcel_data_to_compare_changes(self.utils._official_db, search_criterion, layer_modifiers=layer_modifiers)

        collected_parcel_number = list(dict_collected_parcels.keys())[0]
        # Before calling fill_table we make sure we get one and only one parcel attrs dict
        collected_attrs = dict_collected_parcels[collected_parcel_number][0]
        del collected_attrs[ID_FIELD]  # Remove this line if ID_FIELD is somehow needed

        official_parcel_number = list(dict_official_parcels.keys())[0]
        official_attrs = dict_official_parcels[official_parcel_number][0] if dict_official_parcels else []

        self.tbl_changes_per_parcel.clearContents()
        self.tbl_changes_per_parcel.setRowCount(len(collected_attrs))  # t_id shouldn't be counted
        self.tbl_changes_per_parcel.setSortingEnabled(False)

        for row, (collected_field, collected_value) in enumerate(collected_attrs.items()):
            item = QTableWidgetItem(collected_field)
            # item.setData(Qt.UserRole, parcel_attrs[ID_FIELD])
            self.tbl_changes_per_parcel.setItem(row, 0, item)

            official_value = official_attrs[collected_field] if collected_field in official_attrs else ''

            item = QTableWidgetItem(official_value)
            #item.setData(Qt.UserRole, parcel_attrs[ID_FIELD])
            self.tbl_changes_per_parcel.setItem(row, 1, item)

            item = QTableWidgetItem(collected_value)
            # item.setData(Qt.UserRole, parcel_attrs[ID_FIELD])
            self.tbl_changes_per_parcel.setItem(row, 2, item)

            self.tbl_changes_per_parcel.setItem(row, 3, QTableWidgetItem())
            self.tbl_changes_per_parcel.item(row, 3).setBackground(Qt.green if official_value == collected_value else Qt.red)

        self.tbl_changes_per_parcel.setSortingEnabled(True)

    def alphanumeric_query(self):
        """
        Alphanumeric query
        """
        option = self.cbo_parcel_fields.currentData()
        query = self.txt_alphanumeric_query.value()
        if query:
            if option == FMI_FIELD:
                self.search_data(parcel_fmi=query)
            elif option == PARCEL_NUMBER_FIELD:
                self.search_data(parcel_number=query)
            else: # previous_parcel_number
                self.search_data(previous_parcel_number=query)

        else:
            self.utils.iface.messageBar().pushMessage("Asistente LADM_COL",
                QCoreApplication.translate("DockWidgetChanges", "First enter a query"))

    def show_all_plots(self, state):
        self.parent._official_layers[PLOT_TABLE]['layer'].setSubsetString(self._current_official_substring if not state else "")
        self.parent._layers[PLOT_TABLE]['layer'].setSubsetString(self._current_substring if not state else "")

    def initialize_tools_and_layers(self, panel=None):
        self.parent.deactivate_mapswipe_tool()
        self.show_all_plots(True)
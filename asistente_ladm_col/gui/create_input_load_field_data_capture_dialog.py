# -*- coding: utf-8 -*-
"""
/***************************************************************************
                              Asistente LADM_COL
                             --------------------
        begin                : 2019-04-11
        git sha              : :%H$
        copyright            : (C) 2019 by Jhon Galindo
        email                : jhonsigpjc@gmail.com
 ***************************************************************************/
/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License v3.0 as          *
 *   published by the Free Software Foundation.                            *
 *                                                                         *
 ***************************************************************************/
"""
import os
import stat
import processing

from qgis.PyQt.QtCore import QVariant

from asistente_ladm_col.utils.qt_utils import (make_file_selector,
                                               make_folder_selector)

from ..utils.qfield_utils import run_etl_model_input_load_data

from qgis.core import (QgsProject,
                       QgsField,
                       QgsVectorLayer,
                       QgsVectorLayerJoinInfo)

from ..config.table_mapping_config import (FDC_PARCEL,
                                           FDC_PARTY,
                                           FDC_RIGHT,
                                           FDC_ADMINISTRATIVE_SOURCE,
                                           FDC_RRRSOURCE,
                                           FDC_UEBAUNIT,
                                           FDC_PLOT, 
                                           FDC_SECTOR,
                                           FDC_VILLAGE,
                                           FDC_BLOCK,
                                           FDC_NEIGHBOURHOOD,
                                           FDC_BUILDING,
                                           FDC_VALUATION_BUILDING,
                                           FDC_BUILDING_UNIT_VALUATION_TABLE,
                                           FDC_BUILDING_UNIT_CADASTRE_TABLE)

from qgis.PyQt.QtCore import (Qt,
                              QSettings,
                              QCoreApplication,
                              QFile)
from qgis.PyQt.QtWidgets import (QDialog,
                                 QFileDialog,
                                 QSizePolicy,
                                 QGridLayout)
from qgis.core import (Qgis,
                       QgsMapLayerProxyModel,
                       QgsApplication,
                       QgsCoordinateReferenceSystem,
                       QgsWkbTypes)
from qgis.gui import QgsMessageBar

from ..config.help_strings import HelpStrings

from ..utils import get_ui_class

WIZARD_UI = get_ui_class('wiz_input_load_field_data_capture.ui')


class InputLoadFieldDataCaptureDialog(QDialog, WIZARD_UI):
    def __init__(self, iface, db, qgis_utils, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.iface = iface
        self.log = QgsApplication.messageLog()
        self._db = db
        self.qgis_utils = qgis_utils
        self.help_strings = HelpStrings()
        self.buttonBox.accepted.connect(self.accepted)

        self.btn_browse_file_r1.clicked.connect(
            make_file_selector(self.txt_file_path_r1, QCoreApplication.translate("DialogImportFromExcel",
                        "Select the Excel file with data in the intermediate structure"), 
                        QCoreApplication.translate("DialogImportFromExcel", 'Excel File (*.xlsx *.xls)')))

        self.btn_browse_file_gdb.clicked.connect(
                make_folder_selector(self.txt_file_path_gdb, title=QCoreApplication.translate(
                'SettingsDialog', 'Open Folder with GDB'), parent=None))

    def show_help(self):
        self.qgis_utils.show_help("create_points")

    def accepted(self):
        #self.load_r1()
        #self.mapping_fields_r1()
        self.load_gdb()
        self.mapping_fields_gbb()
        
    def load_r1(self):
        self.layer_r1 = QgsVectorLayer(self.txt_file_path_r1.text(), 'R1_IGAC', 'ogr')
        QgsProject.instance().addMapLayer(self.layer_r1)

        self.res_layers = self.qgis_utils.get_layers(self._db, {
            FDC_PARCEL: {'name': FDC_PARCEL, 'geometry': None},
            FDC_PARTY: {'name': FDC_PARTY, 'geometry': None},
            FDC_RIGHT: {'name': FDC_RIGHT, 'geometry': None},
            FDC_ADMINISTRATIVE_SOURCE: {'name': FDC_ADMINISTRATIVE_SOURCE, 'geometry': None},
            FDC_RRRSOURCE: {'name': FDC_RRRSOURCE, 'geometry': None},
            FDC_UEBAUNIT: {'name': FDC_UEBAUNIT, 'geometry': None}
        }, load=True)

    def load_gdb(self):
        gdb_path = self.txt_file_path_gdb.text()
        layer = QgsVectorLayer(gdb_path, 'layer name', 'ogr')
        info = layer.dataProvider().subLayers()

        root = QgsProject.instance().layerTreeRoot()
        gdb_group = root.addGroup("GDB")
        self.gdb_layer = []

        for data in info:
            vlayer = QgsVectorLayer(gdb_path + '|layername=' + data.split('!!::!!')[1], data.split('!!::!!')[1], 'ogr')
            self.gdb_layer.append(vlayer)
            QgsProject.instance().addMapLayer(vlayer, False)
            gdb_group.addLayer(vlayer)

        self.res_layers_gdb = self.qgis_utils.get_layers(self._db, {
            FDC_PLOT: {'name': FDC_PLOT, 'geometry': QgsWkbTypes.PolygonGeometry},
            FDC_SECTOR: {'name': FDC_SECTOR, 'geometry': None},
            FDC_VILLAGE: {'name': FDC_VILLAGE, 'geometry': None},
            FDC_NEIGHBOURHOOD: {'name': FDC_NEIGHBOURHOOD, 'geometry': None},
            FDC_BUILDING: {'name': FDC_BUILDING, 'geometry': QgsWkbTypes.PolygonGeometry},
            FDC_VALUATION_BUILDING: {'name': FDC_VALUATION_BUILDING, 'geometry': None},
            FDC_BUILDING_UNIT_VALUATION_TABLE: {'name': FDC_BUILDING_UNIT_VALUATION_TABLE, 'geometry': None},
            FDC_BUILDING_UNIT_CADASTRE_TABLE: {'name': FDC_BUILDING_UNIT_CADASTRE_TABLE, 'geometry': QgsWkbTypes.PolygonGeometry}
        }, load=True)

    def mapping_fields_r1(self):
        arreglo = [ FDC_PARCEL, FDC_PARTY, FDC_RIGHT, FDC_ADMINISTRATIVE_SOURCE, FDC_RRRSOURCE]
        for name in arreglo:
            if name == FDC_ADMINISTRATIVE_SOURCE:
                input_data = self.res_layers[FDC_RIGHT]
            else:
                if name == FDC_RRRSOURCE:
                    input_data = self.res_layers[FDC_ADMINISTRATIVE_SOURCE]
                    print (input_data.name())
                else:
                    input_data = self.layer_r1

            output_data = self.res_layers[name]
            run_etl_model_input_load_data(input_data, output_data, name, self.qgis_utils)
            print ("Ejecutando etl" + self.res_layers[name].name())

    def mapping_fields_gbb(self):

        rterreno = QgsProject.instance().mapLayersByName('R_TERRENO')[0].id()
        uterreno = QgsProject.instance().mapLayersByName('U_TERRENO')[0].id()
        rsector = QgsProject.instance().mapLayersByName('R_SECTOR')[0].id()
        usector = QgsProject.instance().mapLayersByName('U_SECTOR')[0].id()
        vereda = QgsProject.instance().mapLayersByName('R_VEREDA')[0].id()
        manzana = QgsProject.instance().mapLayersByName('U_MANZANA')[0].id()
        barrio = QgsProject.instance().mapLayersByName('U_BARRIO')[0].id()
        uconstruccion = QgsProject.instance().mapLayersByName('U_CONSTRUCCION')[0].id()
        rconstruccion = QgsProject.instance().mapLayersByName('R_CONSTRUCCION')[0].id()
        uunidad = QgsProject.instance().mapLayersByName('U_UNIDAD')[0].id()
        runidad = QgsProject.instance().mapLayersByName('R_UNIDAD')[0].id()

        arreglo = [ FDC_PLOT, FDC_SECTOR, FDC_VILLAGE, FDC_BLOCK, FDC_NEIGHBOURHOOD, FDC_BUILDING, FDC_VALUATION_BUILDING,
                    FDC_BUILDING_UNIT_VALUATION_TABLE, FDC_BUILDING_UNIT_CADASTRE_TABLE]
        for name in arreglo:
            if name == FDC_PLOT:
                input_data = [self.fix_polygon_layers(rterreno), self.fix_polygon_layers(uterreno)]
                output_data = self.res_layers_gdb[FDC_PLOT]
            elif name == FDC_SECTOR:
                input_data = [self.fix_polygon_layers(rsector), self.fix_polygon_layers(usector)]
                output_data = self.res_layers_gdb[FDC_SECTOR]
            if name == FDC_VILLAGE:
                input_data = [self.fix_polygon_layers(vereda)]
                output_data = self.res_layers_gdb[FDC_VILLAGE]
            if name == FDC_BLOCK:
                input_data = [self.fix_polygon_layers(manzana)]
                output_data = self.res_layers_gdb[FDC_VILLAGE]
            elif name == FDC_NEIGHBOURHOOD:
                input_data = [self.fix_polygon_layers(barrio)]
                output_data = self.res_layers_gdb[FDC_NEIGHBOURHOOD]
            elif name == FDC_BUILDING:
                input_data = [self.fix_polygon_layers(rconstruccion), self.fix_polygon_layers(uconstruccion)]
                output_data = self.res_layers_gdb[FDC_BUILDING]
            elif name == FDC_VALUATION_BUILDING:
                self.create_column(self.res_layers_gdb[FDC_VALUATION_BUILDING], 'Codigo')
                input_data = [self.fix_polygon_layers(rconstruccion), self.fix_polygon_layers(uconstruccion)]
                output_data = self.res_layers_gdb[FDC_VALUATION_BUILDING]
            elif name == FDC_BUILDING_UNIT_VALUATION_TABLE:
                self.join_layers(uunidad, self.res_layers_gdb[FDC_BUILDING], 'codigo', 'tipo')
                self.join_layers(runidad, self.res_layers_gdb[FDC_BUILDING], 'codigo', 'tipo')
                input_data = [self.fix_polygon_layers(uunidad), self.fix_polygon_layers(runidad)]
                output_data = self.res_layers_gdb[FDC_BUILDING_UNIT_VALUATION_TABLE]
            elif name == FDC_BUILDING_UNIT_CADASTRE_TABLE:
                input_data = [self.fix_polygon_layers(uunidad), self.fix_polygon_layers(runidad)]
                output_data = self.res_layers_gdb[FDC_BUILDING_UNIT_CADASTRE_TABLE]

            for data in input_data:
                run_etl_model_input_load_data(data, output_data, name, self.qgis_utils)
                print ("Ejecutado etl" + name)
            
    def fix_polygon_layers(self, layer):

        params = {'INPUT': layer, 'OUTPUT':'memory:'}
        multipart = processing.run("native:multiparttosingleparts", params)
        params = {'INPUT': multipart['OUTPUT'], 'OUTPUT':'memory:'}
        fix = processing.run("native:fixgeometries", params)

        return fix['OUTPUT']

    def create_column(self, layer, name):
        layer.dataProvider().addAttributes([QgsField(name, QVariant.String, "VARCHAR")])
        layer.updateFields()

    def join_layers(self, initial, target, join_name, target_name):
        joinObject = QgsVectorLayerJoinInfo()
        joinObject.setJoinLayerId(target.id())
        joinObject.setJoinFieldName(target_name)
        joinObject.setTargetFieldName(join_name)
        joinObject.setJoinLayer(target)
        print (initial)
        print (initial.name())
        initial.addJoin(joinObject)
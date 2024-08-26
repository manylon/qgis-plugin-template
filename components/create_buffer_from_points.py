# -*- coding: utf-8 -*-

import json
import os

import psycopg2
from processing.algs.qgis.QgisAlgorithm import QgisAlgorithm
from qgis.core import (
    QgsApplication,
    QgsAuthMethodConfig,
    QgsProcessingException,
    QgsProcessingParameterDatabaseSchema,
    QgsProcessingParameterDatabaseTable,
    QgsProcessingParameterNumber,
    QgsProcessingParameterProviderConnection,
    QgsProcessingParameterString,
    QgsProject,
    QgsProviderConnectionException,
    QgsProviderRegistry,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QIcon

pluginPath = os.path.split(os.path.dirname(__file__))[0]
# Opening JSON file
context = json.load(
    open(os.path.join(pluginPath, "components", "utils", "context.json"), "r")
)


class CreateBufferFromPoints(QgisAlgorithm):

    DATABASE = "DATABASE"
    SCHEMA = "SCHEMA"
    INPUT = "INPUT"
    BUFFER_SIZE = "BUFFER_SIZE"
    NEW_SCHEMA = "NEW_SCHEMA"
    NEW_LAYER = "NEW_LAYER"

    def icon(self):
        return QIcon(os.path.join(pluginPath, "icon", "create_buffer_from_points.svg"))

    def group(self):
        return self.tr(context["postgresql_tools"]["groupname"])

    def groupId(self):
        return self.tr(context["postgresql_tools"]["group_id"])

    def name(self):
        return self.tr(
            context["postgresql_tools"]["tools"]["create_buffer_from_points"]
        )

    def displayName(self):
        return self.tr(
            context["postgresql_tools"]["tools"]["create_buffer_from_points"]
        )

    def shortHelpString(self):
        # Read CSS file
        css_path = os.path.join(pluginPath, "help_pages", "styles.css")
        with open(css_path, "r") as css_file:
            css_read = css_file.read().replace("\r", "").replace("\n", "")

        # Read HTML file and embed CSS
        html_path = os.path.join(
            pluginPath, "help_pages", os.path.basename(__file__).replace(".py", ".html")
        )
        with open(html_path, "r") as html_file:
            html_read = (
                html_file.read()
                .replace("\r", "")
                .replace("\n", "")
                .replace(
                    """<link rel="stylesheet" href="styles.css">""",
                    f"<style> {css_read} </style>",
                )
            )

        return self.tr(html_read)

    def msg(self, var):
        return "Type:" + str(type(var)) + " repr: " + var.__str__()

    def __init__(self):
        super().__init__()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterProviderConnection(
                self.DATABASE, self.tr("Database (connection name)"), "postgres"
            )
        )

        self.addParameter(
            QgsProcessingParameterDatabaseSchema(
                self.SCHEMA,
                self.tr("Schema (schema name)"),
                defaultValue="public",
                connectionParameterName=self.DATABASE,
            )
        )

        self.addParameter(
            QgsProcessingParameterDatabaseTable(
                self.INPUT,
                self.tr("Input layer"),
                connectionParameterName=self.DATABASE,
                schemaParameterName=self.SCHEMA,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.BUFFER_SIZE,
                self.tr("Size of Buffer"),
                QgsProcessingParameterNumber.Double,
                1,
                False,
            )
        )

        self.addParameter(
            QgsProcessingParameterDatabaseSchema(
                self.NEW_SCHEMA,
                self.tr("Select new schema (schema name)"),
                defaultValue="",
                connectionParameterName=self.DATABASE,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterString(
                self.NEW_LAYER, self.tr("New layer name"), "", False, True
            )
        )

    def processAlgorithm(self, parameters, context, feedback, executing=True):
        connection_name = self.parameterAsConnectionName(
            parameters, self.DATABASE, context
        )
        if not connection_name:
            raise QgsProcessingException(self.tr("No connection specified"))

        # resolve connection details to uri
        try:
            uri = (
                QgsProviderRegistry.instance()
                .providerMetadata("postgres")
                .createConnection(connection_name)
                .uri()
            )
            authcfg = uri.split("authcfg=")[1]

            if authcfg:
                auth_manager = QgsApplication.authManager()
                conf = QgsAuthMethodConfig()
                auth_manager.loadAuthenticationConfig(authcfg, conf, True)
                if conf.id():
                    con_uri = f"""{uri.split('authcfg=')[0]} password={conf.config("password", "")} user={conf.config("username", "")}"""
        except QgsProviderConnectionException:
            raise QgsProcessingException(
                self.tr("Could not retrieve connection details for {}").format(
                    connection_name
                )
            )

        layer_name = self.parameterAsDatabaseTableName(parameters, self.INPUT, context)
        schema_name = self.parameterAsString(parameters, self.SCHEMA, context)
        buffer_size = self.parameterAsDouble(parameters, self.BUFFER_SIZE, context)
        new_schema_name = self.parameterAsString(parameters, self.NEW_SCHEMA, context)
        new_layer_name = self.parameterAsString(parameters, self.NEW_LAYER, context)

        if new_schema_name == "":
            new_schema_name = schema_name
        if new_layer_name == "":
            new_layer_name = layer_name + "_buffer"

        connection = psycopg2.connect(con_uri)
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    """
                    SELECT f_geometry_column as columnname, "type" as geomtype, srid
                    FROM geometry_columns
                    WHERE f_table_schema = %s AND f_table_name = %s;
                """,
                    (schema_name, layer_name),
                )
            except psycopg2.Error as e:
                raise QgsProcessingException(
                    self.tr(
                        "Failed to get geometry information from the layer\n" + str(e)
                    )
                )

            geom_info = cursor.fetchone()
            if geom_info[1] not in ("POINT", "MULTIPOINT"):
                raise QgsProcessingException(
                    self.tr("The layer geometry must be of type POINT or MULTIPOINT")
                )

            # Get the columns of the layer
            try:
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema=%s
                    AND table_name =%s
                    AND column_name != 'geom';
                    """,
                    (schema_name, layer_name),
                )
                columns_string = ",".join(
                    [f'"{column[0]}"' for column in cursor.fetchall()]
                )
            except psycopg2.Error as e:
                raise QgsProcessingException(
                    self.tr("Failed to get the columns of the layer\n" + str(e))
                )

            # Get the primary key column name
            try:
                cursor.execute(
                    f"""
                    SELECT a.attname
                    FROM   pg_index i
                    JOIN   pg_attribute a ON a.attrelid = i.indrelid
                                        AND a.attnum = ANY(i.indkey)
                    WHERE  i.indrelid = '{schema_name}.{layer_name}'::regclass
                    AND    i.indisprimary;
                    """
                )
                primary_key_column = cursor.fetchone()[0]
            except psycopg2.Error as e:
                raise QgsProcessingException(
                    self.tr(
                        "Failed to get the primary key column of the layer\n" + str(e)
                    )
                )

            # Create a table with the buffers and save it in a selected schema and name
            try:
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {new_schema_name}.{new_layer_name} AS (
                    SELECT {columns_string}, ST_Buffer(geom, %s) as geom
                    FROM {schema_name}.{layer_name}
                );

                ALTER TABLE {new_schema_name}.{new_layer_name} ADD PRIMARY KEY ({primary_key_column});
                """,
                    (buffer_size,),
                )
                connection.commit()
            except psycopg2.Error as e:
                raise QgsProcessingException(
                    self.tr("Failed to create the buffer table\n" + str(e))
                )

            # # Construct the URI for the layer
            layer_uri = (
                uri
                + f' sslmode=disable key=\'{primary_key_column}\' srid={geom_info[2]} type={geom_info[1]} table="{new_schema_name}"."{new_layer_name}" (geom)'
            )
            layer = QgsVectorLayer(layer_uri, layer_name, "postgres")

            # Check if the layer is valid
            if not layer.isValid():
                raise QgsProcessingException(
                    self.tr("Failed to load the layer from PostGIS")
                )

            # Add the layer to the QGIS project
            QgsProject.instance().addMapLayer(layer)
        return {}

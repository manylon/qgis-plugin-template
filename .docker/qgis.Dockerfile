# Use the official QGIS image as the base image
FROM qgis/qgis:release-3_36


COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Start qgis
CMD ["qgis"]

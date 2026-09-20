FROM quay.io/jupyter/pyspark-notebook:spark-3.5.3

USER root
RUN ln -s /usr/local/spark /opt/spark \
    && mkdir -p /usr/local/spark/work \
    && chown -R ${NB_UID}:${NB_GID} /usr/local/spark/work
COPY jars/hadoop-aws-3.3.4.jar /opt/spark/jars/
ADD --checksum=sha256:873fe7cf495126619997bec21c44de5d992544aea7e632fdc77adb1a0915bae5 https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar /opt/spark/jars/
RUN cp /opt/spark/jars/aws-java-sdk-bundle-1.12.262.jar /tmp/aws-java-sdk-bundle-1.12.262.jar \
    && chmod 644 /tmp/aws-java-sdk-bundle-1.12.262.jar \
    && mv /tmp/aws-java-sdk-bundle-1.12.262.jar /opt/spark/jars/aws-java-sdk-bundle-1.12.262.jar
COPY jars/wildfly-openssl-1.0.7.Final.jar /opt/spark/jars/
RUN pip install --no-cache-dir pymongo==4.9.2
ENV SPARK_DIST_CLASSPATH="/opt/spark/jars/*"
COPY spark/conf/metrics.properties /opt/spark/conf/metrics.properties
COPY spark-apps /opt/spark-apps

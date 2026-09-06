FROM quay.io/jupyter/pyspark-notebook:spark-3.5.3

USER root
RUN pip install --no-cache-dir delta-spark==3.2.0 boto3
COPY jars/hadoop-aws-3.3.4.jar /usr/local/spark/jars/
ADD --checksum=sha256:873fe7cf495126619997bec21c44de5d992544aea7e632fdc77adb1a0915bae5 https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar /usr/local/spark/jars/
COPY jars/wildfly-openssl-1.0.7.Final.jar /usr/local/spark/jars/
COPY spark/conf/metrics.properties /usr/local/spark/conf/metrics.properties
COPY spark/conf/spark-defaults.conf /usr/local/spark/conf/spark-defaults.conf
USER ${NB_UID}

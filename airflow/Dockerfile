FROM apache/airflow:2.10.5-python3.11

USER airflow

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
USER airflow

RUN pip install --no-cache-dir pyspark==3.5.3

ENV PATH="/home/airflow/.local/bin:${PATH}"

COPY jars/delta-spark_2.12-3.2.0.jar /opt/spark-jars/
COPY jars/delta-storage-3.2.0.jar /opt/spark-jars/
COPY jars/hadoop-aws-3.3.4.jar /opt/spark-jars/
ADD --checksum=sha256:873fe7cf495126619997bec21c44de5d992544aea7e632fdc77adb1a0915bae5 https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar /opt/spark-jars/
COPY jars/wildfly-openssl-1.0.7.Final.jar /opt/spark-jars/
COPY airflow/dags /opt/airflow/dags
COPY spark-apps /opt/spark-apps

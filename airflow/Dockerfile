FROM apache/airflow:2.10.5-python3.11

USER airflow

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
USER airflow

RUN pip install --no-cache-dir pyspark==3.5.3 pymongo==4.9.2

ENV PATH="/home/airflow/.local/bin:${PATH}"
ENV SPARK_DIST_CLASSPATH="/opt/spark-jars/*"

USER root
COPY jars/delta-spark_2.12-3.2.0.jar /opt/spark-jars/
COPY jars/delta-storage-3.2.0.jar /opt/spark-jars/
COPY jars/hadoop-aws-3.3.4.jar /opt/spark-jars/
ADD --checksum=sha256:873fe7cf495126619997bec21c44de5d992544aea7e632fdc77adb1a0915bae5 https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar /opt/spark-jars/
RUN cp /opt/spark-jars/aws-java-sdk-bundle-1.12.262.jar /tmp/aws-java-sdk-bundle-1.12.262.jar \
    && chmod 644 /tmp/aws-java-sdk-bundle-1.12.262.jar \
    && mv /tmp/aws-java-sdk-bundle-1.12.262.jar /opt/spark-jars/aws-java-sdk-bundle-1.12.262.jar
COPY jars/wildfly-openssl-1.0.7.Final.jar /opt/spark-jars/
ADD --checksum=sha256:d1ed3f1296827a94299e521576339e496e8cb38d746961e2404cabbfddfdf3a2 https://repo1.maven.org/maven2/org/mongodb/spark/mongo-spark-connector_2.12/10.4.1/mongo-spark-connector_2.12-10.4.1.jar /opt/spark-jars/
ADD --checksum=sha256:618d2ed8d00d2cb9df34ab120562438d027c714800fa48369a4d587b5f0d3d1d https://repo1.maven.org/maven2/org/mongodb/mongodb-driver-sync/5.1.1/mongodb-driver-sync-5.1.1.jar /opt/spark-jars/
ADD --checksum=sha256:6c9e7b79bde8263a48bed1e35d2f00a819095b838a6ebda11ef45c6a303738ef https://repo1.maven.org/maven2/org/mongodb/mongodb-driver-core/5.1.1/mongodb-driver-core-5.1.1.jar /opt/spark-jars/
ADD --checksum=sha256:f11c740042f5c635f42dce186c6c02cbf97f7d0a5a7f6f14b7d0a808175d03ec https://repo1.maven.org/maven2/org/mongodb/bson/5.1.1/bson-5.1.1.jar /opt/spark-jars/
RUN chmod 644 /opt/spark-jars/mongo-spark-connector_2.12-10.4.1.jar \
    /opt/spark-jars/mongodb-driver-sync-5.1.1.jar \
    /opt/spark-jars/mongodb-driver-core-5.1.1.jar \
    /opt/spark-jars/bson-5.1.1.jar
# Decorator dependencies (LLM clients) live in their own venv so they cannot
# conflict with Airflow's pinned packages. Embeddings come from embedding-api.
RUN python -m venv /opt/decorators-venv \
    && /opt/decorators-venv/bin/pip install --no-cache-dir \
        pyspark==3.5.3 pandas pyarrow numpy grpcio grpcio-status googleapis-common-protos requests \
        llm-summary==0.6.1 llm-ner-nel==0.6.1 \
    && chown -R airflow /opt/decorators-venv
COPY lakehouse_data/src /opt/lakehouse_data/src
COPY airflow/dags /opt/airflow/dags
COPY spark-apps /opt/spark-apps
USER airflow

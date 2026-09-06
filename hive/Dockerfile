FROM apache/hive:3.1.3

USER root
COPY jars/postgresql-42.7.4.jar /opt/hive/lib/
COPY jars/hadoop-aws-3.1.0.jar /opt/hive/lib/
ADD --checksum=sha256:faf78ac4880f56cf52791d84ec1068ce7c66acc4295d580a726104b734c01fcd https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.271/aws-java-sdk-bundle-1.11.271.jar /opt/hive/lib/
COPY jars/wildfly-openssl-1.0.7.Final.jar /opt/hive/lib/
RUN cp /opt/hive/lib/hadoop-aws-3.1.0.jar /opt/hadoop/share/hadoop/common/lib/ \
    && cp /opt/hive/lib/aws-java-sdk-bundle-1.11.271.jar /opt/hadoop/share/hadoop/common/lib/ \
    && cp /opt/hive/lib/wildfly-openssl-1.0.7.Final.jar /opt/hadoop/share/hadoop/common/lib/
COPY hive/core-site.xml /opt/hive/conf/core-site.xml
COPY hive/core-site.xml /opt/hadoop/etc/hadoop/core-site.xml

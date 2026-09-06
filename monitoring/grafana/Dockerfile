FROM grafana/grafana:11.4.0

USER root
RUN mkdir -p /usr/share/grafana/plugins \
    && grafana cli --pluginsDir /usr/share/grafana/plugins plugins install trino-datasource
USER grafana

COPY monitoring/grafana/provisioning /etc/grafana/provisioning
COPY monitoring/grafana/dashboards /etc/grafana/dashboards

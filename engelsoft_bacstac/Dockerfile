# Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on.
# The Home Assistant BuildKit workflow expects the Dockerfile to be the
# single source of truth. This base image provides a multi-platform manifest.
FROM ghcr.io/hassio-addons/base-python:14.0.1

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION="Engelsoft BACstac for Home Assistant"
ARG BUILD_NAME="Engelsoft BACstac"
ARG BUILD_REF
ARG BUILD_VERSION="dev"
ENV BACSTAC_VERSION=${BUILD_VERSION}

# Install requirements for add-on
WORKDIR /usr/src
COPY requirements.txt ./requirements.txt
RUN \
  apk add --no-cache \
    nginx \
    python3 \
    py3-pip \
    py3-setuptools \
    py3-wheel \
  && pip3 install --no-cache-dir -r requirements.txt

WORKDIR /

COPY rootfs /

# Keep s6 service entry points executable even when the source tree was
# prepared on a filesystem that does not preserve Unix mode bits.
RUN chmod 0755 \
    /etc/s6-overlay/s6-rc.d/init-interface/run \
    /etc/s6-overlay/s6-rc.d/init-nginx/run \
    /etc/s6-overlay/s6-rc.d/interface/run \
    /etc/s6-overlay/s6-rc.d/interface/finish \
    /etc/s6-overlay/s6-rc.d/nginx/run \
    /etc/s6-overlay/s6-rc.d/nginx/finish

LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="app" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="engelsofta" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Engelsoft" \
    org.opencontainers.image.authors="engelsofta" \
    org.opencontainers.image.licenses="Apache-2.0" \
    org.opencontainers.image.url="https://github.com/engelsofta/engelsoft-bacstac-ha-addon" \
    org.opencontainers.image.source="https://github.com/engelsofta/engelsoft-bacstac-ha-addon" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

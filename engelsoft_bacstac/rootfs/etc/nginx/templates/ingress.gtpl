# Modified by engelsofta in 2026; derived from the Bepacom BACnet/IP add-on.
server {
    # Internal API/WebSocket endpoint used by Engelsoft Beacon BACnet/IP.
    listen 8099;

    allow 172.30.32.0/24;
    allow 127.0.0.0/24;

    {{ range .ip_array }}
        allow {{ . }};
    {{ end }}

    # Changed by engelsofta: the API is internal-only. Home Assistant,
    # loopback and the add-on host addresses above remain permitted.
    deny all;

    # forward request to backend
    location / {
        # send it to upstream
            
        # Replace header to true origin
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header x-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass http://127.0.0.1:7813;
    }

    location /ws {
        proxy_pass http://127.0.0.1:7813/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header x-Forwarded-For $proxy_add_x_forwarded_for;
    }
}

FROM nginx:alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Custom nginx config for SPA
COPY nginx.conf /etc/nginx/conf.d/venueflow.conf

# Copy frontend files
COPY . /usr/share/nginx/html/

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]

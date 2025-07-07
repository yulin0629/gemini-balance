FROM python:3.10-slim

WORKDIR /app

# 复制所需文件到容器中
COPY ./requirements.txt /app
COPY ./VERSION /app

RUN pip install --no-cache-dir -r requirements.txt
COPY ./app /app/app
COPY ./migrations /app/migrations
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV API_KEYS='["your_api_key_1"]'
ENV ALLOWED_TOKENS='["your_token_1"]'
ENV BASE_URL=https://generativelanguage.googleapis.com/v1beta
ENV TOOLS_CODE_EXECUTION_ENABLED=false
ENV IMAGE_MODELS='["gemini-2.0-flash-exp"]'
ENV SEARCH_MODELS='["gemini-2.0-flash-exp","gemini-2.0-pro-exp"]'
ENV URL_NORMALIZATION_ENABLED=false
ENV CLOUDFLARE_IMGBED_UPLOAD_FOLDER=""

# Expose port
EXPOSE 8000

# Run the application with migration check
CMD ["/app/entrypoint.sh"]

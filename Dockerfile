FROM nipype/nipype:py38

WORKDIR /app
COPY . /app

RUN /neurodocker/startup.sh pip install --no-cache-dir -r requirements.txt

# Build the docker image

``` sh
docker build . -t fmri-conf-runner
```

# Generate a configuration CSV file

See https://github.com/Inria-Empenn/fmri_feature_model/tree/master

# Describe your data



# Run configurations

- Run configurations list from `/config.csv` file.
- Read data from `/data`
- Write NiPype cache in `/workdir`
- Write results in `/results`

## Locally
Change `/local/path/to/...` to your local paths
``` sh
docker run -u root -v "/local/path/to/data:/data" -v "/local/path/to/results:/results" -v "/local/path/to/workdir:/work" -v "/local/path/to/configs:/configs" fmri-conf-runner python -u run.py --configs "/configs/config.csv" --data /data/data_desc.json --ref /configs/config_ref.csv
```
## On Abaca (Inria cluster)
- Start 40 jobs in parallel.
- Timeout for each job is 4h
- Needs 40 configurations named CSV `config_[1..40].csv`
```sh
oarsub -S -n fmri-conf-runner ./run_configs.sh
```

# Postprocess data
## Locally
Change `/local/path/to/...` to your local paths
``` sh
docker run -u root -v "/local/path/to/results:/results" fmri-conf-runner python -u postprocess.py --results "/results"
```
## On Abaca (Inria cluster)

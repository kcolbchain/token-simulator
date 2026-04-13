# token-simulator web dashboard

Zero-build, single-file browser port of the `token_simulator` Python model.
Sliders rerun the sim live; the model is the same math as
`token_simulator/model.py`, translated to JS.

## Run locally

```bash
python3 -m http.server -d web 8080
# open http://localhost:8080
```

## Hosted

Also available on the kcolbchain site at `/token-simulator/`.

## Parity

If `token_simulator/model.py` changes, update `web/index.html`'s `runSim`
function in lockstep. A CI parity test against a fixed preset is tracked in
[#1](https://github.com/kcolbchain/token-simulator/issues/1).

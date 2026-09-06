# Paper-type reading checklists

Use the common checklist first, then the matching specialist checklist.

## Common evidence map

- Formal problem or research question; decision variables, targets, constraints, and evaluation unit.
- Prior approach and the exact bottleneck the paper claims to remove.
- Data provenance, period, geography/population, sampling, exclusions, leakage risks, and preprocessing.
- Method pipeline from raw input to final output.
- Training/estimation objective and optimization or inference procedure.
- Baselines, metrics, uncertainty, significance, ablations, sensitivity tests, and negative results.
- Main claim-to-evidence chain and whether each conclusion is direct, inferred, or speculative.
- Reproducibility: code, data, compute, hyperparameters, random seeds, licenses, and missing details.

## Weather AI / Earth-system ML

### Problem and state

- Forecast target, initialization time, nominal versus operational lead time.
- Analysis/reanalysis/observation sources and their operational latency.
- Temporal cadence, forecast horizon, spatial grid, coordinate system, and vertical levels.
- Prognostic, diagnostic, target-only, autoregressive, static, and forcing variables.

### Model and tensors

- Grid/token/mesh representations and mappings between them.
- Batch, ensemble, time-window, level, variable/channel, latitude/longitude or node dimensions.
- Encoder, processor, decoder, conditioning, stochastic latent/noise, and output heads.
- Rollout window, Markov order, teacher forcing or autoregressive feedback.
- Deterministic versus probabilistic output and ensemble generation.

### Training and verification

- Training period, validation/test periods, cycle changes, data gaps, leakage controls.
- Normalization, regridding, interpolation, lapse-rate or bias corrections.
- Losses such as MSE, CRPS, energy score, likelihood, spectral or physical penalties.
- Metrics by variable, level, region, lead time and threshold; reliability, spread-skill and extremes.
- Baselines including NWP, analysis, persistence, climatology and previous AI systems.
- Tropical cyclones, precipitation, stations, operational latency, artifacts and joint consistency.
- Compute, ensemble size, inference cadence, failure cases, climate drift and physical conservation.

## General AI method/model

- Task and data unit; train/test distribution and contamination risk.
- Tokenization or feature construction; embedding and positional representation.
- Layer-by-layer architecture, interfaces, residual paths, conditioning and output heads.
- Tensor ledger from input to output, including masking and batching.
- Objective, optimizer, schedule, regularization, initialization, curriculum and sampling.
- Inference decoding, calibration, retrieval/tool use, latency and memory complexity.
- Scaling laws, ablations, strong baselines, statistical variation and compute fairness.
- Generalization, robustness, interpretability, privacy, safety and deployment limits.

## Numerical weather/climate modelling

- Governing equations, prognostic variables, discretization, grid and time integration.
- Initial/boundary conditions, parameterizations, coupling and conservation properties.
- Resolution, stability constraints, truncation error and numerical diffusion.
- Experiments, forcing scenarios, ensembles, spin-up and control runs.
- Verification observations, uncertainty decomposition and attribution limits.

## Observational/statistical atmospheric science

- Research hypothesis and causal or associational target.
- Instruments, retrieval algorithms, station/satellite coverage and quality control.
- Sampling design, missingness, representativeness and homogenization.
- Statistical model, assumptions, covariates, confounders, multiple testing and uncertainty.
- Robustness, sensitivity, alternative explanations and external validity.

## Applicability rule

Each requested module starts with one status:

- `适用` — supported by paper evidence.
- `证据不足` — scientifically relevant but not sufficiently specified; state exactly what is missing.
- `不适用` — the paper type has no such component; replace it with the closest relevant analysis.

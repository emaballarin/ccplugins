# Literature index

Every citable claim in this plugin resolves here by key. Cite as `L-KEY` at point
of use; give the reader the key, not a bare "papers show that".

**Identifier policy.** An identifier below is either verified or absent. Entries
marked ✅ were checked against the primary source or its official repository
while this file was written. Entries marked ⚠️ carry author, title, venue and
year but **no identifier**, because fabricating one is worse than omitting it —
resolve before quoting an identifier onward. Never invent a DOI or arXiv id to
fill a gap; `folklore` is an available grade and an unresolved citation is an
available state.

---

## Method and experimental protocol

| Key               | Reference                                                                                                                                    |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `L-PLAYBOOK` ✅   | Godbole, Dahl, Gilmer, Shallue, Nado. _Deep Learning Tuning Playbook_, v1.0, 2023. github.com/google-research/tuning_playbook. **CC BY 4.0** |
| `L-CHOI19` ⚠️     | Choi et al. _On Empirical Comparisons of Optimizers for Deep Learning_, 2019. arXiv:1910.05446 — id as cited by `L-PLAYBOOK`                 |
| `L-SHALLUE18` ⚠️  | Shallue et al. _Measuring the Effects of Data Parallelism on Neural Network Training_, 2018. arXiv:1811.03600 — id as cited by `L-PLAYBOOK`  |
| `L-BERGSTRA12` ⚠️ | Bergstra & Bengio. _Random Search for Hyper-Parameter Optimization_. JMLR 13, 2012                                                           |
| `L-GELBART14` ⚠️  | Gelbart et al. _Bayesian Optimization with Unknown Constraints_, 2014. arXiv:1403.5607 — id as cited by `L-PLAYBOOK`                         |
| `L-VIZIER` ✅     | Open Source Vizier. github.com/google/vizier — quasi-random (Halton) designer; infeasible-trial support                                      |
| `L-OPTUNA` ✅     | Optuna samplers reference. Confirmed present: `QMCSampler` (low-discrepancy), `TPESampler`, `GPSampler`, `RandomSampler`, `GridSampler`      |
| `L-AIRBENCH` ⚠️   | Jordan. _94% on CIFAR-10 in 3.29 Seconds on a Single GPU_, 2024. arXiv:2404.00498 — carried from `parml`                                     |

## Optimisers

| Key                 | Reference                                                                                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `L-KINGMA15` ⚠️     | Kingma & Ba. _Adam: A Method for Stochastic Optimization_. ICLR 2015                                                                                                     |
| `L-LOSHCHILOV19` ⚠️ | Loshchilov & Hutter. _Decoupled Weight Decay Regularization_. ICLR 2019                                                                                                  |
| `L-DOZAT16` ⚠️      | Dozat. _Incorporating Nesterov Momentum into Adam_. ICLR 2016 Workshop                                                                                                   |
| `L-ADAN` ✅         | Xie, Zhou, Li, Lin, Yan. _Adan: Adaptive Nesterov Momentum Algorithm for Faster Optimizing Deep Models_, 2022. arXiv:2208.06677. Implementation: github.com/sail-sg/Adan |
| `L-ORVIETO25` ✅    | Orvieto & Gower. _In Search of Adam's Secret Sauce_, 2025. arXiv:2505.21829 — the `β₁ = β₂` tying result                                                                 |
| `L-DEFAZIO24` ⚠️    | Defazio et al. _Optimal Linear Decay Learning Rate Schedules and Further Refinements_, 2024                                                                              |
| `L-SMITH17` ⚠️      | Smith. _Cyclical Learning Rates for Training Neural Networks_. WACV 2017                                                                                                 |
| `L-TANIGUCHI24` ⚠️  | Taniguchi et al. _ADOPT: Modified Adam Can Converge with Any β₂ with the Optimal Rate_, 2024                                                                             |

Verified detail worth keeping with the citation: `L-ADAN`'s repository states its
learning rate is **"5-10 times larger than that in Adam/AdamW"** in all
experiments except MAE pre-training and LSTM; recommends weight decay `0.02`;
reports the optimiser is robust to all three betas, `β₂` especially, and that the
tuning order if needed is `β₃` then `β₁`; and describes total GPU memory cost as
"slightly higher" than Adam/AdamW despite 2× the optimiser state.

## Normalisation and its placement

| Key               | Reference                                                                                                                         |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `L-VASWANI17` ⚠️  | Vaswani et al. _Attention Is All You Need_. NeurIPS 2017 — the original **post-LN** formulation                                   |
| `L-CHEN18` ⚠️     | Chen et al. _The Best of Both Worlds: Combining Recent Advances in Neural Machine Translation_. ACL 2018 — **pre-LN** proposed    |
| `L-XIONG20` ⚠️    | Xiong et al. _On Layer Normalization in the Transformer Architecture_. ICML 2020 — pre-LN gradient analysis; warmup removal       |
| `L-DEEPNET` ✅    | Wang, Ma, Dong, Huang, Zhang, Wei. _DeepNet: Scaling Transformers to 1000 Layers_, 2022. arXiv:2203.00555 — **DeepNorm**          |
| `L-OLMO2` ✅      | OLMo Team. _2 OLMo 2 Furious_, 2025. arXiv:2501.00656 — reordered norm (normalise sublayer **outputs**) + QK-Norm                 |
| `L-PERILN` ✅     | _Peri-LN: Revisiting Normalization Layer in the Transformer Architecture_, 2025. arXiv:2502.02732                                 |
| `L-DEHGHANI23` ⚠️ | Dehghani et al. _Scaling Vision Transformers to 22 Billion Parameters_. ICML 2023 — QK LayerNorm                                  |
| `L-IOFFE15` ⚠️    | Ioffe & Szegedy. _Batch Normalization_. ICML 2015                                                                                 |
| `L-BA16` ⚠️       | Ba, Kiros, Hinton. _Layer Normalization_, 2016                                                                                    |
| `L-ZHANG19` ⚠️    | Zhang & Sennrich. _Root Mean Square Layer Normalization_. NeurIPS 2019                                                            |
| `L-WU18` ⚠️       | Wu & He. _Group Normalization_. ECCV 2018                                                                                         |
| `L-ULYANOV16` ⚠️  | Ulyanov et al. _Instance Normalization_, 2016                                                                                     |
| `L-PEREZ18` ⚠️    | Perez et al. _FiLM: Visual Reasoning with a General Conditioning Layer_. AAAI 2018 — γ, β **predicted from a conditioning input** |

## Architecture, activations, numerics

| Key                   | Reference                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `L-HE16` ⚠️           | He et al. _Deep Residual Learning for Image Recognition_. CVPR 2016                                                 |
| `L-SHAZEER20` ✅      | Shazeer. _GLU Variants Improve Transformer_, 2020. arXiv:2002.05202 — GEGLU, SwiGLU, ReGLU, Bilinear                |
| `L-DAUPHIN17` ⚠️      | Dauphin et al. _Language Modeling with Gated Convolutional Networks_. ICML 2017 — the original GLU                  |
| `L-RAMACHANDRAN17` ⚠️ | Ramachandran et al. _Searching for Activation Functions_, 2017 — Swish / SiLU                                       |
| `L-MISHKIN16` ⚠️      | Mishkin & Matas. _All you need is a good init_. ICLR 2016 — LSUV                                                    |
| `L-DAO22` ⚠️          | Dao et al. _FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness_. NeurIPS 2022              |
| `L-BONDARENKO23` ⚠️   | Bondarenko et al. _Quantizable Transformers: Removing Outliers by Helping Attention Heads Do Nothing_. NeurIPS 2023 |
| `L-SHOEYBI19` ⚠️      | Shoeybi et al. _Megatron-LM_, 2019                                                                                  |
| `L-COHEN16` ⚠️        | Cohen & Welling. _Group Equivariant Convolutional Networks_. ICML 2016                                              |

Verified detail: `L-SHAZEER20` states verbatim that **"to make the parameter
count and FLOP counts match the baseline, we reduce the hidden dimension `d_ff`
by a factor of 2/3"** — the parameter-matching convention that makes a
FFN→SwiGLU comparison fair (D3). Its conclusion offers no mechanism for why the
variants help, hoping instead that "these results encourage future work to study
gating"; grade its advantage `measured-elsewhere` with `source-uncertainty`
accordingly.

## Expressivity, spectral bias, conditioning

| Key               | Reference                                                                                                             |
| ----------------- | --------------------------------------------------------------------------------------------------------------------- |
| `L-RAHAMAN19` ⚠️  | Rahaman et al. _On the Spectral Bias of Neural Networks_. ICML 2019                                                   |
| `L-TANCIK20` ⚠️   | Tancik et al. _Fourier Features Let Networks Learn High Frequency Functions in Low Dimensional Domains_. NeurIPS 2020 |
| `L-SITZMANN20` ⚠️ | Sitzmann et al. _Implicit Neural Representations with Periodic Activation Functions_. NeurIPS 2020 — SIREN            |
| `L-MIYATO18` ⚠️   | Miyato et al. _Spectral Normalization for Generative Adversarial Networks_. ICLR 2018 — a Lipschitz **constraint**    |
| `L-CISSE17` ⚠️    | Cissé et al. _Parseval Networks_. ICML 2017                                                                           |

## Representation bottlenecks, distillation, scaling

| Key                 | Reference                                                                            |
| ------------------- | ------------------------------------------------------------------------------------ |
| `L-JANG17` ⚠️       | Jang et al. _Categorical Reparameterization with Gumbel-Softmax_. ICLR 2017          |
| `L-MADDISON17` ⚠️   | Maddison et al. _The Concrete Distribution_. ICLR 2017 — concurrent with `L-JANG17`  |
| `L-OORD17` ⚠️       | van den Oord et al. _Neural Discrete Representation Learning_. NeurIPS 2017 — VQ-VAE |
| `L-REZENDE18` ⚠️    | Rezende & Viola. _Taming VAEs_, 2018 — GECO                                          |
| `L-HINTON14` ⚠️     | Hinton et al. _Distilling the Knowledge in a Neural Network_. NeurIPS Workshops 2014 |
| `L-FURLANELLO18` ⚠️ | Furlanello et al. _Born-Again Neural Networks_. ICML 2018                            |
| `L-HOFFMANN22` ⚠️   | Hoffmann et al. _Training Compute-Optimal Large Language Models_. NeurIPS 2022       |
| `L-DIELEMAN24` ✅   | Dieleman. _Diffusion is Spectral Autoregression_. sander.ai, 2024                    |

---

## Using this index

- **Grade, then cite.** A citation is what lets a claim be `measured-elsewhere`
  instead of `folklore`; it is not what makes the claim true here. Apply the
  degradation rule in `evidence-grades.md` §1 when the source's conditions differ
  from the pipeline in front of you.
- **State the conditions, not just the key.** "`L-ADAN` reports halved epoch
  budgets on ViT/ConvNeXt/MAE" is usable; "Adan is faster" is not.
- **`source-uncertainty` is a separate flag from the grade.** It marks that the
  cited source itself declines to settle the question — `L-PLAYBOOK`'s 🤖
  sections, `L-SHAZEER20`'s conclusion, the LN final-quality comparison. A
  well-cited open question is still an open question.

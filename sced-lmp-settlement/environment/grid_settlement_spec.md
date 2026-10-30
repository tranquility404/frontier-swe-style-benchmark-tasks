# Normative Specification: Multi-Interval Co-Optimized SCED-OR and Two-Settlement LMP/MCP Market Clearing

## 1. Scope and Execution Contract

The clearing engine in `/app/gridop/settle.py` clears all episode directories under a target directory (defaulting to `/app/episodes`) sorted lexicographically by `episode_id` and writes the combined JSON settlement ledger to a target output path (defaulting to `/app/settlement_ledger.json`).

### 1.1 Command-Line Interface

`/app/gridop/settle.py` must support:
- Default invocation with no arguments:
  ```bash
  python3 /app/gridop/settle.py
  ```
  reading all episodes in `/app/episodes` and writing `/app/settlement_ledger.json`.
- Parameterized invocation:
  ```bash
  python3 /app/gridop/settle.py --episodes-dir <DIR> --output <PATH>
  ```
  (and optional positional arguments `python3 /app/gridop/settle.py <DIR> <PATH>`), reading all episode subdirectories under `<DIR>` containing `grid_topology.json`, `market_offers.json`, and `scada_telemetry.bin`, and writing the ledger JSON to `<PATH>`.

---

## 2. Rule 1: Binary SCADA / Synchrophasor Telemetry Pre-Processing (`scada_telemetry.bin`)

Each episode directory contains a binary telemetry stream `scada_telemetry.bin` encoding raw bus demand measurements and transmission line dynamic rating (DLR) packets across $T = \text{num\_intervals}$ intervals, $N = |\text{buses}|$ buses (indexed $0 \dots N-1$ in array order of `grid_topology.json["buses"]`), and $L = |\text{lines}|$ lines (indexed $0 \dots L-1$ in array order of `grid_topology.json["lines"]`).

### 2.1 Binary Layout (Little-Endian)

1. **File Header (16 bytes, `<6sHHHHH`)**:
   - `magic` (`6s`): ASCII bytes `b"SCADA1"`.
   - `version` (`uint16`): Format version `1`.
   - `num_intervals` (`uint16`): $T$.
   - `num_buses` (`uint16`): $N$.
   - `num_lines` (`uint16`): $L$.
   - `record_count` (`uint16`): Total number of 24-byte frames following the 16-byte header.

2. **Telemetry Frame (24 bytes each, `<BBHIIffHH`)**:
   - `frame_type` (`uint8`): `1` = Nodal Load Synchrophasor Frame ($n \in \{0 \dots N-1\}$), `2` = Transmission Line Dynamic Rating Frame ($\ell \in \{0 \dots L-1\}$).
   - `status_flags` (`uint8` bitmask):
     - `0x01` (`FLAG_VALID`): Frame carries an initialized payload.
     - `0x02` (`FLAG_STALE_HOLD`): Sensor is frozen in stale-hold state.
     - `0x04` (`FLAG_PMU_LOW_QUALITY`): Phase-lock degraded.
     - `0x08` (`FLAG_TELEMETRY_SPIKE`): Hardware transient spike.
     - `0x10` (`FLAG_KW_LOSS_MODE`): Active/loss encoding mode for `frame_type == 1`.
   - `interval_idx` (`uint16`): Interval index $t \in \{0 \dots T-1\}$.
   - `entity_id` (`uint32`): Bus index $n$ or line index $\ell$.
   - `seq_num` (`uint32`): Monotonic packet sequence number.
   - `val_primary` (`float32`): Primary measurement float.
   - `val_secondary` (`float32`): Secondary measurement float.
   - `reserved` (`uint16`): Channel tag (`0`).
   - `crc16` (`uint16`): CRC-16-CCITT checksum over first 22 bytes (`frame[:22]`).

### 2.2 CRC-16-CCITT & Filtering

- **CRC-16-CCITT**: Polynomial `0x1021`, initial value `0xFFFF`, non-reflected, final XOR `0x0000`.
- **Integrity Validation**: Frame is valid if `crc16_ccitt(frame[:22]) == crc16`, `status_flags & 0x01 != 0`, `status_flags & 0x08 == 0`, $0 \le t < T$, and $0 \le \text{entity\_id} < (N \text{ if } \text{type}=1 \text{ else } L)$. Failing frames increment `corrupt_or_spike_dropped`.
- **Deduplication**: Group valid frames by `(frame_type, interval_idx, entity_id)`. Retain the single frame with the strictly largest `seq_num`, incrementing `duplicate_seq_dropped` by $k - 1$. If a higher-`seq_num` frame carries `FLAG_STALE_HOLD` (`0x02`) or `FLAG_PMU_LOW_QUALITY` (`0x04`), it supersedes any earlier lower-`seq_num` frame for that key and marks that interval unusable.
- **Usability & Conversion**:
  - Bus Load (`type == 1`): Usable if `(status_flags & 0x06) == 0`.
    - If `(status_flags & 0x10) == 0`: $d_{n,t}^{\text{raw}} = \frac{S_{n,t} \cdot \cos(\varphi_{n,t} \times 10^{-3})}{1000.0}$.
    - If `(status_flags & 0x10) != 0`: $d_{n,t}^{\text{raw}} = \frac{P_{n,t}^{\text{kw}} + Q_{n,t}^{\text{loss\_kw}}}{1000.0}$.
    - $d_{n,t} = \text{round}(d_{n,t}^{\text{raw}}, 6)$, incrementing `valid_frames_used`.
    - For each bus $n \in \{0 \dots N-1\}$ and interval $t \in \{0 \dots T-1\}$ where bus load $d_{n,t}$ is missing or unusable (`(status_flags & 0x06) != 0`), increment `stale_or_low_quality_imputed` by 1 and linearly interpolate across the nearest preceding and succeeding usable intervals $t_{\text{prev}} < t < t_{\text{next}}$ (clamping to the first usable interval if $t < t_{\text{first}}$, to the last usable interval if $t > t_{\text{last}}$, or falling back to `market_offers.json["da_bus_load_mw"][bus_id][t]` if bus $n$ has no usable Type-1 frames across the entire horizon), yielding the $N \times T$ matrix `reconstructed_bus_load_mw` indexed as `reconstructed_bus_load_mw[n][t]`.
  - Transmission Line Dynamic Rating (`type == 2`): Usable if `(status_flags & 0x06) == 0`.
    - If usable: $\beta_{\ell,t} = \text{round}(\min(1.0, \max(0.5, \text{val\_primary} / 10000.0)), 6)$, incrementing `valid_frames_used`.
    - If a present Type-2 frame is unusable (stale or low quality, i.e., `(status_flags & 0x06) != 0`), it falls back to $1.0$ and increments `stale_or_low_quality_imputed` by 1. (Missing Type-2 intervals not present in the record stream default to $1.0$ without incrementing `stale_or_low_quality_imputed`; for example, in `ep01_radial_bridge`, `stale_or_low_quality_imputed` totals 13: 4 bus-load imputations + 9 unusable DLR fallbacks.)

---

## 3. Rule 2: DC Power Flow PTDF, Phase-Shifters, Radial Bridges, N-1 LODF, and G-1 OTDF-G

Let $S_{\text{base}} = \text{base\_mva}$, and slack bus $r = \text{ref\_bus\_id}$ ($\theta_{r,t} = 0$).

### 3.1 PTDF Matrix and Phase-Shifter Loop Flow

- Branch susceptance in `MW/rad`: $b_\ell = S_{\text{base}} / x_\ell$. Phase-shifter angle in radians: $\phi_\ell^{\text{pst}} = \text{pst\_angle\_deg} \cdot \frac{\pi}{180}$.
- Branch-bus incidence matrix $A \in \{-1, 0, +1\}^{L \times N}$ ($A_{\ell, u_\ell} = +1, A_{\ell, v_\ell} = -1$).
- Reduced bus susceptance matrix: $B_{\text{bus,red}} = A_{\text{red}}^T B_{\text{diag}} A_{\text{red}} \in \mathbb{R}^{(N-1) \times (N-1)}$.
- Injection Shift Factor (`PTDF`) matrix $H \in \mathbb{R}^{L \times N}$: Column $r$ is $\mathbf{0}$, non-reference columns:
  $$H_{:, \mathcal{N}_{\text{nonref}}} = B_{\text{diag}} A_{\text{red}} B_{\text{bus,red}}^{-1}$$
- Base-case Phase-Shifting Transformer (`PST`) offset $f^{\text{pst},(0)} \in \mathbb{R}^L$:
  $$f^{\text{pst},(0)} = H \left(A^T (b \odot \phi^{\text{pst}})\right) - (b \odot \phi^{\text{pst}})$$
- Affine base-case line flow:
  $$f_t^{(0)} = H p_t^{\text{net}} + f^{\text{pst},(0)}$$

### 3.2 Radial Bridge Detection and N-1 Line Outage Factors (`LODF` & `OTDF`)

- Transfer impedance: $h_{:, k} = H_{:, u_k} - H_{:, v_k} \in \mathbb{R}^L$.
- If $|1.0 - h_{k,k}| < 10^{-9}$, line $k$ is a **radial bridge (cut-edge)**:
  - Add to `bridge_line_ids`. Excluded from N-1 contingency outage redistribution ($D_{:, k} = \mathbf{0}$).
  - Base-case N-0 thermal limit derated by $\gamma_{\text{bridge}}$: $\bar{F}_{k,t}^{(0)} = \gamma_{\text{bridge}} \beta_{k,t} F_k^{\max}$.
- If $|1.0 - h_{k,k}| \ge 10^{-9}$, non-bridge line $k$ has N-0 limit $\bar{F}_{k,t}^{(0)} = \beta_{k,t} F_k^{\max}$ and `LODF` column:
  $$D_{\ell, k} = \begin{cases} -1.0, & \ell = k \\ \dfrac{h_{\ell, k}}{1.0 - h_{k,k}}, & \ell \ne k \end{cases}$$
- For each active N-1 contingency pair $c = (\ell, k)$ with monitored line $\ell$ (`is_monitored == true`), candidate outage $k \notin \text{bridge\_line\_ids}$ (`is_contingency_candidate == true`), $\ell \ne k$, and $|D_{\ell,k}| \ge 10^{-9}$:
  $$\text{OTDF}_{c, :} = H_{\ell, :} + D_{\ell,k} H_{k, :}, \qquad f_c^{\text{pst},(1)} = f_\ell^{\text{pst},(0)} + D_{\ell,k} f_k^{\text{pst},(0)}$$
  Post-contingency line flow: $f_{\ell,t}^{(k)} = \text{OTDF}_{c, :} p_t^{\text{net}} + f_c^{\text{pst},(1)}$, subject to emergency rating $F_{\ell,t}^{\text{cont}} = \alpha_\ell^{\text{emg}} \beta_{\ell,t} F_\ell^{\max}$.

### 3.3 G-1 Generator Outage Contingencies with Governor Droop Redistribution (`OTDF-G`)

- Let $\mathcal{G}_t^{\text{on}} = \{g \in \mathcal{G} : u_{g,t} = 1\}$ denote the set of committed online thermal generators in interval $t$. For each generator $g \in \mathcal{G}$, governor droop response factor is $\delta_g = 1.0 / \text{droop\_pu}_g$.
- If online generator $k \in \mathcal{G}_t^{\text{on}}$ trips in interval $t$ with output $p_{k,t}$, the lost generation is compensated by all remaining online generators $j \in \mathcal{G}_t^{\text{on}} \setminus \{k\}$ according to their relative governor response share:
  $$\alpha_{j,k,t} = \frac{\delta_j}{\sum_{m \in \mathcal{G}_t^{\text{on}}, m \ne k} \delta_m}$$
  (Offline generators with $u_{m,t} = 0$ have zero governor response and do not participate.)
- The net nodal post-contingency power change vector $\Delta p^{(G-k)}_t \in \mathbb{R}^N$ has:
  $$\Delta p_{n,t}^{(G-k)} = -\mathbb{I}(n = n(k)) p_{k,t} + \sum_{j \in \mathcal{G}_t^{\text{on}}, j \ne k, n(j) = n} \alpha_{j,k,t} p_{k,t}$$
- For each monitored line $\ell \in \mathcal{M}$ (`is_monitored == true`) and online generator contingency $k \in \mathcal{G}_t^{\text{on}}$, the G-1 transfer factor is:
  $$\Psi_{\ell, k, t} = \sum_{j \in \mathcal{G}_t^{\text{on}}, j \ne k} \alpha_{j,k,t} H_{\ell, n(j)} - H_{\ell, n(k)}$$
- The post-$G-1$ contingency line flow on monitored line $\ell \in \mathcal{M}$ when generator $k \in \mathcal{G}_t^{\text{on}}$ trips is:
  $$f_{\ell,t}^{(G-k)} = f_{\ell,t}^{(0)} + \Psi_{\ell, k, t} p_{k,t}$$
  subject to emergency thermal rating: $|f_{\ell,t}^{(G-k)}| \le F_{\ell,t}^{\text{cont}}$.

---

## 4. Rule 3: Coupled Multi-Interval SCED and Operating Reserves (SCED-OR)

### 4.1 Minimum-Uptime Carry-Over Commitment

Generator commitment $u_{g,t} \in \{0, 1\}$ is determined deterministically from `initial_on_intervals` ($k_0$), `min_uptime_intervals` ($U_g^{\min}$), and `must_run_schedule` ($m_{g,t} \in \{0, 1\}$): a generator is committed ($u_{g,t} = 1$) in interval $t \in \{0 \dots T-1\}$ if and only if $m_{g,t} = 1$ or it was online in interval $t-1$ (with $u_{g,-1} = \mathbb{I}(k_0 > 0)$) and its consecutive online duration ending at $t-1$ (seeded with $k_0$ at $t = -1$ and resetting to $0$ whenever $u_{g,t} = 0$) is strictly less than $U_g^{\min}$.

### 4.2 Joint Co-Optimization Linear Program

Solve a single coupled linear program over all intervals $t \in \{0 \dots T-1\}$ with $\Delta t = \text{interval\_hours}$:

1. **Decision Variables**:
   - Generator block outputs: Each generator $g$ has three offer blocks identified by `block_idx` $b \in \{0, 1, 2\}$ in `market_offers.json["generator_offers"][gen_id]` (which may appear in arbitrary list order and must be indexed by `block_idx` $b \in \{0, 1, 2\}$), with block capacity $\bar{P}_{g,b}^{\text{blk}} = \text{mw\_cap}$ and marginal price $c_{g,b} = \text{price\_per\_mwh}$:
     $$0 \le p_{g,b,t}^{\text{blk}} \le \bar{P}_{g,b}^{\text{blk}} u_{g,t}, \qquad p_{g,t} = u_{g,t} P_g^{\min} + \sum_{b=0}^{2} p_{g,b,t}^{\text{blk}}$$
   - 10-minute Synchronized Spinning Reserves: Bounded by both the static reserve cap `max_spin_mw` and the 10-minute ($\frac{10}{60}\text{ h} = \frac{1}{6}\text{ h}$) physical ramp-up capability:
     $$0 \le r_{g,t}^{\text{spin}} \le \min\left(\text{max\_spin\_mw}_g, \; \frac{1}{6} R_g^{\text{up}}\right) u_{g,t}$$
   - Storage charging $0 \le p_{s,t}^{\text{ch}} \le P_s^{\text{ch,max}}$, discharging $0 \le p_{s,t}^{\text{dis}} \le P_s^{\text{dis,max}}$, and storage spinning reserve $0 \le r_{s,t}^{\text{spin}} \le \text{max\_spin\_mw}_s$.
   - System reserve scarcity deficit variable: $s_t^{\text{scarcity}} \ge 0$.

2. **Objective Function (Total Variable Operating Cost in USD)**:
   $$\min \sum_{t=0}^{T-1} \Delta t \left( \sum_{g \in \mathcal{G}} \sum_{b=0}^{2} c_{g,b} p_{g,b,t}^{\text{blk}} + \sum_{g \in \mathcal{G}} c_g^{\text{spin}} r_{g,t}^{\text{spin}} + \sum_{s \in \mathcal{S}} \left( c_s^{\text{wear}} (p_{s,t}^{\text{ch}} + p_{s,t}^{\text{dis}}) + c_s^{\text{spin}} r_{s,t}^{\text{spin}} \right) + V_{\text{scarcity}} s_t^{\text{scarcity}} \right)$$
   where $V_{\text{scarcity}} = \text{reserve\_scarcity\_penalty\_usd\_per\_mwh}$.

3. **System Energy Balance (per interval $t$)**:
   $$p_{n,t}^{\text{net}} = \sum_{g \in \mathcal{G}_n} p_{g,t} + \sum_{s \in \mathcal{S}_n} (p_{s,t}^{\text{dis}} - p_{s,t}^{\text{ch}}) - d_{n,t}, \qquad \sum_{n=0}^{N-1} p_{n,t}^{\text{net}} = 0 \;\; (\text{dual } \lambda_t^{\text{energy}})$$

4. **System Spinning Reserve Requirement (per interval $t$)**:
   $$\sum_{g \in \mathcal{G}} r_{g,t}^{\text{spin}} + \sum_{s \in \mathcal{S}} r_{s,t}^{\text{spin}} + s_t^{\text{scarcity}} \ge R_t^{\text{req}} \;\; (\text{dual } \text{MCP}_t^{\text{spin}} \ge 0)$$
   where $R_t^{\text{req}} = \text{min\_spinning\_reserve\_mw}$.

5. **Joint Capacity & Headroom Constraints**:
   $$p_{g,t} + r_{g,t}^{\text{spin}} \le P_g^{\max} u_{g,t}$$
   $$p_{s,t}^{\text{dis}} + r_{s,t}^{\text{spin}} \le P_s^{\text{dis,max}}$$

6. **Inter-Temporal Ramping with Reserve Sharing** (with $u_{g,-1} = \mathbb{I}(\text{initial\_on\_intervals}_g > 0)$ and $p_{g,-1} = \text{p\_init\_mw}_g$):
   - Continuing online ($u_{g,t} = 1$ and $u_{g,t-1} = 1$):
     $$p_{g,t} - p_{g,t-1} + r_{g,t}^{\text{spin}} \le R_g^{\text{up}} \Delta t$$
     $$p_{g,t-1} - p_{g,t} \le R_g^{\text{down}} \Delta t$$
   - Startup transition ($u_{g,t} = 1$ and $u_{g,t-1} = 0$):
     $$p_{g,t} + r_{g,t}^{\text{spin}} \le \min\left(P_g^{\max}, \; P_g^{\min} + R_g^{\text{up}} \Delta t\right)$$
   - Decommitment / shutdown transition ($u_{g,t} = 0$ and $u_{g,t-1} = 1$ for $t \in \{1 \dots T-1\}$):
     $$p_{g,t-1} \le \min\left(P_g^{\max}, \; P_g^{\min} + R_g^{\text{down}} \Delta t\right)$$

7. **Storage Leaky State-of-Charge & Sustained Reserve Duration Headroom**:
   - SoC recurrence (with $E_{s,-1} = \text{soc\_init\_mwh}_s$): $E_{s,t} = \rho_s E_{s,t-1} + (\eta_s^{\text{ch}} p_{s,t}^{\text{ch}} - p_{s,t}^{\text{dis}} / \eta_s^{\text{dis}}) \Delta t$.
   - Energy bounds: $E_s^{\min} \le E_{s,t} \le E_s^{\max}$, and terminal target $E_{s,T-1} \ge E_s^{\text{term}}$.
   - Sustained reserve duration buffer (where $\tau_s^{\text{res}} = \text{reserve\_duration\_hours}_s$ on storage unit $s$, falling back to top-level `reserve_duration_hours` if omitted on unit $s$):
     $$E_{s,t} - \left(p_{s,t}^{\text{dis}} + r_{s,t}^{\text{spin}}\right) \times \tau_s^{\text{res}} \ge E_s^{\min}$$
     $$E_{s,t} + p_{s,t}^{\text{ch}} \times \tau_s^{\text{res}} \le E_s^{\max}$$

8. **Transmission Security Limits (N-0, N-1, and G-1)**:
   - N-0 limits (all lines $\ell \in \{0 \dots L-1\}$): $-\bar{F}_{\ell,t}^{(0)} \le f_{\ell,t}^{(0)} \le \bar{F}_{\ell,t}^{(0)}$ ($\mu_{\ell,t}^{(0)+}, \mu_{\ell,t}^{(0)-} \ge 0$).
   - N-1 line limits (active contingency pairs $c = (\ell, k) \in \mathcal{C}$): $-F_{\ell,t}^{\text{cont}} \le f_{\ell,t}^{(k)} \le F_{\ell,t}^{\text{cont}}$ ($\mu_{c,t}^{(1)+}, \mu_{c,t}^{(1)-} \ge 0$).
   - G-1 generator limits (monitored lines $\ell \in \mathcal{M}$ and online generators $k \in \mathcal{G}_t^{\text{on}}$): $-F_{\ell,t}^{\text{cont}} \le f_{\ell,t}^{(G-k)} \le F_{\ell,t}^{\text{cont}}$ ($\mu_{\ell,k,t}^{(G)+}, \mu_{\ell,k,t}^{(G)-} \ge 0$).
   - The reported `max_post_contingency_loading_ratio[t]` is the maximum over all active N-1 pairs $c = (\ell, k) \in \mathcal{C}$ and all monitored lines $\ell \in \mathcal{M}$ with online generator contingencies $k \in \mathcal{G}_t^{\text{on}}$ of $|f_{\ell,t}^{(k)}| / F_{\ell,t}^{\text{cont}}$ and $|f_{\ell,t}^{(G-k)}| / F_{\ell,t}^{\text{cont}}$.

---

## 5. Rule 4: KKT Shadow-Price Decomposition for LMPs and Reserve MCPs

All shadow prices are scaled by $1 / \Delta t$ to express values in `$/MWh`.

1. **System Energy Price $\lambda_t^{\text{energy}}$ & Reserve Price $\text{MCP}_t^{\text{spin}}$**:
   - $\lambda_t^{\text{energy}}$ is the dual multiplier of the system power balance constraint.
   - $\text{MCP}_t^{\text{spin}}$ is the non-negative dual multiplier of the system reserve requirement.

2. **Nodal Congestion LMP & Total LMP**:
   $$\text{LMP}_{n,t}^{\text{cong}} = -\sum_{\ell=0}^{L-1} H_{\ell,n}(\mu_{\ell,t}^{(0)+} - \mu_{\ell,t}^{(0)-}) - \sum_{c \in \mathcal{C}} \text{OTDF}_{c,n}(\mu_{c,t}^{(1)+} - \mu_{c,t}^{(1)-}) - \sum_{k \in \mathcal{G}_t^{\text{on}}} \sum_{\ell \in \mathcal{M}} H_{\ell,n}(\mu_{\ell,k,t}^{(G)+} - \mu_{\ell,k,t}^{(G)-})$$
   $$\text{LMP}_{n,t} = \lambda_t^{\text{energy}} + \text{LMP}_{n,t}^{\text{cong}}$$
   At slack bus $r$, $H_{\ell,r} = 0$ so $\text{LMP}_{r,t}^{\text{cong}} = 0$ and $\text{LMP}_{r,t} = \lambda_t^{\text{energy}}$.

3. **Congestion Rent & Net Surplus**:
   - Total interval congestion rent:
     $$\text{CR}_t = -\Delta t \sum_{n=0}^{N-1} \text{LMP}_{n,t} p_{n,t}^{\text{net}}$$
   - Interval PST loop-flow congestion rent (`interval_pst_congestion_rent_usd`):
     $$\text{CR}_t^{\text{PST}} = -\Delta t \left( \sum_{\ell=0}^{L-1} (\mu_{\ell,t}^{(0)+} - \mu_{\ell,t}^{(0)-}) f_\ell^{\text{pst},(0)} + \sum_{c \in \mathcal{C}} (\mu_{c,t}^{(1)+} - \mu_{c,t}^{(1)-}) f_c^{\text{pst},(1)} + \sum_{k \in \mathcal{G}_t^{\text{on}}} \sum_{\ell \in \mathcal{M}} (\mu_{\ell,k,t}^{(G)+} - \mu_{\ell,k,t}^{(G)-}) f_\ell^{\text{pst},(0)} \right)$$

---

## 6. Rule 5: Two-Settlement Imbalance with Multi-Interval Netting BCR

1. **Generator Settlement**:
   - Day-Ahead Energy Revenue: $R_g^{\text{DA,E}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{LMP}_{n(g),t}^{\text{DA}} \cdot p_{g,t}^{\text{DA}}$
   - Real-Time Energy Imbalance: $R_g^{\text{RT,E}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{LMP}_{n(g),t} \cdot (p_{g,t} - p_{g,t}^{\text{DA}})$
   - Day-Ahead Reserve Revenue: $R_g^{\text{DA,R}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{MCP}_t^{\text{DA,spin}} \cdot r_{g,t}^{\text{DA,spin}}$
   - Real-Time Reserve Imbalance: $R_g^{\text{RT,R}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{MCP}_t^{\text{spin}} \cdot (r_{g,t}^{\text{spin}} - r_{g,t}^{\text{DA,spin}})$
   - Total Operating Production Cost (with $u_{g,-1} = \mathbb{I}(\text{initial\_on\_intervals}_g > 0)$):
     $$C_g^{\text{tot}} = \sum_{t=0}^{T-1} \left( u_{g,t} C_g^{\text{no-load}} \Delta t + \Delta t \sum_{b=0}^{2} c_{g,b} p_{g,b,t}^{\text{blk}} + \Delta t c_g^{\text{spin}} r_{g,t}^{\text{spin}} \right) + \sum_{t=0}^{T-1} \mathbb{I}(u_{g,t}=1 \land u_{g,t-1}=0) C_g^{\text{startup}}$$
   - Real-Time As-Dispatched Value (Energy + Reserves):
     $$V_g^{\text{RT-as-disp}} = \sum_{t=0}^{T-1} \Delta t \left( \text{LMP}_{n(g),t} p_{g,t} + \text{MCP}_t^{\text{spin}} r_{g,t}^{\text{spin}} \right)$$
   - **Multi-Interval Netted Make-Whole Payment (MWP) Uplift**:
     $$\text{MWP}_g = \max\left(0.0, \; C_g^{\text{tot}} - V_g^{\text{RT-as-disp}}\right)$$
     $$\text{NetSettlement}_g = R_g^{\text{DA,E}} + R_g^{\text{RT,E}} + R_g^{\text{DA,R}} + R_g^{\text{RT,R}} + \text{MWP}_g$$

2. **Storage Settlement**:
   - $R_s^{\text{DA,E}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{LMP}_{n(s),t}^{\text{DA}} \cdot p_{s,t}^{\text{DA,net}}$
   - $R_s^{\text{RT,E}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{LMP}_{n(s),t} \cdot (p_{s,t}^{\text{net}} - p_{s,t}^{\text{DA,net}})$
   - $R_s^{\text{DA,R}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{MCP}_t^{\text{DA,spin}} \cdot r_{s,t}^{\text{DA,spin}}$
   - $R_s^{\text{RT,R}} = \sum_{t=0}^{T-1} \Delta t \cdot \text{MCP}_t^{\text{spin}} \cdot (r_{s,t}^{\text{spin}} - r_{s,t}^{\text{DA,spin}})$
   - Wear cost: $C_s^{\text{wear}} = \sum_{t=0}^{T-1} \Delta t \cdot c_s^{\text{wear}} (p_{s,t}^{\text{ch}} + p_{s,t}^{\text{dis}})$
   - Net Settlement: $R_s^{\text{DA,E}} + R_s^{\text{RT,E}} + R_s^{\text{DA,R}} + R_s^{\text{RT,R}}$

3. **LSE Allocation**:
   - Metered load share: $w_m = \frac{E_m^{\text{RT}}}{\sum_{m'} E_{m'}^{\text{RT}}}$, where $E_m^{\text{RT}} = \sum_{n \in \mathcal{B}_m} \sum_{t=0}^{T-1} \Delta t \cdot d_{n,t}$.
   - Congestion rent rebate: $\text{Rebate}_m^{\text{CR}} = w_m \cdot \sum_{t=0}^{T-1} \text{CR}_t$.
   - Uplift charge allocation: $\text{Alloc}_m^{\text{MWP}} = w_m \cdot \sum_{g \in \mathcal{G}} \text{MWP}_g$.
   - Net LSE charge: $\text{Pay}_m^{\text{DA}} + \text{Pay}_m^{\text{RT}} - \text{Rebate}_m^{\text{CR}} + \text{Alloc}_m^{\text{MWP}}$.

---

## 7. Output Ledger Schema (`/app/settlement_ledger.json`)

All floats are rounded to 6 decimal places (`round(val, 6)`). Top-level structure:
```json
{
  "schema_version": "1.0",
  "episodes": {
    "<episode_id>": {
      "episode_id": "<episode_id>",
      "num_intervals": 8,
      "interval_hours": 0.5,
      "telemetry_summary": {
        "valid_frames_used": 60,
        "corrupt_or_spike_dropped": 10,
        "duplicate_seq_dropped": 12,
        "stale_or_low_quality_imputed": 13,
        "reconstructed_bus_load_mw": [[...], ...]
      },
      "topology_diagnostics": {
        "bridge_line_ids": ["L11"],
        "active_contingency_pairs": [["L01", "L02"], ...]
      },
      "dispatch": {
        "thermal_mw": { "G01": [...], ... },
        "generator_block_dispatch_mw": { "G01": [[...], [...], [...]], ... },
        "spinning_reserve_mw": { "G01": [...], ... },
        "storage_charge_mw": { "S01": [...], ... },
        "storage_discharge_mw": { "S01": [...], ... },
        "storage_spin_mw": { "S01": [...], ... },
        "storage_soc_mwh": { "S01": [...], ... },
        "reserve_scarcity_mw": [...],
        "commitment_status": { "G01": [1, 1, ...], ... },
        "net_nodal_injection_mw": { "B01": [...], ... },
        "base_line_flow_mw": { "L01": [...], ... },
        "max_post_contingency_loading_ratio": [...],
        "total_variable_dispatch_cost_usd": 10272.842105
      },
      "prices": {
        "system_energy_lambda_usd_per_mwh": [...],
        "reserve_mcp_usd_per_mwh": [...],
        "nodal_lmp_usd_per_mwh": { "B01": [...], ... },
        "nodal_congestion_lmp_usd_per_mwh": { "B01": [...], ... }
      },
      "settlement": {
        "interval_congestion_rent_usd": [...],
        "interval_pst_congestion_rent_usd": [...],
        "total_congestion_rent_usd": 145.201234,
        "generator_settlement": {
          "G01": {
            "da_energy_revenue_usd": 0.0,
            "rt_imbalance_revenue_usd": 0.0,
            "da_reserve_revenue_usd": 0.0,
            "rt_reserve_revenue_usd": 0.0,
            "rt_as_dispatched_energy_value_usd": 0.0,
            "total_three_part_cost_usd": 0.0,
            "make_whole_uplift_usd": 0.0,
            "total_net_settlement_usd": 0.0
          }
        },
        "storage_settlement": {
          "S01": {
            "da_energy_revenue_usd": 0.0,
            "rt_imbalance_revenue_usd": 0.0,
            "da_reserve_revenue_usd": 0.0,
            "rt_reserve_revenue_usd": 0.0,
            "wear_cost_usd": 0.0,
            "total_net_settlement_usd": 0.0
          }
        },
        "lse_settlement": {
          "LSE_01": {
            "total_rt_load_mwh": 0.0,
            "load_share_ratio": 0.0,
            "da_load_payment_usd": 0.0,
            "rt_imbalance_load_payment_usd": 0.0,
            "congestion_rent_rebate_usd": 0.0,
            "uplift_charge_allocation_usd": 0.0,
            "net_lse_charge_usd": 0.0
          }
        },
        "total_make_whole_uplift_usd": 4200.123456
      }
    }
  }
}
```
Here `generator_block_dispatch_mw[gen_id]` is a $3 \times T$ list of lists `[block_0_series, block_1_series, block_2_series]` ordered by `block_idx` $b \in \{0, 1, 2\}$ where each series has length $T$.

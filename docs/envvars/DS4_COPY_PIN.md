# `DS4_COPY_PIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の MXFP4 GGUF で、CPU lane の expert を RAM にコピーしたとき、そのコピー領域を `cudaHostRegister` に渡して GPU から直接読み出せるようにするかを制御します。有効時は `cudaHostRegisterPortable`、別変数 `DS4_COPY_PIN_RO` が整数として非ゼロなら `cudaHostRegisterReadOnly` を指定します。登録に成功すると prompt path がコピー領域を直接 DMA する状態になり、失敗すると staging 経由のままです。

## 値と判定

共通 helper `env_tri()` は `getenv()` が null のとき `-1`、設定されていれば `atoi()` の結果が 0 かどうかで `0` / `1` にします。したがって空文字や数字で始まらない値は `0`、整数として非ゼロになる値は `1` です。`atoi()` は文字列全体の厳密な検証ではないため、数値の後ろに文字がある値も数値部分で判定されます（例: `1abc` は `1`、`0abc` は `0`）。

| `DS4_COPY_PIN` | `copy_pin_default()` の判定 |
|---|---|
| 未設定 | `DS4_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` のいずれかなら OFF。それ以外は下記の自動条件で決定 |
| `atoi()` が 0 | OFF |
| `atoi()` が非ゼロ | ON。ただし CPU lane の RAM コピー領域が存在することは必要 |

未設定時の自動条件は、`DS4_DEFAULTS` が上記の旧既定値でなく、かつ RAM コピー chunk が一つ以上あり、次のいずれかを満たすことです。

- コピー arena の全 chunk が明示的な 2 MB huge page 上にある。
- HIP build で全使用 GPU が RDNA4（`gfx1200` / `gfx1201`）と判定され、GPU が routed expert の少なくとも半分を保持できる（`gpu_expert_share() >= 0.5`）。

CUDA build では `rdna4()` は false なので、未設定時の RDNA4 条件は成立しません。明示値 `0` / 非ゼロは `DS4_DEFAULTS=026` による既定値を上書きします。Strata の「DeepSeek speed-ups」を OFF にすると設定環境へ `DS4_DEFAULTS=026` と `DS4_COPY_PIN=0` が書かれます。ON の既定状態ではこれらの項目を出さず、エンジンの既定判定に任せます。

## 有効になる条件

- 対象コード経路は `load_experts()` が MXFP4 を検出して呼ぶ `load_experts_mx()` です。
- `load_experts_mx()` が `!ram_tier && !warm.empty()` の場合にコピー候補を作り、`copy_experts()` を呼びます。`--mmap-experts on`（内部値が正）では `copy_experts()` が即時に戻るため、この変数による登録はありません。
- `--mmap-experts off` は収まる範囲をコピーし、`auto` は自動コピー条件と RAM 予算を満たす場合にコピーします。候補が空、コピー予算が 0 以下、割り当て失敗などで chunk がなければ、明示的に非ゼロを指定しても pin されません。
- 自動 pin の huge-page 条件は `DS4_COPY_HUGETLB` の判定にも依存します。huge arena を要求しても割り当てで pool が尽きた chunk は通常 arena に fallback し、`arena_all_huge` が false になります。この場合、全 chunk が huge page という条件は満たしません。明示的な `DS4_COPY_PIN` 非ゼロならこの自動条件は不要です。

`--mmap-experts` は `on` / `off` / `auto` を受け取り、その他の文字列も実装上は `auto` 相当（内部値 `-1`）になります。pin 専用 CLI 引数は確認できません。

## 実行時の詳細

`DS4_COPY_PIN` は `copy_experts()` が CPU lane のコピーを作った後、コピー完了ログの後で `env_tri("DS4_COPY_PIN")` により読み取られます。読み取り結果自体に static cache はありません。環境値の変更はこのモデル読み込み時の判定に間に合う必要があり、既に読み込んだモデルの prompt / decode ごとには再評価されません。対して `DS4_DEFAULTS` は helper 内の `static const bool` に一度保存され、同じプロセスで最初に呼ばれた後の環境変更では再判定されません。

有効判定後、Strata は `ram_chunks` の各 chunk を順に `cudaHostRegister` します。全て成功した場合は `ram_pinned=true` とし、stderr に `ds4: the copied experts pinned in ...: the prompt path DMAs them in place`（読み取り専用なら `read-only`）を出します。どれかの登録が失敗すると `ok=false` となり、stderr に `ds4: pinning the copied experts failed: the prompt path stages them` を出します。ここでは pin 処理の失敗だけでモデル読み込みを失敗扱いにはしません。

## 根拠

- `src/dsv41/ds4_model.cu:97-101` — `env_tri()` の unset / `atoi()` 判定。
- `src/dsv41/ds4_experts_rule.hpp:22-28,174-180` — `DS4_DEFAULTS` の認識値と cache、および `DS4_COPY_PIN` の明示値・自動条件。
- `src/dsv41/ds4_model.cu:4796-4806,4877-4880,4959-4960,4989-5006` — MXFP4 load、コピー呼び出し、CLI モード・RAM 予算によるコピー条件。
- `src/dsv41/ds4_model.cu:90-100,935-948,3267-3282` — HIP build / RDNA4 条件と GPU expert share の算出。
- `src/dsv41/ds4_model.cu:5043-5065` — huge-page arena の割り当てと通常 arena への fallback。
- `src/dsv41/ds4_model.cu:5131-5161` — 値の読み取り時点、host registration、stderr ログと失敗時の継続。
- `src/dsv41/ds4_main.cpp:1348-1350` — `--mmap-experts` の CLI 値。
- `strata_control/speed_switches.py:48-55` — Terminal の DeepSeek speed-ups OFF が設定する `DS4_COPY_PIN=0` と既定状態。

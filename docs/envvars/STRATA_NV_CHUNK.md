# `STRATA_NV_CHUNK`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で未変更。

## 役割

CUDA 版 Strata の裸の `--prefill auto` が NVIDIA GPU で使う prompt chunk の上限を、既定の 8192 から 16384 または 32768 に引き上げる機能を調整します。prefill は入力 prompt を複数の token chunk に分けて処理します。この変数が指定するのは上限であり、実際の chunk は context 長、GPU cache から借りられる buffer、RAM guard によってさらに小さくなる場合があります。

## 値と判定

エンジンは `std::getenv` の値を `nv_chunk_ceiling()` に渡し、次の規則で上限を決めます。整数 parse は行わず、大文字小文字や空白も変換しません。

| `STRATA_NV_CHUNK` | 選ばれる ceiling | 意味 |
|---|---:|---|
| 未設定 | 32768 | 新しい既定上限 |
| 完全一致 `16` | 16384 | 中間の上限 |
| 先頭文字が `0`（例: `0`, `0abc`, `016`） | 0 | NVIDIA の引き上げを行わず、通常の 8192 上限を維持 |
| その他（例: 空文字、`1`, `16x`, `true`, `-1`, 空白） | 32768 | 新しい既定上限 |

`STRATA_DEFAULTS` が `026`, `0.2.6`, `v0.2.6` のいずれかなら、この変数の値にかかわらず ceiling は 0 となり、通常の 8192 に戻ります。`STRATA_DEFAULTS` の判定結果は `qwen_defaults_026()` が初回呼び出し時に static cache します。

## 有効になる条件

- 対象は `!STRATA_USE_HIP && !STRATA_GPU_METAL` の CUDA 系ビルドです。NVIDIA の device count を取得でき、表示されている GPU が 1 台以上必要です。
- 裸の `--prefill auto`（`:N` なし）で、かつ `STRATA_PREFILL_AUTO_MAX` が設定されていない場合だけ候補になります。`--prefill auto:16384`、`auto:32768`、数値指定、および `STRATA_PREFILL_AUTO_MAX` による上限はこの規則の対象外です。`STRATA_PREFILL_AUTO_MAX` が空文字でも設定済みなら裸 auto 扱いにはならず、既存の `atoll("")` により通常上限側になります。
- 全 GPU の compute capability major の最小値が 8 以上の場合だけ上限が引き上げられます。major が 8 未満、または capability の取得に失敗した場合は通常の 8192 のままです。
- 複数 GPU／layer split では、引き上げられた上限が通常 8192 に戻されます。`STRATA_SPLIT_CHUNK16K` を `atoi` で変換して非 0 になる値にした場合は、この clamp が行われません。
- Context 長と cache の fit scan も実際に選べる chunk を制限します。さらに RAM が `resident experts` 分、追加 loan 分、6 GiB の合計を下回る場合、RAM guard は上限を 32768 → 16384 → 8192 と下げます。ただし `STRATA_NV_CHUNK` が文字列として完全に `1` の場合、この guard による引き下げを抑止します。`16` は 16384 の ceiling を選びますが、RAM guard を無効にはしません。

## 実行時の詳細

`--prefill` の引数処理が bare-auto 状態を決めた後、CUDA の NVIDIA 判定箇所で `STRATA_NV_CHUNK` を読みます。値が 0 の場合や対応 GPU がない場合は prefill 設定を引き上げず、初期値の 8192 が使われます。有効な場合は `prefill_auto_max` と `prefill_chunk` に ceiling を設定し、stderr に `strata generate: NVIDIA: --prefill auto may take chunks up to ...` を出します。その後、複数 GPU clamp、RAM guard、context 上限、cache fit scan により chunk の実値が決まります。

ceiling を選ぶ直接読み取りは generate の引数処理中に行われ、そこで `STRATA_NV_CHUNK` を static cache しません。RAM guard は後段で同じ変数を動的な名前で読む `static const char*` を初回評価時に cache します。NVIDIA 経路では名前が `STRATA_NV_CHUNK`、gfx12 経路では `STRATA_GFX12_CHUNK` となる共通コードで、NVIDIA の場合に値が文字列として完全に `1` のときだけ guard による引き下げを無効にします。

`setup.py` の `bare_auto_is_32768()` もこの変数を読む箇所がありますが、これは setup の bench tip を表示するための判定です。設定ファイル側の `env` が当該キーを持てばその値を使い、なければ setup プロセスの `os.environ` を参照します。この判定は実行 engine の設定を変更しません。また、setup は `0` または `16` で始まる値を抑止値とみなすため、エンジン本体の完全一致 `16`／先頭 `0` 判定とは一部異なります。たとえば `16x` は setup の tip 判定では抑止されますが、エンジンでは 32768 を選ぶ値です。

## 根拠

- `include/strata/core/nv_chunk.hpp:15-23`: 未設定、完全一致 `16`、先頭 `0` の値規則。
- `include/strata/core/nv_chunk.hpp:25-29`: 最小 compute capability major が 8 以上である条件と RAM guard の段階値。
- `include/strata/core/defaults_026.hpp:21-29`: `STRATA_DEFAULTS` の許容値と初回読み取り後の cache。
- `src/program/generate.cpp:807-829`: prefill auto の既定値と bare-auto フラグ。
- `src/program/generate.cpp:3526-3548`: CLI `--prefill`、`STRATA_PREFILL_AUTO_MAX`、bare-auto の設定。
- `src/program/generate.cpp:3873-3898`: CUDA の NVIDIA GPU 条件、変数読み取り、上限設定、stderr ログ。
- `src/program/generate.cpp:9655-9709`: context ceiling、multi-GPU clamp、動的な guard 読み取り、RAM guard と `STRATA_NV_CHUNK=1` の例外。
- `setup.py:7918-7931`: setup の情報表示用判定と設定 env／プロセス環境の優先関係。
- `docs/DETAILS.md:1309-1315`: bare auto の上限、RAM guard、layer split と明示指定の説明。コードの現行挙動を優先して記載。

# `STRATA_INTEL_GEN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL エンジンが GPU の世代を `Battlemage` / `Alchemist` / `Unknown` のどれとして扱うかを上書きする。世代分類は、Battlemage 向けカーネルや既定で有効になる最適化など、多数の SYCL 実行時分岐に使われる。設定値はカーネルを直接指定するものではなく、GPU の実世代・能力を変更するものでもない。`engine/sycl/include/strata/sycl_queue.hpp` の `intel_gpu_gen_override()` と `intel_gpu_gen()` が実装箇所である。SYCL は独立したビルドで、通常の CUDA/HIP エンジンではこの判定を使わない（`engine/sycl/CMakeLists.txt:1-11,375-377`）。

例えば `unknown` は Xe3 を含む GPU の自動的な Battlemage 分類を抑止し、`battlemage` は Battlemage 向け分岐を選択可能にする。`alchemist` は Alchemist 向け分岐を選択する。分類は GPU 上の多数の処理から参照されるが、各処理は別途 backend、デバイス能力、build 設定、入力形状などを検査するため、この変数だけで特定カーネルの実行が保証されるわけではない（`engine/sycl/include/strata/sycl_queue.hpp:154-191`; 例: `engine/sycl/src/prefill/esimd_moe.dp.cpp:811-820,840-858`、`engine/sycl/src/prefill/prefill.cpp:4832-4848`）。

## 値と判定

`std::getenv` で取得した文字列全体を `std::string` にし、ASCII の小文字列と完全一致で比較する。前後の空白除去、大文字小文字の正規化、数値変換はしない。未設定または空文字は「上書きなし」。それ以外で許可リストにない値は警告を出して「上書きなし」となり、デバイスの自動判定へ戻る（`engine/sycl/include/strata/sycl_queue.hpp:141-152`）。

| 条件（SYCL の GPU 世代判定） | unset | 有効になる値（例） | 無効値・扱い（例） |
|---|---|---|---|
| `STRATA_INTEL_GEN` が未設定、または空文字 | デバイス情報から自動判定 | 該当なし | `""` は未設定と同じ。警告なし |
| 明示値 | 自動判定を使わず指定世代を返す | `battlemage`、`alchemist`、`unknown` | `Battlemage`、`ALCHEMIST`、`true`、`1`、`0`、` battlemage`、`battlemage `、`battlemage-extra` は不一致。警告後に自動判定へ戻る |

比較は大文字小文字を区別し、文字列全体を比較する。したがって先頭が有効語でも後ろに文字が続けば無効値となる。負値・境界値を数値として解釈する処理はない（同上）。

## 有効になる条件

- **SYCL の GPU デバイスを世代判定する経路で有効。** `intel_gpu_gen()` は GPU 以外なら先に `Unknown` を返して override を呼ばない。GPU の場合は override を自動判定より先に返すため、このコードにベンダー確認はなく、明示値は Intel 以外の SYCL GPU に対する分類にも適用され得る（`engine/sycl/include/strata/sycl_queue.hpp:154-157`）。
- **デバイス自動判定との優先順位:** 有効な明示値は architecture enum、Xe3 判定、デバイス名や PCI ID による推定より優先される。上書きがない場合は Battlemage / Alchemist の architecture enum、Xe3 architecture、名称・PCI ID 等で判定する（`engine/sycl/include/strata/sycl_queue.hpp:154-191`）。
- **分類後も各処理の条件が必要。** 例として ESIMD fused-int8 経路は Battlemage 分類に加え、ESIMD aspect と `sint8 × sint8` の `nsize=16, ksize=32` capability を検査する。また `STRATA_I8_FORCE` が先頭文字 `0` なら利用不可にする（`engine/sycl/src/prefill/esimd_moe.dp.cpp:811-820,840-858`）。
- **routed-expert の処理にも追加条件がある。** 例として grouped/prefetch 経路は in-order Level Zero queue 等を要求し、別の window 経路は `STRATA_HAS_TLA_EXPERT_GU` の build 有無や単一・非 batch 実行などを検査する（`engine/sycl/src/prefill/prefill.cpp:4832-4848,5818-5835`; `engine/sycl/CMakeLists.txt:340-373`）。
- **CLI や他の環境変数は分類値を上書きしないが、機能を別途制御する。** 例えば `--pipeline-windows` が指定済みなら自動選択を行わず、未指定の場合も `--serve`、2 GPU の layer split、MTP 等が揃わなければ有効にならない。`STRATA_PIPELINE_AUTO=0` も自動選択を無効にする（`engine/sycl/src/program/generate.cpp:3590-3618,3620-3634`）。また `STRATA_COPY_ENGINE=1` は copy queue の Battlemage 分類ゲートを迂回する（`engine/sycl/src/core/copy_queue.cpp:90-101`）。

## 実行時の詳細

`intel_gpu_gen_override()` 内の関数ローカル `static const int` 初期化子で、最初にこの関数が評価された時点の環境を読み、そのプロセス内で値を保持する。従って起動後に環境を変更しても再読込されない。空文字・未設定は `-1`、許可値は enum 値、無効値も警告後に `-1` として保持される。`intel_gpu_gen()` は `-1` の場合のみデバイス情報による判定へ進む（`engine/sycl/include/strata/sycl_queue.hpp:141-191`）。

呼び出し側も `static` に判定結果を保持するものがあり、例えば `bm_default_on()` を使うカーネル制御は各 call site で初回評価結果を保存する（`engine/sycl/include/strata/sycl_queue.hpp:196-200`; `engine/sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:688-691`）。そのため変更が反映されないのは override 自身のキャッシュだけでなく、呼び出し側のキャッシュがある経路も含む。

この名前について Strata が行う読み取りは上記の一箇所で、コード上に子プロセスへの転送や環境値の書き換えはない。SYCL の本番実行ファイル `strata` は同じ SYCL engine / prefill ライブラリをリンクする（`engine/sycl/CMakeLists.txt:375-377`）。

## ログと測定値

無効な非空文字列を初回評価したとき、stderr に次の文言を出す。無効値では自動判定へ進み、有効値・未設定・空文字ではこの警告を出さない（`engine/sycl/include/strata/sycl_queue.hpp:142-151`）。

```text
strata: STRATA_INTEL_GEN=<値> is not battlemage, alchemist or unknown; ignored
```

環境変数そのものについて、Strata の資料に条件付きで記載された測定値は確認できなかった。下流機能が選択された場合のログはそれぞれの経路に依存し、例えば pipeline の自動有効時は `strata generate: --pipeline-windows 2 is on by default for a layer split across two Arc B-series cards (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)` を stderr に出す（`engine/sycl/src/program/generate.cpp:3614-3618`）。

## 根拠

- 候補名の実読み取り、値判定、キャッシュ、警告: `engine/sycl/include/strata/sycl_queue.hpp:139-152`
- GPU 世代 override と自動判定: `engine/sycl/include/strata/sycl_queue.hpp:154-191`
- `bm_default_on()` の世代連動: `engine/sycl/include/strata/sycl_queue.hpp:193-200`
- SYCL エンジンのビルド範囲: `engine/sycl/CMakeLists.txt:1-11,375-377`
- 世代に応じた fused-int8 選択と capability 条件: `engine/sycl/src/prefill/esimd_moe.dp.cpp:811-820,840-858`
- 世代依存の実行例と他条件: `engine/sycl/src/program/generate.cpp:3590-3634`; `engine/sycl/src/prefill/prefill.cpp:4832-4848,5818-5835`; `engine/sycl/src/core/copy_queue.cpp:90-101`
- Intel 資料との照合: `docs/INTEL.md:238-245,394-405,419-424`。世代指定と Xe3 の扱いという要約はソースと一致する。資料表だけでは値の完全一致規則、キャッシュ、無効値の fallback までは説明していない。

# `STRATA_CKPT_POOL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

serve engine のチェックポイントプールを有効にします。破棄・退避した会話 checkpoint のベクトル領域を保持し、次の checkpoint 保存や batch slot の保存に再利用します。プールが空なら従来どおり新しい `ConvCheckpoint` を使うため、変数は checkpoint 内容や会話キャッシュの選択規則を指定するものではありません。保存ではコピー先の全 byte を上書きする実装です。[`engine/src/program/generate.cpp:500-503`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L500-L503) [`engine/src/program/generate.cpp:2591-2628`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L2591-L2628)

値を未設定にしたときは、通常 build では単一 stage の serve に会話キャッシュがあり、checkpoint の実行状態サイズが正の場合に自動で有効になります。Metal build ではこの自動有効化をしません。batch slot 用の `STRATA_SLOT_CKPT_MOVE` も同じプールを必要とし、その変数が有効なら本変数を `0` にしていてもプールは有効です。[`engine/src/program/generate.cpp:13838-13840`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13838-L13840) [`engine/src/program/generate.cpp:13905-13915`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13905-L13915)

## 値と判定

`std::getenv` で取得した文字列の先頭 byte だけを見ます。未設定は内部状態 `-1`、先頭 byte が `'0'` なら `0`、それ以外なら `1` です。空文字は設定済みで先頭 byte が `'0'` ではないため有効になります。文字列全体の parse、数値変換、大文字小文字変換、空白除去はしません。[`engine/src/program/generate.cpp:508-517`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L508-L517)

| 条件 | unset | 有効になる値の例 | 無効になる値の例 |
|---|---|---|---|
| 値の判定（全 build 共通） | 内部状態 `-1`。下記の起動条件で既定値を決める | `1`、`true`、`yes`、空文字、その他先頭が `0` でない文字列 | `0`、`0anything`、`00`、`0.5`。先頭が `0` なら残りは見ない |
| `STRATA_CKPT_POOL` を明示設定 | 該当しない | 先頭が `0` でない値 | 先頭が `0` の値 |
| Metal build で unset | 自動既定有効化なし | 該当しない | 該当しない |

判定結果は関数内 `static` に初回呼び出し時に保存されます。実行中に環境を変更しても再読込されません。[`engine/src/program/generate.cpp:510-515`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L510-L515)

## 有効になる条件

- **未設定時の serve 既定値:** Metal 以外で、会話 cache の予算が正、layer split がなく、checkpoint の実行状態サイズが正なら有効になります。cache が無効、layer split がある、またはサイズが 0 なら自動では有効になりません。[`engine/src/program/generate.cpp:13881-13883`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13881-L13883) [`engine/src/program/generate.cpp:13896-13915`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13896-L13915)
- **並列 batch の自動設定:** Linux CUDA build では `o.batch` が 2 以上のとき、ユーザーが設定していなければ engine が環境へ `STRATA_CKPT_POOL=1` を設定します。Windows の gfx1151、または discrete RDNA3 でも、対応する arch defaults が有効で batch slot が 2 以上なら同様に設定します。各設定処理は既存値を保持するので、明示した空文字や `0` も上書きしません。[`engine/src/program/generate.cpp:4410-4414`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L4410-L4414) [`engine/src/core/arch_defaults.cpp:226-260`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/core/arch_defaults.cpp#L226-L260) [`engine/src/core/arch_defaults.cpp:240-245`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/core/arch_defaults.cpp#L240-L245) [`engine/include/strata/core/gfx11_extra.hpp:116-132`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/include/strata/core/gfx11_extra.hpp#L116-L132)
- Windows gfx1151 の既定 stack は `STRATA_GFX1151_DEFAULTS=0` で抑止され、discrete RDNA3 の既定 stack は `STRATA_GFX11_DEFAULTS=0` で抑止されます。Linux CUDA の batch 既定注入にはこの抑止変数はありません。[`engine/src/core/arch_defaults.cpp:240-245`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/core/arch_defaults.cpp#L240-L245) [`engine/src/core/arch_defaults.cpp:312-355`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/core/arch_defaults.cpp#L312-L355)
- `STRATA_SLOT_CKPT_MOVE` の値が先頭 `0` 以外なら共有 pool を必要とするため、`STRATA_CKPT_POOL=0` でも `ckpt_pool.configure` は pool を ON にします。`STRATA_SLOT_CKPT_MOVE` は本変数と同じ先頭 byte 判定です。[`engine/src/program/generate.cpp:560-571`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L560-L571) [`engine/src/program/generate.cpp:13913-13915`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13913-L13915)
- `STRATA_CKPT_POOL_READY` は pool の有効化スイッチではなく、事前に ready にする checkpoint 数です。未設定時は、pool 自体が unset からの自動有効化なら `park_pool_plan` の数を使い、それ以外では 0（先行確保なし）です。したがって `STRATA_CKPT_POOL=1` だけを明示しても先行確保は始まりません。ready 数が 0 でも、pool が ON なら破棄済み checkpoint の領域再利用は行います。[`engine/src/program/generate.cpp:518-533`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L518-L533) [`engine/src/program/generate.cpp:13905-13915`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13905-L13915)
- ready checkpoint の事前確保は layer split では行いません。serve が busy の間も refill を開始せず、pool が空なら新規 checkpoint に fallback します。[`engine/src/program/generate.cpp:14208-14225`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L14208-L14225)

## 実行時の詳細

serve loop で `CheckpointPool` を作り、設定値または上記の既定条件に従って ON/OFF を設定します。checkpoint 保存時は pool から領域を取り、会話 checkpoint の LRU 退避時などに領域を戻します。pool が OFF または空なら `take()` は空の checkpoint を返し、通常の保存経路が使われます。[`engine/src/program/generate.cpp:2595-2628`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L2595-L2628) [`engine/src/program/generate.cpp:14604-14607`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L14604-L14607) [`engine/src/program/generate.cpp:14747-14753`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L14747-L14753)

`STRATA_CKPT_POOL_READY` が正なら、単一 stage の場合に必要な checkpoint 領域を background thread で補充します。補充は request が in-flight でない間に限り、会話 cache budget と `--conversation-cache-min-free-mib` の RAM floor に余裕がある範囲です。request 中に pool が足りない場合は待たずに新しい領域を使います。pool の idle memory は cache budget に計上され、必要時には会話退避や RAM floor の前に返却されます。[`engine/include/strata/core/park_pool_policy.hpp:2-6`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/include/strata/core/park_pool_policy.hpp#L2-L6) [`engine/src/program/generate.cpp:14214-14249`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L14214-L14249)

CLI に `STRATA_CKPT_POOL` を直接切り替える引数はありません。batch 数を指定する CLI 値はアーキテクチャ別の自動注入条件に影響します。通常の unset 既定判定は pool 初期化時に行われ、環境値自体は helper の static cache により初回参照時に一度だけ読み取られます。[`engine/src/program/generate.cpp:510-515`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L510-L515) [`engine/src/program/generate.cpp:13840`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13840) [`engine/src/program/generate.cpp:4410-4414`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L4410-L4414)

## ログと測定値

本変数専用のログはありません。`STRATA_PARK_TRACE` が設定されている場合に限り、pool の on/off、ready 数、上限、checkpoint 1 個の MiB 数、cache 予算が `strata parktrace: park pools: ...` として stderr に出ます。出力は `STRATA_PARK_TRACE` がないと抑制されます。[`engine/src/program/generate.cpp:13954-13959`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L13954-L13959)

ソースコメントには新規ベクトルの zero-fill や page fault を避ける設計意図がありますが、この調査では性能測定を実施していません。[`engine/src/program/generate.cpp:500-503`](https://github.com/Niko1221/Strata/blob/d46f5f268f8ed797e83a5c63a69bffbd7a581cf6/engine/src/program/generate.cpp#L500-L503) `docs/DETAILS.md:1788-1796` は CMP 170HX（GA100、sm_80、PCIe Gen2 x4）での報告値として、`STRATA_CKPT_POOL_READY=N`、`STRATA_PARK_ASYNC=1`、`STRATA_CKPT_GATHER=1` を組み合わせた park 時間 21.5-40.1 / 26.9 ms を載せています。同資料は著者の測定であり、Strata 側では測定していないと明記しています。この複合条件の値を `STRATA_CKPT_POOL` 単独の効果とは扱いません。

## 根拠

- `engine/src/program/generate.cpp:500-533` — 値判定、unset 状態、関連する ready 数。
- `engine/src/program/generate.cpp:13838-13915` — pool 初期化、自動有効化条件、Metal build 条件、明示値との合成。
- `engine/src/program/generate.cpp:2591-2628` — pool の保持、返却、取得。
- `engine/src/program/generate.cpp:14208-14249` — ready pool の補充条件と background refill。
- `engine/src/core/arch_defaults.cpp:226-260, 302-355`、`engine/include/strata/core/gfx11_extra.hpp:116-132` — batch slot 向け環境値注入と arch 条件。
- `engine/include/strata/core/park_pool_policy.hpp:2-6, 22-40` — cache budget と idle 中の upkeep 方針。

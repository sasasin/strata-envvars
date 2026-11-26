# `STRATA_PREFILL_BORROW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

prompt の一時バッファ用に expert cache の slot を借りる動作を残すための抑止スイッチです。`1` で「借用を維持」しますが、適用経路ごとに意味が異なります。Windows HIP の統合 gfx1151 では既定の非借用を取り消し、Linux CUDA の条件付き自動非借用を止めます。Linux HIP の KFD LEND では非借用を無効にしますが、この非借用は `STRATA_KFD_QUIET_LEND=1` による明示 opt-in が前提です。いずれも `generate.cpp` が起動時の GPU・cache 設定を組み立てる間に環境から直接読みます（`engine/src/program/generate.cpp:4399-4405,9505-9529,9533-9567`）。

## 値と判定

全箇所で `getenv` の結果が null でないか、および `value[0] == '1'` かだけを見ます。文字列全体の比較・数値変換・空白除去・大文字小文字変換はありません。したがって `1`、`10`、`1anything` は「借用を維持」する値です。`0`、`true`、`01`、` 1`、空文字はその扱いになりません。unset と空文字は、この変数自体の判定では同じく先頭 `1` ではありません。

| 実行経路 | unset / 空文字 | 先頭が `1` の値 | その他の設定値 |
|---|---|---|---|
| Windows HIP、全可視 GPU が統合 gfx1151 | gfx1151 の既定ブロックが有効なら非借用 | gfx1151 の既定非借用を抑止し、従来どおり借用可能 | 既定ブロックが有効なら非借用を選択 |
| Linux CUDA、自動 cache・batch など下記条件を満たす場合 | cache と prompt バッファが収まれば自動で非借用 | 自動非借用を抑止し、借用を維持 | `STRATA_AUTO_NOBORROW` が先頭 `0` でなければ自動判定を続ける |
| Linux HIP、KFD LEND 対象 GPU | `STRATA_KFD_QUIET_LEND=1` の場合のみ非借用判定へ進む | 非借用判定を抑止 | `STRATA_KFD_QUIET_LEND=1` かつ他条件を満たす場合のみ非借用判定へ進む |

「借用を維持」は `--no-prefill-borrow` を取り消しません。CLI 指定は parse 時に `o.no_prefill_borrow` を true にし、後段の借用状態 `pf_borrow` はその値が false かつ expert profile がある場合に限り true です（`engine/src/program/generate.cpp:4035,6821`）。

## 有効になる条件

- **Windows HIP**: `STRATA_USE_HIP` ビルドで、デバイス情報取得に成功し、全可視 GPU が統合 GPU かつ同じ gfx arch で、arch 名が `gfx1151` の場合に読み取ります。`STRATA_GFX1151_DEFAULTS` が設定され先頭文字が `0` なら gfx1151 既定ブロック全体が止まり、この変数による切替も行われません（`engine/src/program/generate.cpp:4287-4302,4392-4406`）。
- **Linux CUDA**: HIP・Metal・Windows ではないビルドの自動 cache sizing 節でのみ読み取ります。`--expert-cache auto`（内部で `auto_cache`）、借用可能な expert profile、`--prefill auto`、`--batch` が 2 以上、単一 GPU、split なし、helper cache なし、profile の全 pair が cache に入り、という条件がそろう必要があります。さらに `STRATA_AUTO_NOBORROW` が先頭 `0` なら自動非借用を無効にします。`--prefill N` の明示値、layer split、helper cache は対象外です（`engine/src/program/generate.cpp:9505-9510`）。
- **Linux HIP**: HIP かつ Linux の KFD LEND 節です。`class_flag` が立つのは統合 gfx11 の同一 arch が全可視 GPU を占める場合です。arch 判定は gfx1103 / gfx1150 / gfx1151 / gfx1152 / gfx1153 を対象にします。さらに `STRATA_KFD_QUIET=0`（先頭文字）または `STRATA_KFD_QUIET_LEND=0` は無効化し、`STRATA_KFD_QUIET_LEND=1` は既定値を上書きして有効化します。デフォルト `kNoLendDefaultOn` は false です（`engine/src/program/generate.cpp:4291-4302,4337-4340,9541-9545`; `engine/src/core/arch_defaults.cpp:152-160`; `engine/include/strata/core/kfd_quiet.hpp:125-143`）。
- Linux HIP の非借用は、借用状態であり、単一 GPU・split なし・remote helper なしで、chunk が 1〜16,384 tokens、かつ自身の prompt buffer が cache・reserve の横に必要量と 3,072 MiB の余裕を残して収まる場合だけ選ばれます。chunk が範囲外、複数 GPU、または VRAM 不足なら借用を維持します（`engine/src/program/generate.cpp:9544-9566`; `engine/include/strata/core/kfd_quiet.hpp:129-161`）。
- **他の backend**: この変数を読む実装は CUDA / HIP の上記箇所だけです。Metal 等で同名の環境変数による効果は確認できません（直接参照の全件検索結果、および `engine/src/program/generate.cpp:4400,9509,9543`）。

## 実行時の詳細

Windows gfx1151 の既定ブロックは CLI parse 後、cache sizing 前に読みます。非借用を選ぶと `o.no_prefill_borrow` と `o.prefill_own_keep_chunk` を立てます。これにより cache sizing は prompt の自前 buffer 分を見込み、`--prefill auto` が借用なしであることだけを理由に chunk を 2,048 へ縮める処理も避けます。`STRATA_GFX1151_DEFAULTS=0` はこの既定ブロックを止めます（`engine/src/program/generate.cpp:4392-4405,4990-4995,9059-9070`）。

Linux CUDA の自動判定は expert cache の slot 数を決めた後に走ります。全 profile pair が cache に入り、必要な自前 buffer と 3,072 MiB を確保できる場合だけ `o.no_prefill_borrow=true` とし、`pf_borrow=false`、`o.prefill_auto=false`、chunk を最大 8,192 tokens に設定します。cache 全体を保持したまま自前 buffer を使う分岐です（`engine/src/program/generate.cpp:9498-9529`）。

Linux HIP の LEND 判定も cache sizing 後です。env 判定で非借用が有効でも、`no_lend_pick` の条件を満たさなければ何も切り替えません。成功時は借用をやめて `o.prefill_auto=false` としますが chunk 数は変更しません。この判定後、通常の `--no-prefill-borrow` と同様に prompt path の自前 buffer を初期化します（`engine/src/program/generate.cpp:9533-9567,6821-6832`）。

環境値は各 generate 起動の設定処理中に `getenv` で読み直され、static cache には保存されません。実行中の環境変更を再評価する処理はありません。設定の結果は `o.no_prefill_borrow` 等の起動時状態となり、後続の prompt path 初期化で使われます（`engine/src/program/generate.cpp:4400,9508-9510,9541-9566,23993-23994`）。

## ログと測定値

- Linux CUDA の自動判定条件を満たし、`STRATA_PREFILL_BORROW` が先頭 `1` でなく `STRATA_AUTO_NOBORROW` も先頭 `0` でなければ、stderr に `strata generate: every expert fits the cache; the prompt path's own buffers (...) fit ...: no loan of cache slots` または buffer 不足時の `... do not fit ...: the loan stays` が出ます。変数を先頭 `1` にした場合、この判定節に入らず、この行も出ません（`engine/src/program/generate.cpp:9506-9522`）。
- Linux HIP では `STRATA_TRACE` が設定されている場合、KFD LEND 判定が走ると stderr に `strata trace: kfd quiet: prompt path without a loan: ...` が出ます。`STRATA_TRACE` がなければこの理由行は出ません（`engine/src/program/generate.cpp:9554-9560`）。
- 借用しない場合の通常ログは `strata generate: prompt path allocates its own buffers (no cache slots to borrow)`、借用する場合は `strata generate: prompt path borrows ... cache slots ...` です（`engine/src/program/generate.cpp:24115-24116,24108-24112`）。この環境変数名自体を出力する専用ログは見つかりませんでした。
- 自前 buffer の初期化に失敗すると `strata generate: <理由>` を出して終了コード 1 になります。serve の prompt path 初期化では chunk を小さくして再試行する経路もあり、再試行できない失敗は同じく終了コード 1 です（`engine/src/program/generate.cpp:24118-24123,13101-13140`）。

測定値はここでは追加しません。Strix Halo の既存資料は Windows gfx1151 での非借用と `STRATA_PREFILL_BORROW=1` による借用復帰を記載していますが、資料の測定条件をこの環境変数の一般的な効果としては扱いません（`docs/STRIX_HALO_WINDOWS.md:77-85`; `docs/STRIX_HALO.md:146-152`）。

## 根拠

- `engine/src/program/generate.cpp:4399-4405` — Windows gfx1151 の判定と設定。
- `engine/src/program/generate.cpp:9505-9529` — Linux CUDA の条件付き自動非借用。
- `engine/src/program/generate.cpp:9533-9567` — Linux HIP の KFD LEND 判定。
- `engine/include/strata/core/kfd_quiet.hpp:127-161` — LEND の既定値、先頭文字判定、容量条件。
- `engine/src/core/arch_defaults.cpp:152-160` — Linux 統合 GPU の対象 arch 判定。

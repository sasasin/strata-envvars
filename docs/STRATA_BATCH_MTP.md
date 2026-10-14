# `STRATA_BATCH_MTP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。対象は Strata 所有の CUDA、SYCL、Python サーバーのソース。外部ライブラリの環境変数動作は対象外。

## 役割

サーバーの batch slot ごとに MTP（multi-token prediction）の候補を1個作り、通常の slot token と候補 token の2行を同じ verify window で検証します。候補が採用された slot はその window で2 token、採用されない slot は1 token進みます。これを有効にする環境変数です。既定では無効です。

`--batch-mtp` CLI オプションも同じ機能を有効にします。判定は `o.batch_mtp || env_enabled` なので、CLI オプションは環境変数が無効値でも有効化できます。

## 値と判定

CUDA と SYCL の engine は文字列を数値として parse せず、環境変数が設定されていて、空文字でなく、先頭文字が `0` でない場合に有効とします（`src/program/generate.cpp:4491-4492`、`sycl/src/program/generate.cpp:3985-3986`）。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`、`0abc`、`00` | 無効（先頭文字が `0`） |
| `1`、`true`、`false`、`2`、` 0` | 有効（空でなく、先頭文字が `0` でない） |

大文字小文字、空白、数値としての妥当性、文字列全体は検査しません。環境値は engine の起動時に batch MTP の初期化経路で読み取られ、その後の環境変更を再読する実装ではありません。

## 有効になる条件

変数の値が有効でも、CUDA/SYCL engine では次の条件を満たさない場合、batch MTP を無効にして stderr に警告を出し、通常の batch 動作を続けます。

- `--batch` が2以上、`--mtp` が指定済み、`--spec` が2以上で、`--serve` を使う。
- CUDA: layer split を使う場合、各 stage が別 GPU に置かれた構成であること。helper expert cache または `--remote-expert-opt` を使う layer split では batch MTP を無効化する。
- SYCL: 単一 GPU で動かすこと。multi-GPU、helper、layer split がある場合は「one GPU」条件で無効化する。
- CUDA の layer split で複数 slot group の pipeline が選ばれる場合、batch MTP の draft は pipeline と併用できない。`--batch-groups` を省略した自動既定の group 数は `STRATA_BATCH_MTP_SERIAL` などに応じて1へ落ちる場合がある。明示した `--batch-groups auto` も、または `G > 1` の指定も、実際に複数 group へ解決された場合は batch MTP を無効にする。起動時に `--batch-mtp is off` の警告が出る。

条件不足時の警告文は `strata generate: WARNING: --batch-mtp is off: ...` です（CUDA: `src/program/generate.cpp:4493-4512`、SYCL: `sycl/src/program/generate.cpp:3987-3994`）。batch 自体も別途 `--serve` と2 slot 以上が必要です。GPU メモリに slot session や slot drafter が収まらない場合は、使える slot 数を減らすか batch を停止します。

## 実行時の詳細

有効時、各 slot の MTP drafter は solo drafter の重みを共有し、slot ごとの KV state と buffer を持ちます。CUDA layer split では drafters は最終 stage の GPU に置かれます。起動ログには `strata batch: MTP proposals accepted ...` が出て、slot drafters の数と各 slot の private K/V・buffer の容量も表示されます（`src/program/generate.cpp:4631-4653,10161-10164`）。SYCL でも slot ごとの drafter を作成し、最大 draft 数を1にします（`sycl/src/program/generate.cpp:4110-4119`）。

各 batch window は有効な slot を巡回して詰め、MTP 有効時は slot ごとに現在 token と提案 token の2 row を載せます。window 後、対象モデルの出力が提案 token と一致し、EOS/cancel でなく、生成上限と context 上限に余裕がある場合だけ2行分を commit します。それ以外は現在 token の1行分を commit します。継続 slot は window の residual から次の proposal を作ります（CUDA: `src/program/generate.cpp:9951-9981,10033-10042,10090-10106`、SYCL: `sycl/src/program/generate.cpp:9010-9037,9056-9065,9096-9108`）。

通常の verify window は最大8 row です。batch MTP では1 slot あたり2 row なので、1 window では最大4 slot分を処理し、slot がさらにあれば次の window に巡回します。batch MTP が無効なら batch 数を8までに制限しますが、有効ならこの8 slot上限の clamp を行わず、実際には VRAM に収まった数を使います（CUDA: `src/program/generate.cpp:4515-4527,9957-9981`、SYCL: `sycl/src/program/generate.cpp:3996-4008,9013-9037`）。

サーバーは `child_env()` で親プロセスの環境をコピーし、モデル設定の `env` で上書きして engine 子プロセスへ渡します（`serve/server.py:2788-2805`）。また「parallel」数が8を超えたときの案内を出すかの判定にもこの変数を使いますが、Python 側は環境値が `""` または `"0"` の場合だけ MTP なしと扱い、それ以外を案内抑制扱いにします（`serve/server.py:2606-2627`）。従って `STRATA_BATCH_MTP=00` は server の案内を抑制する一方、engine では先頭文字が0なので batch MTP は無効です。この案内判定は engine の有効判定とは一致しません。

## 文書・測定との照合

`docs/BATCHING.md` は環境変数または `--batch-mtp` で有効化すること、slot ごとに1 proposal を検証すること、slot draft 用 VRAM が必要なことを説明しており、実装と一致します（`docs/BATCHING.md:22-39,112-121,210-216`）。layer split の group pipeline との条件も現行実装と一致します。

同資料は測定結果も報告していますが、性能は条件に依存します。例として、2枚のR9700で全expertがVRAMに入る測定は pipeline 既定比で80.2から62.7 tok/sへ低下（-21.9%、5組中0組で高速）と記録され、別の2x RTX 3080 20 GB構成では二つの同時decodeで89.2 tok/s（serial batch MTP）を記載しています。これらは資料記載の構成・測定に限る値で、一般的な性能保証ではありません（`docs/BATCHING.md:41-66`）。同資料は特定の条件下の短いpromptで生成テキストが一致したことも報告しますが、bit-exactness の証明ではないと明記しています（`docs/BATCHING.md:72-76`）。

## 根拠

- `src/program/generate.cpp:4491-4512` — CUDA側の環境値判定、起動条件、警告。
- `src/program/generate.cpp:4631-4653,9951-9981,10033-10106` — slot drafter、row巡回、proposal採用と次候補の生成。
- `sycl/src/program/generate.cpp:3983-4008,4110-4119,9010-9108` — SYCL側の判定、制約、window処理。
- `serve/server.py:2606-2627,2788-2805` — serverのparallel案内判定とengine子プロセスへの環境継承。
- `include/strata/program/batch_groups.hpp:3-11,49-64` — layer splitの自動group選択とbatch MTPの関係。
- `docs/BATCHING.md:22-76,112-121,210-216` — 利用条件、測定条件、制限の説明。

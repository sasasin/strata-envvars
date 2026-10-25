# `--kv-grow`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ推論エンジン） |
| オプション | `--kv-grow` |
| 別名 | なし。無効化用の別フラグ `--no-kv-grow` がある |
| 値 | 値を取らないフラグ |

## 役割

QSA の K/V cache の VRAM を起動時に `--max-context` 全体分確保せず、要求が届いたセル数に応じて段階的に確保します。必要な VRAM は expert cache の領域から回し、足りなければ expert cache の一部を縮めます。短い要求の後は K/V 領域を縮め、profile 上位の expert を cache に戻す経路があります。これは K/V cache の圧縮形式（`--kv`）を選ぶオプションではありません（`src/program/generate.cpp:827-839`、`src/program/generate.cpp:7853-7859`）。

## 使い方

```sh
strata generate --pack /path/to/model --tokens "1,2,3" --expert-profile /path/to/profile.bin --kv-grow
```

エンジンの usage は `strata generate --pack DIR --tokens "1,2,3" [options]` です。`--expert-profile` がない場合は有効化条件を満たしません（`src/program/generate.cpp:808`、`src/program/generate.cpp:988-990`、`src/program/generate.cpp:5196-5207`）。

## 値と既定値

値は不要です。parser は指定時に `kv_grow=true`、`--no-kv-grow` 指定時に `false` とし、同じ実行引数で両方を重ねた場合は後に現れた方が parser 上の値になります。これらのフラグ自体に個別の値 validation はありません（`src/program/generate.cpp:488`、`src/program/generate.cpp:2480-2484`）。

既定は無効です。加えて `STRATA_KV_GROW` が非空ならその値が CLI のフラグ状態を上書きし、先頭文字が `0` なら無効、それ以外なら有効要求として扱います。空または未設定なら CLI の状態を使います（`src/program/generate.cpp:5199-5204`）。

有効化された場合の初期マップ量は `STRATA_KV_GROW_INIT` の正数値（`atoll` で解釈）で指定でき、未設定・非正数なら 16384 cells です。これは CLI 引数ではありません（`src/program/generate.cpp:5211-5213`、`src/core/layer.cpp:625-626`、`src/core/layer.cpp:680-683`）。

## 実行時の動作

`--kv-grow` の要求を実際に有効化するには、単一 GPU、`--kv-resident` が 0 以下（通常は既定の非 streaming 設定）、`--expert-profile` の指定、CPU resident expert mode ではないこと、expert cache が無効値 0 でないこと、remote expert cache がないこと、VMM が利用可能であることが必要です。また `--batch` が 0、`--vram-elastic` が無効、`--peer-device` 未指定である必要があります。いずれかを満たさないと elastic K/V は無効になります（`src/program/generate.cpp:5196-5207`）。

この判定を通っても、実際に grow/trim を行うには VMM range と residency table があり、host residency と source が利用でき、対象の cache slot 数が内部 floor を超えている必要があります。満たさない場合は `kvg_start` が有効にならず、elastic K/V の処理は行われません（`src/program/generate.cpp:7869-7877`）。

K/V pool は VMM range に作られ、最初は初期 cell 数だけ map します。要求ごとに必要な cells を既定 8192 cells 単位（上限 `--max-context`）に切り上げて map し、K/V pool の各 chunk をゼロ初期化します。追加領域は expert cache の slot を空けて捻出し、必要に応じて slot 間で expert を移動します。cache が floor に達した後は新規 VRAM chunk も試みます（`src/core/layer.cpp:638-670`、`src/core/layer.cpp:814-835`、`src/program/generate.cpp:7860-7867`、`src/program/generate.cpp:7885-7893`、`src/program/generate.cpp:7915-7948`、`src/program/generate.cpp:7957-7987`）。

短い要求の完了後は、保持中の会話が要求する分も考慮して K/V を shrink し、解放した chunk を expert cache に戻して profile に従い expert を補充します。既定では要求サイズまで trim し、`STRATA_KV_GROW_HOLD` が `atoi` で非ゼロなら、parked conversation の最長分も保持します。成長量の刻みは `STRATA_KV_GROW_STEP`、cache の slot 下限は `STRATA_KV_GROW_FLOOR` の正数値で変更できます（既定はそれぞれ 8192 cells と 128 slots）。これらの環境変数は CLI parser の値ではありません（`src/program/generate.cpp:7863-7865`、`src/program/generate.cpp:7875-7877`、`src/program/generate.cpp:7990-7998`、`src/program/generate.cpp:8025-8057`、`src/program/generate.cpp:12940-12948`）。

VMM は CUDA の仮想メモリ API とデバイス対応を確認し、HIP では HIP 6 以降かつデバイスの VMM 対応を確認します。HIP では `STRATA_HIP_VMM=0` で無効化できます。これらの確認を通らない実装では `vmm_available()` は false になり、このオプションは有効になりません（`src/core/vmm.cpp:41-56`、`src/core/vmm.cpp:154-167`、`src/core/vmm.cpp:190-209`、`src/core/vmm.cpp:299-308`）。

## 適用条件と副作用

K/V が伸びる間、expert cache が保持する expert 数が減り、profile 外または cache 外の expert は RAM から CPU 計算側へ回り得ます。slot の移動、VMM map/unmap、CUDA/HIP 同期、K/V chunk のゼロ化、residency table の GPU への再転送が発生します。従って「VRAM 使用量が常に減る」または速度が上がるとは限りません。コード上は `--max-context` を縮めるのではなく、K/V と expert cache で VRAM を融通する設計です（`src/program/generate.cpp:7853-7859`、`src/program/generate.cpp:7892-7893`、`src/program/generate.cpp:7950-7966`、`src/core/layer.cpp:663-673`）。

オプションが要求されても条件を満たさない場合、stderr に `--kv-grow is off` と条件概要を出します。VMM pool の reserve/map 失敗は session 初期化失敗となり、エンジンは終了コード 1 で終了します（`src/program/generate.cpp:5208-5213`、`src/core/layer.cpp:833-835`、`src/program/generate.cpp:5215-5220`）。

実行中の成長失敗は、通常の prompt / token 経路では stdout に `ERR the K/V cannot grow...` を出して終了コード 1 になります。serve の会話復元など一部の経路では要求を拒否するか、同様のエラーを表示してエンジンを終了します。grow 中に CUDA エラーが起きると tier が途中状態になり得るため、コードは処理を続けず停止させる経路を設けています（`src/program/generate.cpp:12540-12546`、`src/program/generate.cpp:12246-12250`、`src/program/generate.cpp:12829-12833`、`src/program/generate.cpp:15077-15081`）。

## 根拠

- usage とオプション説明: `src/program/generate.cpp:808`、`src/program/generate.cpp:836-839`
- parser と CLI/environment 優先順位、有効化条件: `src/program/generate.cpp:2480-2484`、`src/program/generate.cpp:5196-5213`
- VMM 初期化と K/V pool map: `src/core/vmm.cpp:41-56`、`src/core/vmm.cpp:154-167`、`src/core/layer.cpp:680-705`、`src/core/layer.cpp:814-848`
- cache slot の退避・成長・縮小: `src/program/generate.cpp:7885-7987`、`src/program/generate.cpp:7990-8057`
- 失敗処理: `src/core/layer.cpp:663-674`、`src/program/generate.cpp:5215-5220`、`src/program/generate.cpp:12540-12546`

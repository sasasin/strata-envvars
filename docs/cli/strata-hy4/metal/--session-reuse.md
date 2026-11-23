# `--session-reuse`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（serve モード） |
| オプション | `--session-reuse` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換し、0 は無効、0 以外は有効 |

## 役割

`--serve` で起動した Metal の行プロトコルサーバーに、要求間で会話の token 列と KV cache を保持し、後続 prompt と先行会話の共通 prefix を再利用させます。既定は無効です。単発の非 serve 実行では値を設定しても serve 側の再利用処理には入りません。

## 使い方

```sh
# Metal serve を起動し、会話 prefix の再利用を有効にする
strata-hy4-metal --model /path/to/model.strata --serve --session-reuse 1

# 再利用を明示的に無効にする（既定と同じ）
strata-hy4-metal --model /path/to/model.strata --serve --session-reuse 0
```

## 値と既定値

省略時は `session_reuse = false` です。値は `atoi` に渡され、その結果が 0 なら無効、0 以外なら有効です。オプション独自の範囲検証や拒否経路はありません。値を取る引数であるため、値も指定してください。

## 実行時の動作

`--serve` が有効なとき、main はこの値を `ServeOpts.session_reuse` に渡します。有効時、serve は会話 slot を最大4個、KV cache 予算を 16384 MiB、SWA ring slack を 8192 にする既定値を設定します。`--conversation-slots`、`--conversation-cache-mib`、`--ring-slack` を同時指定した場合は、それぞれの明示値が使われます。実際の slot 数は KV set のサイズと予算に応じて指定 slot 数以下に制限されます。

要求ごとに既存 slot の token と prompt の共通 prefix を探し、再利用可能な slot を選びます。再開位置が正なら `RESUME <位置>` を出力し、その位置から prompt の残りを処理します。複数 slot 時は再利用位置が `--conversation-min-tokens` による下限（短い prompt では prompt 長の半分まで縮小）を満たす slot を選び、該当しない場合は free、空きがなければ LRU slot を選びます。無効時は slot の prefix 再利用をしません。

有効時は SSD spill も条件付きで有効になります。明示した `--conversation-spill-dir` があればその場所を使い、未指定でもモデルパスに `/models/` が含まれる場合はその親の `conversation-spill` が既定 root になります。どちらも空なら spill は行われません。また `--conversation-spill-mib 0` でも spill は無効です。spill 対象は `--conversation-min-tokens` 以上の処理済み token を持つ slot で、`--conversation-spill-persist` を使う場合は終了時にも resident conversation を保存します。

## 適用条件と副作用

再利用は `--serve` 経路にのみ適用されます。画像を含む要求は slot 選択時に `no_reuse` 扱いとなり、完了後の KV 位置も 0 に戻るため、画像要求の前後で会話 KV は再利用されません。`INFO` 行には `session_reuse=0|1` と、実効 slot 数・spill 状態が報告されます。

有効化すると追加の KV slot が GPU/Metal 側の作業集合に加わり、条件が整えば spill 用 KV set とファイル I/O も発生します。slot 数のメモリ予算による制限や spill の容量等は関連オプションで調整します。

## 出力とエラー

serve 起動時に stdout の `INFO` 行で設定状態が通知されます。共通 prefix を使って処理を再開した要求では `RESUME <位置>` が出力されます。オプション値自体を検証してエラーにする分岐は見つかりませんでした。serve の一般的な引数・モデル読み込み・要求処理の失敗は別の条件で発生し、このスイッチ固有の失敗経路とは確認できませんでした。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497` — serve と再利用の既定値、および関連 cache/spill 引数の初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1590-1599` — Metal parser の `--serve`、`--session-reuse` と関連引数の値変換。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1655` — serve 経路への分岐と、`ServeOpts` への値・関連既定値の設定。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:219-242` — serve 初期化と、有効時に cold-expert 作業集合計画へ slot/spill の予算を渡す処理。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:260-276` — 実効 slot 数の予算計算と、session reuse 条件付き spill 初期化。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:302-304` — `INFO` と `READY` の出力。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:375-391` — 要求ごとの slot 選択、再利用無効化条件、spill 候補の復元判定。
- `engine/src/hy4flash/metal/hy4_metal_slots.h:35-67` — prefix 再利用位置の選択、複数 slot 時の再利用下限、free/LRU 選択。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:419-460` — slot 退避時の spill と復元後の再開位置計算。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:564-593` — 無効時または画像要求時の再利用状態リセット、および永続 spill の終了時保存。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:71-78` — 明示 spill root、モデルパスに基づく既定 root、無効時の root 判定。

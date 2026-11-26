# `strata generate --session-min-free-mib`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--session-min-free-mib` |
| 別名 | なし |
| 値 | MiB 単位の 10 進非負整数。上限は `INT64_MAX / 1,048,576`（8,796,093,022,207） |

## 役割

`--serve` のセッションを `SAVE <path>` でディスクへ保存するとき、保存後にそのボリュームへ残す空き容量の下限を指定します。既定値は 4096 MiB です。`--serve` では会話キャッシュの SSD tier を初期化する際にも同じ下限を空き容量から差し引き、tier の予算を抑えます。

## 使い方

```sh
# serve を起動し、セッション保存後に少なくとも 8192 MiB を残す
strata generate --serve --pack ./data/packs/example --session-min-free-mib 8192 --tokens "1,2,3"
```

## 値と既定値

- 省略時は 4096 MiB です。別名はありません。
- parser は値全体を `int64_t` の 10 進整数として読み、負数、整数でない値、値全体を読み切れない値、MiB からバイトへ変換できる上限を超える値を拒否します。重複指定は parser の走査順で後の値が上書きします。
- `0` は `SAVE` 時の空き容量事前確認を無効にします。負数や形式不正では stderr にエラーを出し、終了コード 2 で引数解析を中断します。

## 実行時の動作

`--serve` 中の `SAVE <path>` は、保存するセッションの全体サイズを計算した後、指定先のボリュームの空き容量を調べます。下限が 0 より大きい場合、保存ファイルのサイズと指定下限の合計を確保できなければ書き込み前に拒否します。サイズ確認を通ると、一時ファイルへ書き込み、完了後に保存先名へ publish します。したがって、この設定はディスク容量を予約するものではなく、確認後に他プロセスが空き容量を消費する競合までは防ぎません。

会話キャッシュの SSD tier が有効な場合、tier 初期化時の空き容量からこの下限を引いて tier の上限を計算します。計算された tier 予算が 64 MiB 未満なら tier は無効になります。この効果は `SAVE` の容量確認とは別の起動時処理です。

## 適用条件と副作用

この値が `SAVE` の容量確認に使われるのは `--serve` の `SAVE <path>` です。`--serve` なしでは値は parser に保存されますが、確認したソース上ではこの用途の実行経路がありません。`RESTORE` の読み込みや通常の生成の空き容量判定には使われません。

`0` は `SAVE` の事前確認だけを無効にします。ディスクが実際に不足している場合の書き込み失敗は防がず、SSD tier については空き容量から差し引く下限が 0 になるだけで、tier 自体は別条件（予算が 64 MiB 以上など）に従います。

## 出力とエラー

容量を確認できない場合、または保存ファイル全体と下限を満たす空き容量がない場合、保存処理は失敗します。後者は `storage` 種別として扱われ、stderr に `strata serve: session save <path>: ...`、標準出力に `SERR storage 0 ...` を出します。SAVE の拒否後もサーバーの処理ループは継続します。ディスク容量確認を通った後の書き込み・flush・rename も別途失敗することがあります。

## 根拠

- `engine/src/program/generate.cpp:1110-1111` — 値の既定値と SAVE 時の意味。
- `engine/src/program/generate.cpp:1312` — CLI usage の表示（既定値 4096、0 は確認なし）。
- `engine/src/program/generate.cpp:4084-4107` — parser、整数範囲検証、値の格納。
- `engine/src/program/generate.cpp:14058-14066` — serve 中の会話 SSD tier 予算から下限を控除し、64 MiB 未満で tier を無効化。
- `engine/src/program/generate.cpp:18568-18580` — `SAVE <path>` が `--serve` の要求として処理されること。
- `engine/src/program/generate.cpp:18705-18712` — `session_min_free_mib` をバイトへ変換して保存処理へ渡し、失敗を `SERR` 経路へ送る。
- `engine/src/program/generate.cpp:18721-18724`、`engine/src/program/generate.cpp:18805-18806` — 保存成功時の stderr/stdout と、要求処理の継続。
- `engine/src/core/conversation_file.cpp:1098-1109` — ファイル総サイズと空き容量・下限を比較し、不足時に `SessionError::storage` を返す。
- `engine/src/core/conversation_file.cpp:326-332` — Windows で保存先ドライブの空き容量を取得する実装。その他のプラットフォームでは同ファイル `engine/src/core/conversation_file.cpp:520` 付近で `statvfs` を使う。
- `engine/sycl/src/program/generate.cpp:740-741`、`engine/sycl/src/program/generate.cpp:2065-2078`、`engine/sycl/src/program/generate.cpp:8241-8249`、`engine/sycl/src/program/generate.cpp:10425-10432` — SYCL parser と SSD tier / SAVE の同等経路。

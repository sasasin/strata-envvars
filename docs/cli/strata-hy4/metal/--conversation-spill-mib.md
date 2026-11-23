# `strata-hy4-metal --conversation-spill-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal、`--serve` 実行時） |
| オプション | `--conversation-spill-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数として `atoi` で変換される値 |

## 役割

`--serve --session-reuse` で使う会話 KV キャッシュの SSD spill tier の容量上限を MiB で指定する。常駐スロットから退避した会話の KV をディスクに保存し、後続リクエストで再利用する機能の予算である。Metal runner の既定値は `32768` MiB（32 GiB）だが、SSD tier 自体が有効になるには session reuse と spill 保存先も必要。

## 使い方

```sh
strata-hy4-metal --model /path/to/model.strata --serve --session-reuse 1 \
  --conversation-spill-dir /path/to/local-spill --conversation-spill-mib 8192
```

この例では serve 中の spill tier の索引済みエントリ容量を 8192 MiB に制限する。保存先は既存データを含むディレクトリとして扱われるため、用途に合わせた専用ディレクトリを指定する。

## 値と既定値

- 値は次の引数文字列を `atoi` で変換した `int`。parser に明示的な範囲検査やエラー処理はない。変換後が `0` 以下なら spill 初期化を行わない。
- 省略時は `32768` MiB。
- `atoi` のため、非数値で始まる値は `0`、数値の後ろに非数字が続く値は数字部分として扱われる。負数も受理されるが、実行時の初期化条件を満たさず tier は無効となる。
- このオプションの値を指定する必要があるが、parser の `nxt()` 呼び出しに引数欠落時の専用 validation はない。

## 実行時の動作

`--conversation-spill-mib` の値は `ServeOpts::spill_mib` に渡される。spill は `--serve` 分岐の中でのみ利用され、さらに `--session-reuse` が有効で、spill root が空でなく、容量が正の場合に初期化される。したがって、この容量指定だけでは spill を有効化しない。

spill root は `--conversation-spill-dir` が空でなければその指定値を使う。指定がなく、session reuse が有効で、モデルパスに `/models/` が含まれる場合はその `/models/` より前を data root として `<data>/conversation-spill` を使う。それ以外は root が空になり SSD tier は動作しない。初期化時に上限を MiB × 1,048,576 bytes に変換する。容量超過時は最も古い sequence の保存エントリから削除し、上限内に収める。従ってこの上限は会話スロットの Metal メモリ量ではなく、spill 保存エントリの索引上の合計サイズに適用される。

spill が有効なとき、会話スロットの退避時に保存ジョブをバックグラウンド writer に渡す。後続リクエストで保存済み会話が常駐スロットより長い prefix を再利用できる場合、KV を読み戻す。終了時には writer を停止し、非永続モードのプロセス別ディレクトリを削除する。永続モードの扱いは [`--conversation-spill-persist`](--conversation-spill-persist.md) を参照。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal serve 経路。通常のオフライン生成では容量値は `ServeOpts` に渡されず、spill tier は開始されない。
- `--session-reuse` が無効なら root の既定解決は空となり、serve 側も spill 初期化を呼ばない。明示的な spill directory を指定しても、session reuse が無効なら tier は開始されない。
- spill root とその `hy4-<fingerprint>` 配下のディレクトリ作成を試みる。初期化成功時は会話 KV をファイルに書き込み、容量超過時や同一会話のより長い保存時に古いファイルを削除する。非永続モードでは終了時にプロセス別ディレクトリを削除する。
- root が空、容量が 0 以下、または session reuse が無効の場合は、spill はオフ。root/容量条件を満たして初期化を試みたものの、fingerprint ディレクトリを作成・確認できない場合も spill を無効にする。

## 出力とエラー

spill ディレクトリを作成・確認できず初期化に失敗した場合、stderr に `[spill] cannot create <path>: spill off` を出す。これは serve 全体の失敗ではなく spill の無効化経路で、stdout の serve `INFO` 行では `spill=0` と報告される。容量値自体について専用の validation error は確認できない。

書き込み成功時は stderr に保存 token 数、MiB、所要時間を出す。writer loop は `write_job` の戻り値を検査せず、書き込み失敗時に対応する専用エラー出力は確認できなかった。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1494-1497` — spill 容量の既定値 `32768` MiB と関連引数の初期値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1597-1599` — `--conversation-spill-mib` parser。`atoi` 変換、専用 validation なし。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1655` — serve 分岐で `ServeOpts` を組み立て、spill root と容量値を渡す。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:71-78` — 明示 root、`/models/` を含むモデル path、session reuse による既定 root の解決。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:31-34,219-232,271-276` — serve 設定の既定値と session reuse/root/正の容量を条件にした初期化。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:180-200` — 容量を byte 上限に変換し、spill directory を確認して writer を起動する処理と初期化エラー。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:40-49,302-304` — protocol 出力先が stdout であることと `INFO` 行。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:386-429,431-453,455-474` — spill file 書き込み、古い sequence から容量を削る処理、writer loop。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:383-390,419-425,570-593` — 退避データの再利用、スロット退避、永続時終了処理。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:330-335` — writer 停止後、非永続ディレクトリを削除する処理。

# `--conversation-spill-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--conversation-spill-dir` |
| 別名 | なし |
| 値 | spill データのルートディレクトリを表す文字列 |

## 役割

`--serve` とセッション再利用を併用する Metal サーバーで、会話スロットの KV 状態を一時退避または永続化する spill データのルートを指定する。サーバーはスロット退避時に状態を書き出し、後続リクエストの共通 prefix が常駐スロットより長ければ読み戻す。spill が有効になるには `--session-reuse` が真で、spill 容量 `--conversation-spill-mib` が正である必要がある。

## 使い方

```sh
strata-hy4-metal --serve --model /data/strata/models/Hy4.strata \
  --session-reuse 1 --conversation-spill-dir /var/tmp/strata-spill
```

この例では spill のルートを明示する。永続化するかどうかは別オプション `--conversation-spill-persist` で決まり、この指定だけではプロセスをまたいで保存しない。

## 値と既定値

- 値は `--conversation-spill-dir` の直後の引数を文字列として受け取り、パスの存在、書き込み権限、絶対パスかどうかの事前検証は行わない。値の正規化や空白のトリムもない。引数 parser は `argv[++i]` をそのまま読む実装であり、値を省略した呼び出しは正常な入力として扱われない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1597`）。
- 既定値は空文字列。空文字列または未指定なら明示パス扱いにならず、セッション再利用が有効で、モデルパスに `/models/` が含まれる場合に限り、該当部分より前を基点に `<data>/conversation-spill` を使う。それ以外は spill root が空となる（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1495-1497`, `engine/src/hy4flash/metal/hy4_metal_spill.h:71-78`）。

## 実行時の動作

Metal runner は `--serve` の処理で値を `hy4_spill_root` に渡し、解決した root を `ServeOpts` に設定する。`--session-reuse` が無効、root が空、または `--conversation-spill-mib` が 0 以下の場合は spill 層を初期化しない。したがって、このディレクトリ指定だけで spill は有効にならない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1592-1599,1636-1654`; `engine/src/hy4flash/metal/hy4_metal_serve.h:227-232,271-277`）。

初期化時に root とその下のモデル・設定 fingerprint 別ディレクトリをモード `0755` で作成しようとする。実際の保存先は `<root>/hy4-<fingerprint>.p<PID>`（通常）または `<root>/hy4-<fingerprint>`（永続化）で、fingerprint はモデル名・ファイル情報、Engram のファイル情報、context/ring/層構成等から作る。ディレクトリ作成後に保存先がディレクトリとして確認できなければ stderr に `[spill] cannot create ...: spill off` を出し、spill を無効にする。初期化失敗はサーバー起動全体のエラーにはせず、起動時の `INFO` 行では `spill=0` と報告される（`engine/src/hy4flash/metal/hy4_metal_spill.h:42-62,80-83,181-201`; `engine/src/hy4flash/metal/hy4_metal_serve.h:302-304`）。

spill 有効時、セッション再利用で退避対象となった十分な長さの会話状態はバックグラウンド writer に渡され、後続リクエストで再利用候補になります。保存ファイルは一時ファイルへ書き、完了後 rename します。通常モードではプロセス終了時にプロセス固有ディレクトリを削除します。永続化モードでは終了時に resident conversation も書き込み、ディレクトリを残して次回起動時に採用します。次回初期化時には root 内の終了済み PID に属するプロセス固有ディレクトリを削除します（`engine/src/hy4flash/metal/hy4_metal_serve.h:383-390,419-438,570-592`; `engine/src/hy4flash/metal/hy4_metal_spill.h:4-6,96-116,233-245,386-429,476-502,325-335`）。

## 適用条件と副作用

- この値を利用するのは `strata-hy4-metal --serve` 経路である。サーバー起動前のモデル読み込みや `--load-only` などでは、値を parser が受理しても spill root の設定・初期化には進まない（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1597,1635-1654`）。
- spill の実効条件は `--session-reuse` 有効かつ `--conversation-spill-mib > 0`。これらの設定は別 option であり、容量上限など spill の保存量は `--conversation-spill-mib` が制御する（`engine/src/hy4flash/metal/hy4_metal_serve.h:31-34,227-232,271-277`）。
- 指定した root と配下の fingerprint ディレクトリを作成し、KV 状態をファイルに書く。永続化しない場合、終了時に当該プロセス用ディレクトリ内のファイルを削除する。永続化する場合、保存済み状態を次回起動時に再利用するためデータを残す（`engine/src/hy4flash/metal/hy4_metal_spill.h:80-93,181-201,325-335`; `engine/src/hy4flash/metal/hy4_metal_serve.h:570-592`）。
- 保存失敗（open/write/rename 等）の詳細な診断や終了コードはこの経路では報告されず、spill の保存・再利用が成立しないことがある。ソース上、ディレクトリ初期化時の失敗メッセージ以外に、各書き込み失敗を stderr に出す処理は確認できない（`engine/src/hy4flash/metal/hy4_metal_spill.h:386-417,455-473`）。

## 出力とエラー

- serve の stdout `INFO` 行に spill 層の有効状態 `spill=0|1` と永続化状態 `persist=0|1` が含まれる。ログや診断は stderr、serve プロトコルは stdout に出す設計（`engine/src/hy4flash/metal/hy4_metal_serve.h:4-9,302-304`）。
- spill 保存先をディレクトリとして確認できない場合は stderr に `[spill] cannot create <path>: spill off` を出し、spill だけを無効化して処理を続ける（`engine/src/hy4flash/metal/hy4_metal_spill.h:188-200`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1495-1497,1592-1599` — 既定値、parser、隣接するセッション再利用・spill 容量オプション。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1636-1654` — serve 経路での設定転送。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:71-83,181-201` — root の既定値、ディレクトリ作成、初期化失敗時の扱い。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:227-232,271-277,302-304` — 適用条件、spill 層初期化、起動時状態表示。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:383-390,419-438,570-592` — 再読み込み・退避・終了時の永続化。
- `engine/src/hy4flash/metal/hy4_metal_spill.h:96-116,233-245,325-335,386-429,476-502` — stale directory の削除、書き込み・保持・クリーンアップ・永続データの採用。
